from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from app.core.config import settings
from app.services.performance_state_advanced_service import (
    TAIL_MODEL_VERSION,
    advanced_state_path,
    tail_state_path,
)
from app.services.performance_state_service import (
    DEVELOPMENT_YEAR,
    ROLES,
    STATE_MODEL_VERSION,
    TEST_YEAR,
    filtered_state_path,
)


FORECAST_MODEL_VERSION = "collapse_rebound_forecast_v1"
VALIDATION_VERSION = "performance_state_external_diagnostic_v1"
SHADOW_MODEL_VERSION = "performance_state_shadow_monitor_v1"
TARGETS = (
    "process_collapse",
    "result_collapse",
    "return_to_baseline",
    "strong_rebound",
)
TARGET_LABELS = {
    "process_collapse": "Process Collapse",
    "result_collapse": "Result Collapse",
    "return_to_baseline": "Return to Baseline",
    "strong_rebound": "Strong Rebound",
}
REBOUND_TARGETS = {"return_to_baseline", "strong_rebound"}
KEYS = ["year", "pitcher_id", "role", "game_pk", "game_date"]

FEATURE_LAYERS: dict[str, list[str]] = {
    "A_baseline": [
        "lag_process_score",
        "lag_result_score",
        "process_ma5",
        "process_ewm",
        "lag_process_volatility",
        "calendar_days_since_prior",
        "previous_appearance_pitches",
        "workload_pitches_7d",
        "workload_pitches_28d",
        "season_pitches_before",
    ],
    "B_latent_state": [
        "stuff_state_forecast",
        "stuff_state_forecast_sd",
        "command_state_forecast",
        "command_state_forecast_sd",
        "result_state_forecast",
        "result_state_forecast_sd",
    ],
    "C_regime_prior": [
        "regime_prior_stable",
        "regime_prior_declining",
        "regime_prior_collapse",
        "regime_prior_recovering",
        "regime_prior_high_volatility",
    ],
    "D_gas_har": ["gas_har_variance_forecast"],
    "E_evt": [
        "evt_extreme_probability",
        "evt_expected_loss_severity",
        "evt_tail_supported",
    ],
    "F_challengers": ["gjr_variance_forecast", "caviar_var95"],
}


def forecast_audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_slice8_9.json"


def forecast_state_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"performance_state_forecasts_{int(year)}.parquet"


def shadow_audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_slice11.json"


def shadow_ledger_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_shadow_ledger.parquet"


def _number(value: Any, digits: int = 6) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return round(float(numeric), digits) if pd.notna(numeric) and np.isfinite(float(numeric)) else None


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register("forecast_states", frame)
        target = str(temporary).replace("'", "''")
        connection.execute(f"COPY forecast_states TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    temporary.replace(path)


def _load_panel(root: Path, years: tuple[int, int]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year in years:
        filtered = filtered_state_path(year, root)
        advanced = advanced_state_path(year, root)
        tail = tail_state_path(year, root)
        for path in (filtered, advanced, tail):
            if not path.exists():
                raise FileNotFoundError(f"Frozen Performance State artifact not found: {path}")
        with duckdb.connect() as connection:
            base = connection.execute("SELECT * FROM read_parquet(?)", [str(filtered)]).fetchdf()
            advanced_rows = connection.execute(
                "SELECT * EXCLUDE (year, game_date) FROM read_parquet(?)", [str(advanced)]
            ).fetchdf()
            tail_rows = connection.execute(
                "SELECT * EXCLUDE (year, game_date) FROM read_parquet(?)", [str(tail)]
            ).fetchdf()
        base["year"] = int(year)
        base = base.merge(advanced_rows, on=["pitcher_id", "role", "game_pk"], how="left", validate="one_to_one")
        base = base.merge(tail_rows, on=["pitcher_id", "role", "game_pk"], how="left", validate="one_to_one")
        frames.append(base)
    panel = pd.concat(frames, ignore_index=True)
    panel["game_date"] = pd.to_datetime(panel["game_date"], errors="coerce")
    panel["evt_tail_supported"] = panel["evt_tail_supported"].astype(float)
    return panel.sort_values(["pitcher_id", "role", "game_date", "game_pk"], kind="stable").reset_index(drop=True)


def _cumulative_features(layer: str) -> list[str]:
    names: list[str] = []
    for layer_name, columns in FEATURE_LAYERS.items():
        names.extend(columns)
        if layer_name == layer:
            return names
    raise ValueError(f"Unknown feature layer: {layer}")


def _observed_features(frame: pd.DataFrame, features: list[str]) -> list[str]:
    return [feature for feature in features if frame[feature].notna().any()]


def _eligible_rows(panel: pd.DataFrame, role: str, target: str) -> pd.DataFrame:
    rows = panel[panel["role"].eq(role) & panel[target].notna()].copy()
    if target in REBOUND_TARGETS:
        rows = rows[rows["lag_process_collapse"].fillna(False)].copy()
    return rows.sort_values(["game_date", "game_pk", "pitcher_id"], kind="stable")


def _chronological_split(rows: pd.DataFrame) -> dict[str, pd.DataFrame]:
    dates = rows["game_date"].dropna()
    if dates.empty:
        return {name: rows.iloc[0:0].copy() for name in ("train", "calibration", "validation")}
    train_cutoff = dates.quantile(0.60)
    calibration_cutoff = dates.quantile(0.80)
    return {
        "train": rows[rows["game_date"].le(train_cutoff)].copy(),
        "calibration": rows[rows["game_date"].gt(train_cutoff) & rows["game_date"].le(calibration_cutoff)].copy(),
        "validation": rows[rows["game_date"].gt(calibration_cutoff)].copy(),
    }


@dataclass
class CalibratedModel:
    estimator: Any
    calibrator: LogisticRegression | None
    prevalence: float

    def predict(self, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
        raw = np.asarray(self.estimator.predict_proba(frame[features])[:, 1], dtype=float)
        if self.calibrator is None:
            return np.clip(raw, 1e-6, 1 - 1e-6)
        logits = np.log(np.clip(raw, 1e-6, 1 - 1e-6) / np.clip(1.0 - raw, 1e-6, 1 - 1e-6))
        return np.clip(self.calibrator.predict_proba(logits.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6)


def _new_logistic() -> Any:
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(max_iter=2000, C=0.5),
    )


def _new_xgboost() -> Any:
    return XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        n_estimators=160,
        learning_rate=0.03,
        max_depth=3,
        min_child_weight=10,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=2.0,
        n_jobs=4,
        random_state=20261005,
    )


def _fit_calibrated(
    estimator: Any,
    train: pd.DataFrame,
    calibration: pd.DataFrame,
    features: list[str],
    target: str,
) -> CalibratedModel:
    truth = train[target].astype(int)
    prevalence = float(truth.mean()) if len(truth) else 0.5
    if len(train) == 0 or truth.nunique() < 2:
        raise ValueError(f"Insufficient classes to fit {target}.")
    estimator.fit(train[features], truth)
    calibrator: LogisticRegression | None = None
    calibration_truth = calibration[target].astype(int)
    if len(calibration) and calibration_truth.nunique() == 2:
        raw = np.asarray(estimator.predict_proba(calibration[features])[:, 1], dtype=float)
        logits = np.log(np.clip(raw, 1e-6, 1 - 1e-6) / np.clip(1.0 - raw, 1e-6, 1 - 1e-6))
        calibrator = LogisticRegression(max_iter=1000, C=1.0)
        calibrator.fit(logits.reshape(-1, 1), calibration_truth)
    return CalibratedModel(estimator=estimator, calibrator=calibrator, prevalence=prevalence)


def _calibration_summary(truth: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    bins = pd.qcut(pd.Series(clipped), q=min(10, len(clipped)), duplicates="drop")
    table: list[dict[str, Any]] = []
    for _, positions in pd.Series(np.arange(len(clipped))).groupby(bins, observed=True):
        index = positions.to_numpy(dtype=int)
        table.append({
            "rows": int(len(index)),
            "mean_probability": _number(clipped[index].mean()),
            "observed_rate": _number(truth[index].mean()),
        })
    weights = np.array([row["rows"] for row in table], dtype=float)
    errors = np.array([abs(row["mean_probability"] - row["observed_rate"]) for row in table])
    ece = float(np.average(errors, weights=weights)) if len(weights) else math.nan
    slope = intercept = None
    if len(np.unique(truth)) == 2:
        logits = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
        model = LogisticRegression(C=1e6, max_iter=1000).fit(logits, truth)
        slope = _number(model.coef_[0, 0])
        intercept = _number(model.intercept_[0])
    return {"ece": _number(ece), "intercept": intercept, "slope": slope, "bins": table}


def _metrics(truth: pd.Series | np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    y = np.asarray(truth, dtype=int)
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    if len(y) == 0 or len(np.unique(y)) < 2:
        return {"rows": int(len(y)), "events": int(y.sum()), "prevalence": _number(y.mean()) if len(y) else None,
                "average_precision": None, "brier": None, "log_loss": None, "calibration": {}}
    return {
        "rows": int(len(y)),
        "events": int(y.sum()),
        "prevalence": _number(y.mean()),
        "average_precision": _number(average_precision_score(y, p)),
        "brier": _number(brier_score_loss(y, p)),
        "log_loss": _number(log_loss(y, p, labels=[0, 1])),
        "calibration": _calibration_summary(y, p),
    }


def _alert_metrics(truth: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict[str, Any]:
    alerts = probabilities >= threshold
    positives = truth == 1
    negatives = ~positives
    return {
        "threshold": _number(threshold),
        "alert_rate": _number(alerts.mean()),
        "recall": _number((alerts & positives).sum() / max(positives.sum(), 1)),
        "false_alert_rate": _number((alerts & negatives).sum() / max(negatives.sum(), 1)),
    }


def _fixed_false_alert_threshold(truth: np.ndarray, probabilities: np.ndarray) -> float:
    negative_scores = probabilities[np.asarray(truth, dtype=int) == 0]
    return float(np.quantile(negative_scores, 0.90)) if len(negative_scores) else 1.0


def _bootstrap_delta(
    rows: pd.DataFrame,
    target: str,
    probabilities: np.ndarray,
    baseline: np.ndarray,
    samples: int = 100,
) -> dict[str, Any]:
    working = rows[["pitcher_id", target]].copy().reset_index(drop=True)
    working["probability"] = probabilities
    working["baseline"] = baseline
    pitchers = working["pitcher_id"].dropna().unique()
    rng = np.random.default_rng(20261005)
    ap_deltas: list[float] = []
    brier_deltas: list[float] = []
    for _ in range(samples):
        sampled = rng.choice(pitchers, size=len(pitchers), replace=True)
        chunks = [working[working["pitcher_id"].eq(pitcher)] for pitcher in sampled]
        boot = pd.concat(chunks, ignore_index=True)
        truth = boot[target].astype(int).to_numpy()
        if len(np.unique(truth)) < 2:
            continue
        ap_deltas.append(
            average_precision_score(truth, boot["probability"])
            - average_precision_score(truth, boot["baseline"])
        )
        brier_deltas.append(
            brier_score_loss(truth, boot["probability"])
            - brier_score_loss(truth, boot["baseline"])
        )
    def interval(values: list[float]) -> list[float | None]:
        return [_number(np.quantile(values, 0.025)), _number(np.quantile(values, 0.975))] if values else [None, None]
    return {
        "requested_samples": samples,
        "successful_samples": len(ap_deltas),
        "average_precision_delta_95_interval": interval(ap_deltas),
        "brier_delta_95_interval": interval(brier_deltas),
    }


def _dominant_arsenal(rows: pd.DataFrame) -> pd.Series:
    columns = ["fastball_pitches", "breaking_pitches", "offspeed_pitches"]
    numeric = rows[columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    labels = np.array(["Fastball", "Breaking", "Offspeed"])
    total = numeric.sum(axis=1).to_numpy()
    dominant = labels[np.argmax(numeric.to_numpy(), axis=1)]
    return pd.Series(np.where(total > 0, dominant, "Unknown"), index=rows.index)


def _subgroup_metrics(rows: pd.DataFrame, target: str, probabilities: np.ndarray) -> dict[str, Any]:
    working = rows.copy()
    working["probability"] = probabilities
    working["dominant_arsenal"] = _dominant_arsenal(working)
    output: dict[str, Any] = {}
    for arsenal, subset in working.groupby("dominant_arsenal"):
        output[str(arsenal)] = _metrics(subset[target], subset["probability"].to_numpy())
    return output


def _excess_recovery_diagnostic(rows: pd.DataFrame, probabilities: np.ndarray) -> dict[str, Any] | None:
    values = pd.to_numeric(rows["excess_recovery"], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(values) & np.isfinite(probabilities)
    if valid.sum() < 20:
        return None
    valid_values = values[valid]
    valid_probability = probabilities[valid]
    lower = float(np.quantile(valid_probability, 0.20))
    upper = float(np.quantile(valid_probability, 0.80))
    correlation = np.corrcoef(valid_probability, valid_values)[0, 1]
    return {
        "rows": int(valid.sum()),
        "probability_excess_recovery_correlation": _number(correlation),
        "bottom_probability_quintile_mean_excess_recovery": _number(valid_values[valid_probability <= lower].mean()),
        "top_probability_quintile_mean_excess_recovery": _number(valid_values[valid_probability >= upper].mean()),
        "note": "Excess recovery subtracts the frozen 2025 role-specific mean reversion after a process collapse.",
    }


def _feature_importance(model: CalibratedModel, features: list[str], model_type: str) -> list[dict[str, Any]]:
    if model_type == "logistic":
        classifier = model.estimator.named_steps["logisticregression"]
        values = np.abs(classifier.coef_[0])
    else:
        values = np.asarray(model.estimator.feature_importances_, dtype=float)
    order = np.argsort(values)[::-1][:12]
    return [{"feature": features[index], "importance": _number(values[index])} for index in order]


def _passes_release_gate(model: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    ap_gain = float(model["average_precision"] or 0.0) - float(baseline["average_precision"] or 0.0)
    brier_ok = model["brier"] is not None and baseline["brier"] is not None and model["brier"] <= baseline["brier"]
    log_ok = model["log_loss"] is not None and baseline["log_loss"] is not None and model["log_loss"] <= baseline["log_loss"]
    passed = ap_gain >= 0.01 and brier_ok and log_ok
    return {
        "average_precision_gain": _number(ap_gain),
        "minimum_average_precision_gain": 0.01,
        "brier_not_worse": bool(brier_ok),
        "log_loss_not_worse": bool(log_ok),
        "passed": bool(passed),
    }


def refresh_performance_state_forecasts(
    data_dir: Path | None = None,
    development_year: int = DEVELOPMENT_YEAR,
    test_year: int = TEST_YEAR,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    panel = _load_panel(root, (development_year, test_year))
    output = panel[KEYS].copy()
    for target in TARGETS:
        output[f"{target}_probability"] = np.nan
        output[f"{target}_alert"] = False

    slice8: dict[str, Any] = {
        "version": FORECAST_MODEL_VERSION,
        "status": "research_only",
        "information_time": {
            "collapse": "Before the target appearance; filtered/current-appearance states are prohibited.",
            "rebound": "After a completed process-collapse appearance and before the next same-role appearance.",
        },
        "feature_layers": FEATURE_LAYERS,
        "roles": {},
    }
    slice9: dict[str, Any] = {
        "version": VALIDATION_VERSION,
        "status": "research_only",
        "evaluation_status": "test_with_documented_slice3a_amendment",
        "prospective_untouched_year": 2027,
        "roles": {},
    }

    for role in ROLES:
        slice8["roles"][role] = {}
        slice9["roles"][role] = {}
        for target in TARGETS:
            development = _eligible_rows(panel[panel["year"].eq(development_year)], role, target)
            external = _eligible_rows(panel[panel["year"].eq(test_year)], role, target)
            splits = _chronological_split(development)
            ablations: dict[str, Any] = {}
            fitted_layers: dict[str, tuple[CalibratedModel, list[str]]] = {}
            for layer in ("A_baseline", "B_latent_state", "C_regime_prior", "D_gas_har", "E_evt"):
                features = _observed_features(splits["train"], _cumulative_features(layer))
                fitted = _fit_calibrated(_new_logistic(), splits["train"], splits["calibration"], features, target)
                validation_probability = fitted.predict(splits["validation"], features)
                ablations[layer] = _metrics(splits["validation"][target], validation_probability)
                fitted_layers[layer] = (fitted, features)
            selected_layer = max(
                ablations,
                key=lambda name: (
                    float(ablations[name]["average_precision"] or -1.0),
                    -float(ablations[name]["brier"] or 1.0),
                ),
            )
            selected_model, selected_features = fitted_layers[selected_layer]
            challenger_features = _observed_features(
                splits["train"], _cumulative_features("F_challengers")
            )
            challenger = _fit_calibrated(
                _new_xgboost(), splits["train"], splits["calibration"], challenger_features, target
            )
            validation_challenger_probability = challenger.predict(splits["validation"], challenger_features)
            validation_challenger = _metrics(splits["validation"][target], validation_challenger_probability)

            calibration_probability = selected_model.predict(splits["calibration"], selected_features)
            alert_threshold = _fixed_false_alert_threshold(
                splits["calibration"][target].astype(int).to_numpy(), calibration_probability
            )
            for year in (development_year, test_year):
                eligible = _eligible_rows(panel[panel["year"].eq(year)], role, target)
                probability = selected_model.predict(eligible, selected_features)
                key_index = pd.MultiIndex.from_frame(output[KEYS])
                eligible_index = pd.MultiIndex.from_frame(eligible[KEYS])
                positions = key_index.get_indexer(eligible_index)
                if np.any(positions < 0):
                    raise RuntimeError(f"Forecast output key mismatch for {year} {role} {target}.")
                output.loc[positions, f"{target}_probability"] = probability
                output.loc[positions, f"{target}_alert"] = probability >= alert_threshold

            external_probability = selected_model.predict(external, selected_features)
            challenger_external_probability = challenger.predict(external, challenger_features)
            baseline_probability = np.full(len(external), selected_model.prevalence)
            primary_metrics = _metrics(external[target], external_probability)
            baseline_metrics = _metrics(external[target], baseline_probability)
            challenger_metrics = _metrics(external[target], challenger_external_probability)
            alert = _alert_metrics(external[target].astype(int).to_numpy(), external_probability, alert_threshold)
            gate = _passes_release_gate(primary_metrics, baseline_metrics)
            slice8["roles"][role][target] = {
                "eligible_development_rows": int(len(development)),
                "split_rows": {name: int(len(rows)) for name, rows in splits.items()},
                "selected_primary_layer": selected_layer,
                "selected_features": selected_features,
                "validation_ablations": ablations,
                "validation_xgboost_challenger": validation_challenger,
                "primary_feature_importance": _feature_importance(selected_model, selected_features, "logistic"),
                "xgboost_feature_importance": _feature_importance(challenger, challenger_features, "xgboost"),
                "fixed_false_alert_threshold": _number(alert_threshold),
            }
            slice9["roles"][role][target] = {
                "external_rows": int(len(external)),
                "primary": primary_metrics,
                "development_prevalence_baseline": baseline_metrics,
                "xgboost_challenger": challenger_metrics,
                "fixed_false_alert_metrics": alert,
                "pitcher_cluster_bootstrap": _bootstrap_delta(
                    external, target, external_probability, baseline_probability
                ),
                "dominant_arsenal_subgroups": _subgroup_metrics(external, target, external_probability),
                "excess_recovery_diagnostic": (
                    _excess_recovery_diagnostic(external, external_probability)
                    if target in REBOUND_TARGETS else None
                ),
                "release_gate": gate,
            }

    for year in (development_year, test_year):
        _write_parquet_atomic(output[output["year"].eq(year)].copy(), forecast_state_path(year, root))
    source_modified_at = {
        str(year): {
            "filtered": int(filtered_state_path(year, root).stat().st_mtime_ns),
            "advanced": int(advanced_state_path(year, root).stat().st_mtime_ns),
            "tail": int(tail_state_path(year, root).stat().st_mtime_ns),
        }
        for year in (development_year, test_year)
    }
    all_gates = [
        result["release_gate"]["passed"]
        for role_results in slice9["roles"].values()
        for result in role_results.values()
    ]
    audit = {
        "model_version": FORECAST_MODEL_VERSION,
        "validation_version": VALIDATION_VERSION,
        "status": "research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "development_year": development_year,
        "test_year": test_year,
        "evaluation_status": "test_with_documented_slice3a_amendment",
        "prospective_untouched_year": 2027,
        "source_state_model_version": STATE_MODEL_VERSION,
        "source_tail_model_version": TAIL_MODEL_VERSION,
        "freeze_audit": {
            "model_selection_year": development_year,
            "probability_calibration_year": development_year,
            "alert_threshold_year": development_year,
            "test_year_used_for_selection_or_calibration": False,
        },
        "source_modified_at": source_modified_at,
        "data_as_of": {
            str(year): str(panel.loc[panel["year"].eq(year), "game_date"].max())[:10]
            for year in (development_year, test_year)
        },
        "slice8": slice8,
        "slice9": slice9,
        "prospective_release_decision": "eligible_for_2027_shadow" if all(all_gates) else "keep_research_only",
        "warnings": [
            "Forecasts estimate performance collapse or recovery, not fatigue, injury, health or medical risk.",
            "2026 is an external diagnostic with a documented Slice 3A amendment; 2027 remains the untouched prospective season.",
            "Targets remain separate; no composite risk score is published.",
            "RP CAViaR and GJR-GARCH enter only the challenger layer because their earlier validation gates failed.",
        ],
    }
    _write_json_atomic(audit, forecast_audit_path(root))
    _cached_forecast_audit.cache_clear()
    return audit


@lru_cache(maxsize=2)
def _cached_forecast_audit(path_value: str, modified_at: int) -> dict[str, Any]:
    del modified_at
    return json.loads(Path(path_value).read_text(encoding="utf-8"))


def get_performance_state_forecast_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = forecast_audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slices 8-9 have not been built.")
    payload = _cached_forecast_audit(str(path.resolve()), path.stat().st_mtime_ns).copy()
    stale_years: list[int] = []
    for year_text, sources in payload.get("source_modified_at", {}).items():
        year = int(year_text)
        current = {
            "filtered": filtered_state_path(year, root),
            "advanced": advanced_state_path(year, root),
            "tail": tail_state_path(year, root),
        }
        if any(path_value.exists() and path_value.stat().st_mtime_ns > int(sources[name]) for name, path_value in current.items()):
            stale_years.append(year)
    payload["dataset_status"] = "stale" if stale_years else "current"
    if stale_years:
        payload["warnings"] = list(payload.get("warnings", [])) + [
            f"Frozen source artifacts changed after forecast build for: {', '.join(map(str, stale_years))}."
        ]
    return payload


def get_performance_state_leaderboard(
    year: int = TEST_YEAR,
    role: str = "SP",
    target: str = "process_collapse",
    minimum_forecasts: int = 1,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    role_value = str(role).upper()
    target_value = str(target).lower()
    if role_value not in ROLES:
        raise ValueError("role must be SP or RP.")
    if target_value not in TARGETS:
        raise ValueError(f"target must be one of: {', '.join(TARGETS)}.")
    if minimum_forecasts < 1:
        raise ValueError("minimum_forecasts must be at least 1.")
    forecast_path = forecast_state_path(year, root)
    state_path = filtered_state_path(year, root)
    if not forecast_path.exists() or not state_path.exists():
        raise FileNotFoundError(f"Performance State forecast artifact not found for {year}.")
    probability_column = f"{target_value}_probability"
    with duckdb.connect() as connection:
        frame = connection.execute(
            f"""
            SELECT
                f.pitcher_id,
                s.pitcher_name,
                s.team,
                f.role,
                f.game_pk,
                f.game_date,
                f.{probability_column} AS probability,
                s.{target_value} AS actual
            FROM read_parquet(?) f
            INNER JOIN read_parquet(?) s
                USING (year, pitcher_id, role, game_pk, game_date)
            WHERE f.role = ? AND f.{probability_column} IS NOT NULL
            ORDER BY f.pitcher_id, f.game_date, f.game_pk
            """,
            [str(forecast_path), str(state_path), role_value],
        ).fetchdf()
    rows: list[dict[str, Any]] = []
    for pitcher_id, pitcher_rows in frame.groupby("pitcher_id", sort=False):
        if len(pitcher_rows) < int(minimum_forecasts):
            continue
        latest = pitcher_rows.iloc[-1]
        rows.append({
            "pitcher_id": int(pitcher_id),
            "pitcher_name": str(latest["pitcher_name"]),
            "team": str(latest["team"]) if pd.notna(latest["team"]) else None,
            "role": role_value,
            "appearances": int(len(pitcher_rows)),
            "eligible_forecasts": int(pitcher_rows["probability"].notna().sum()),
            "latest_game_date": pd.Timestamp(latest["game_date"]).strftime("%Y-%m-%d"),
            "latest_probability": float(latest["probability"]),
            "season_mean_probability": float(pitcher_rows["probability"].mean()),
            "actual_events": int(pitcher_rows["actual"].fillna(False).astype(bool).sum()),
            "actual_rate": float(pitcher_rows["actual"].fillna(False).astype(bool).mean()),
            "latest_actual": bool(latest["actual"]),
        })
    rows.sort(key=lambda item: (-item["latest_probability"], -item["eligible_forecasts"], item["pitcher_name"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    audit = get_performance_state_forecast_audit(root)
    validation = audit["slice9"]["roles"][role_value][target_value]
    model = audit["slice8"]["roles"][role_value][target_value]
    return {
        "year": int(year),
        "role": role_value,
        "target": target_value,
        "target_label": TARGET_LABELS[target_value],
        "model_version": FORECAST_MODEL_VERSION,
        "status": "research_only",
        "data_as_of": audit.get("data_as_of", {}).get(str(year)),
        "evaluation_status": audit.get("evaluation_status", "research_only"),
        "selected_primary_layer": model["selected_primary_layer"],
        "model": model,
        "validation": validation,
        "rows": rows,
        "warnings": [
            "This is a retrospective ranking of pre-appearance forecasts for completed appearances, not a next-game forecast.",
            "A high probability estimates performance-event risk or recovery likelihood; it is not fatigue, injury or health risk.",
            "Targets and SP/RP models are not comparable as one combined score.",
        ],
    }


def refresh_performance_state_shadow(
    data_dir: Path | None = None,
    evaluation_year: int = TEST_YEAR,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    forecasts = forecast_state_path(evaluation_year, root)
    states = filtered_state_path(evaluation_year, root)
    if not forecasts.exists() or not states.exists():
        raise FileNotFoundError(f"Performance State forecast artifact not found for {evaluation_year}.")
    with duckdb.connect() as connection:
        panel = connection.execute(
            """
            SELECT
                f.year, f.pitcher_id, f.role, f.game_pk, f.game_date,
                s.pitcher_name, s.team,
                s.process_collapse, s.result_collapse,
                s.return_to_baseline, s.strong_rebound,
                f.process_collapse_probability, f.process_collapse_alert,
                f.result_collapse_probability, f.result_collapse_alert,
                f.return_to_baseline_probability, f.return_to_baseline_alert,
                f.strong_rebound_probability, f.strong_rebound_alert
            FROM read_parquet(?) f
            INNER JOIN read_parquet(?) s
                USING (year, pitcher_id, role, game_pk, game_date)
            ORDER BY f.game_date, f.game_pk, f.pitcher_id, f.role
            """,
            [str(forecasts), str(states)],
        ).fetchdf()
    recorded_at = datetime.now(timezone.utc).isoformat()
    candidates: list[pd.DataFrame] = []
    for target in TARGETS:
        probability_column = f"{target}_probability"
        alert_column = f"{target}_alert"
        rows = panel[panel[probability_column].notna()].copy()
        rows["target"] = target
        rows["probability"] = pd.to_numeric(rows[probability_column], errors="coerce")
        rows["alert"] = rows[alert_column].fillna(False).astype(bool)
        rows["actual"] = rows[target].fillna(False).astype(bool)
        rows["outcome"] = np.select(
            [rows["actual"] & rows["alert"], rows["actual"], rows["alert"]],
            ["hit", "miss", "false_alert"],
            default="correct_negative",
        )
        rows["recorded_at"] = recorded_at
        candidates.append(rows[[
            "year", "pitcher_id", "pitcher_name", "team", "role", "game_pk", "game_date",
            "target", "probability", "alert", "actual", "outcome", "recorded_at",
        ]])
    candidate = pd.concat(candidates, ignore_index=True)
    keys = ["year", "pitcher_id", "role", "game_pk", "target"]
    ledger_path = shadow_ledger_path(root)
    conflicts = 0
    appended = len(candidate)
    observation_mode = "historical_backfill"
    if ledger_path.exists():
        with duckdb.connect() as connection:
            existing = connection.execute("SELECT * FROM read_parquet(?)", [str(ledger_path)]).fetchdf()
        existing_keys = pd.MultiIndex.from_frame(existing[keys])
        candidate_keys = pd.MultiIndex.from_frame(candidate[keys])
        matched = candidate_keys.isin(existing_keys)
        if matched.any():
            comparison = candidate.loc[matched, keys + ["probability"]].merge(
                existing[keys + ["probability"]], on=keys, suffixes=("_new", "_frozen"), validate="one_to_one"
            )
            conflicts = int(
                (comparison["probability_new"] - comparison["probability_frozen"]).abs().gt(1e-9).sum()
            )
        additions = candidate.loc[~matched].copy()
        additions["recorded_at"] = recorded_at
        additions["observation_mode"] = "prospective_append"
        existing_columns = list(existing.columns)
        if "observation_mode" not in existing_columns:
            existing["observation_mode"] = "historical_backfill"
        ledger = pd.concat([existing, additions], ignore_index=True)[existing.columns]
        appended = int(len(additions))
        observation_mode = "prospective_append" if appended else "no_new_rows"
    else:
        candidate["observation_mode"] = "historical_backfill"
        ledger = candidate
    ledger = ledger.sort_values(keys, kind="stable").reset_index(drop=True)
    if ledger.duplicated(keys).any():
        raise RuntimeError("Shadow ledger contains duplicate forecast keys.")
    _write_parquet_atomic(ledger, ledger_path)

    monitoring: dict[str, Any] = {}
    for role in ROLES:
        monitoring[role] = {}
        for target in TARGETS:
            rows = ledger[ledger["role"].eq(role) & ledger["target"].eq(target)].copy()
            metrics = _metrics(rows["actual"], rows["probability"].to_numpy(dtype=float))
            alerts = rows["alert"].astype(bool)
            actual = rows["actual"].astype(bool)
            monitoring[role][target] = {
                "rows": int(len(rows)),
                "pitchers": int(rows["pitcher_id"].nunique()),
                "data_as_of": pd.to_datetime(rows["game_date"], errors="coerce").max().strftime("%Y-%m-%d") if len(rows) else None,
                "metrics": metrics,
                "confusion": {
                    "hits": int((alerts & actual).sum()),
                    "misses": int((~alerts & actual).sum()),
                    "false_alerts": int((alerts & ~actual).sum()),
                    "correct_negatives": int((~alerts & ~actual).sum()),
                },
            }
    prospective_rows = int(ledger["observation_mode"].eq("prospective_append").sum())
    audit = {
        "version": SHADOW_MODEL_VERSION,
        "status": "research_only",
        "generated_at": recorded_at,
        "evaluation_year": int(evaluation_year),
        "source_forecast_model_version": FORECAST_MODEL_VERSION,
        "source_modified_at": {
            "forecast": int(forecasts.stat().st_mtime_ns),
            "filtered": int(states.stat().st_mtime_ns),
        },
        "observation_mode": observation_mode,
        "ledger_rows": int(len(ledger)),
        "appended_rows": appended,
        "probability_conflicts_preserved": conflicts,
        "prospective_rows": prospective_rows,
        "monitoring": monitoring,
        "integration_gate": {
            "eligible": False,
            "required_untouched_year": 2027,
            "minimum_prospective_rows_per_role_target": 250,
            "reason": "2026 rows are historical backfill. Player-page and next-start integration require untouched 2027 prospective monitoring.",
        },
        "warnings": [
            "Existing ledger probabilities are immutable; rebuild conflicts are counted and the frozen values are preserved.",
            "Historical backfill evaluates the monitoring workflow but is not prospective evidence.",
            "This monitor concerns performance events, not fatigue, health, injury or medical risk.",
        ],
    }
    _write_json_atomic(audit, shadow_audit_path(root))
    _cached_shadow_audit.cache_clear()
    return audit


@lru_cache(maxsize=2)
def _cached_shadow_audit(path_value: str, modified_at: int) -> dict[str, Any]:
    del modified_at
    return json.loads(Path(path_value).read_text(encoding="utf-8"))


def get_performance_state_shadow_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = shadow_audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slice 11 has not been built.")
    payload = _cached_shadow_audit(str(path.resolve()), path.stat().st_mtime_ns).copy()
    sources = payload.get("source_modified_at", {})
    current = {
        "forecast": forecast_state_path(int(payload["evaluation_year"]), root),
        "filtered": filtered_state_path(int(payload["evaluation_year"]), root),
    }
    stale = any(
        source.exists() and source.stat().st_mtime_ns > int(sources.get(name, 0))
        for name, source in current.items()
    )
    payload["dataset_status"] = "stale" if stale else "current"
    if stale:
        payload["warnings"] = list(payload.get("warnings", [])) + [
            "Forecast or filtered-state artifacts changed after the shadow ledger refresh."
        ]
    return payload
