from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import genpareto, kstest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss

from app.core.config import settings
from app.services.performance_state_advanced_service import (
    VOLATILITY_SIGNAL,
    _binary_alert_metrics,
    _bootstrap_gpd,
    _caviar_forecasts,
    _decluster_exceedances,
    _fit_caviar,
    _fit_gpd,
    _fit_regime_models,
    _fit_volatility_models,
    _gpd_candidate_audit,
    _kupiec_test,
    _quantile_loss,
    _tail_probability_and_severity,
)
from app.services.performance_state_forecast_service import (
    _chronological_split,
    _cumulative_features,
    _fit_calibrated,
    _fixed_false_alert_threshold,
    _metrics,
    _new_logistic,
    _observed_features,
    _passes_release_gate,
)
from app.services.performance_state_service import (
    ROLES,
    _apply_state_space,
    _fit_state_parameters,
    _number,
    _state_space_audit,
    _write_json_atomic,
    _write_parquet_atomic,
)
from app.services.performance_state_v2_service import (
    TARGETS,
    YEARS,
    _prepare_fold,
    _target_rows,
    v2_audit_path,
    v2_fold_predictions_path,
    v2_warehouse_path,
)


SLICE14_VERSION = "performance_state_multiseason_slice14_v1"
SLICE14A_VERSION = "performance_state_cluster_calibration_audit_v1"
SLICE14B_VERSION = "performance_state_multiseason_advanced_v1"
TRAIN_YEARS = (2023, 2024, 2025)
TEST_YEAR = 2026
BOOTSTRAP_SAMPLES = 100


def slice14_audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice14.json"


def slice14_state_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"performance_state_v2_slice14_states_{year}.parquet"


def slice14_prediction_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice14_predictions_2026.parquet"


def _load_warehouses(root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year in YEARS:
        path = v2_warehouse_path(year, root)
        if not path.exists():
            raise FileNotFoundError(f"Performance State v2 warehouse not found: {path}")
        with duckdb.connect() as connection:
            frame = connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchdf()
        frame["year"] = int(year)
        frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).sort_values(
        ["pitcher_id", "role", "game_date", "game_pk"], kind="stable"
    ).reset_index(drop=True)


def _calibration(truth: np.ndarray, probability: np.ndarray, weights: np.ndarray | None = None) -> dict[str, Any]:
    y = np.asarray(truth, dtype=int)
    p = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
    if len(y) == 0 or len(np.unique(y)) < 2:
        return {"intercept": None, "slope": None, "ece": None}
    logits = np.log(p / (1.0 - p)).reshape(-1, 1)
    model = LogisticRegression(C=1e6, max_iter=1000).fit(logits, y, sample_weight=weights)
    quantiles = pd.qcut(pd.Series(p), q=min(10, len(p)), duplicates="drop")
    total_weight = float(np.sum(weights)) if weights is not None else float(len(p))
    ece = 0.0
    for _, positions in pd.Series(np.arange(len(p))).groupby(quantiles, observed=True):
        indices = positions.to_numpy(dtype=int)
        group_weights = weights[indices] if weights is not None else None
        group_weight = float(np.sum(group_weights)) if group_weights is not None else float(len(indices))
        predicted = float(np.average(p[indices], weights=group_weights))
        observed = float(np.average(y[indices], weights=group_weights))
        ece += group_weight / max(total_weight, 1.0) * abs(predicted - observed)
    return {
        "intercept": _number(model.intercept_[0]),
        "slope": _number(model.coef_[0, 0]),
        "ece": _number(ece),
    }


def _cluster_bootstrap(
    rows: pd.DataFrame,
    probability: np.ndarray,
    baseline_probability: float,
    samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    working = rows[["pitcher_id", "actual"]].copy().reset_index(drop=True)
    working["probability"] = np.asarray(probability, dtype=float)
    truth = working["actual"].astype(int).to_numpy()
    baseline = np.full(len(working), baseline_probability, dtype=float)
    pitchers = working["pitcher_id"].dropna().unique()
    rng = np.random.default_rng(20261007)
    values: dict[str, list[float]] = {name: [] for name in ("ap_delta", "brier_delta", "log_loss_delta", "slope", "intercept", "ece")}
    pitcher_values = working["pitcher_id"].to_numpy()
    for _ in range(samples):
        selected = rng.choice(pitchers, size=len(pitchers), replace=True)
        counts = pd.Series(selected).value_counts()
        weights = pd.Series(pitcher_values).map(counts).fillna(0).to_numpy(dtype=float)
        included = weights > 0
        sampled_truth = truth[included]
        if len(np.unique(sampled_truth)) < 2:
            continue
        sampled_probability = working.loc[included, "probability"].to_numpy(dtype=float)
        sampled_baseline = baseline[included]
        sampled_weights = weights[included]
        values["ap_delta"].append(
            average_precision_score(sampled_truth, sampled_probability, sample_weight=sampled_weights)
            - average_precision_score(sampled_truth, sampled_baseline, sample_weight=sampled_weights)
        )
        values["brier_delta"].append(
            brier_score_loss(sampled_truth, sampled_probability, sample_weight=sampled_weights)
            - brier_score_loss(sampled_truth, sampled_baseline, sample_weight=sampled_weights)
        )
        values["log_loss_delta"].append(
            log_loss(sampled_truth, sampled_probability, sample_weight=sampled_weights, labels=[0, 1])
            - log_loss(sampled_truth, sampled_baseline, sample_weight=sampled_weights, labels=[0, 1])
        )
        calibration = _calibration(sampled_truth, sampled_probability, sampled_weights)
        for key in ("slope", "intercept", "ece"):
            if calibration[key] is not None:
                values[key].append(float(calibration[key]))

    def interval(name: str) -> list[float | None]:
        series = values[name]
        return [_number(np.quantile(series, 0.025)), _number(np.quantile(series, 0.975))] if series else [None, None]

    return {
        "requested_samples": samples,
        "successful_samples": len(values["ap_delta"]),
        "average_precision_delta_95_interval": interval("ap_delta"),
        "brier_delta_95_interval": interval("brier_delta"),
        "log_loss_delta_95_interval": interval("log_loss_delta"),
        "calibration_slope_95_interval": interval("slope"),
        "calibration_intercept_95_interval": interval("intercept"),
        "ece_95_interval": interval("ece"),
    }


def _slice14a(panel: pd.DataFrame, root: Path) -> dict[str, Any]:
    fold_results: list[dict[str, Any]] = []
    for train_years, test_year in (((2023,), 2024), ((2023, 2024), 2025), (TRAIN_YEARS, TEST_YEAR)):
        prepared, _ = _prepare_fold(panel, train_years, test_year)
        clean = prepared[prepared["model_eligible"]]
        with duckdb.connect() as connection:
            predictions = connection.execute(
                "SELECT * FROM read_parquet(?) WHERE cohort = 'clean'", [str(v2_fold_predictions_path(test_year, root))]
            ).fetchdf()
        fold: dict[str, Any] = {"train_years": list(train_years), "test_year": test_year, "roles": {}}
        for role in ROLES:
            fold["roles"][role] = {}
            role_rows = clean[clean["role"].eq(role)]
            for target in TARGETS:
                eligible = _target_rows(role_rows, target)
                train = eligible[eligible["year"].isin(train_years)]
                train = train[train[[
                    "lag_process_score", "lag_result_score", "process_ma5", "process_ewm",
                    "lag_process_volatility", "calendar_days_since_prior", "workload_pitches_7d",
                    "workload_pitches_28d", "previous_appearance_pitches",
                ]].notna().sum(axis=1).ge(2)]
                test_predictions = predictions[
                    predictions["role"].eq(role) & predictions["target"].eq(target)
                ].copy()
                probability = pd.to_numeric(test_predictions["probability"], errors="coerce").to_numpy(dtype=float)
                truth = test_predictions["actual"].astype(int).to_numpy()
                baseline_probability = float(train[target].mean()) if len(train) else 0.5
                baseline = np.full(len(truth), baseline_probability)
                model_metrics = _metrics(truth, probability)
                baseline_metrics = _metrics(truth, baseline)
                bootstrap = _cluster_bootstrap(test_predictions, probability, baseline_probability)
                ap_interval = bootstrap["average_precision_delta_95_interval"]
                brier_interval = bootstrap["brier_delta_95_interval"]
                evidence = (
                    "supported"
                    if ap_interval[0] is not None and ap_interval[0] > 0 and brier_interval[1] is not None and brier_interval[1] <= 0
                    else "ranking_only_or_uncertain"
                )
                fold["roles"][role][target] = {
                    "model": model_metrics,
                    "train_prevalence_baseline": baseline_metrics,
                    "calibration": _calibration(truth, probability),
                    "pitcher_cluster_bootstrap": bootstrap,
                    "evidence_status": evidence,
                }
        fold_results.append(fold)
    return {
        "version": SLICE14A_VERSION,
        "bootstrap_unit": "pitcher_id",
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "folds": fold_results,
        "interpretation": {
            "supported": "The 95% pitcher-cluster interval has positive AP gain and non-worse Brier error.",
            "ranking_only_or_uncertain": "Ranking may improve, but clustered uncertainty or probability error does not support promotion.",
        },
    }


def _restore_year(frame: pd.DataFrame, source: pd.DataFrame) -> pd.DataFrame:
    mapping = source[["pitcher_id", "role", "game_pk", "year"]].rename(columns={"year": "original_year"})
    output = frame.drop(columns=["year"]).merge(
        mapping, on=["pitcher_id", "role", "game_pk"], how="left", validate="one_to_one"
    )
    return output.rename(columns={"original_year": "year"})


def _add_advanced_history(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.sort_values(["pitcher_id", "role", "game_date", "game_pk"], kind="stable").copy()
    groups = output.groupby(["pitcher_id", "role"], sort=False)
    output["stuff_state_change"] = groups["stuff_state_filtered"].diff()
    output["stuff_innovation_volatility5"] = groups[VOLATILITY_SIGNAL].transform(
        lambda values: values.rolling(5, min_periods=3).std()
    )
    squared = pd.to_numeric(output[VOLATILITY_SIGNAL], errors="coerce").pow(2)
    output["lag_innovation_squared"] = groups[VOLATILITY_SIGNAL].shift(1).pow(2)
    output["innovation_variance5"] = squared.groupby(
        [output["pitcher_id"], output["role"]]
    ).transform(lambda values: values.shift(1).rolling(5, min_periods=2).mean())
    output["innovation_variance15"] = squared.groupby(
        [output["pitcher_id"], output["role"]]
    ).transform(lambda values: values.shift(1).rolling(15, min_periods=3).mean())
    return output.reset_index(drop=True)


def _fit_tail(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    output = panel[["year", "pitcher_id", "role", "game_pk", "game_date"]].copy()
    for column in ("evt_extreme_probability", "evt_expected_loss_severity", "caviar_var95"):
        output[column] = np.nan
    output["evt_tail_supported"] = False
    output["extreme_innovation"] = False
    audit: dict[str, Any] = {"roles": {}}
    for role in ROLES:
        rows = panel[panel["role"].eq(role)].copy().reset_index()
        development = rows[rows["year"].isin(TRAIN_YEARS)].copy()
        cutoff = development["game_date"].quantile(0.80)
        fit_rows = development[development["game_date"].le(cutoff)]
        validation_rows = development[development["game_date"].gt(cutoff)]
        candidates = [
            _gpd_candidate_audit(fit_rows, validation_rows, quantile, run_length)
            for quantile in (0.90, 0.925, 0.95)
            for run_length in (0, 1, 2)
        ]
        eligible = [candidate for candidate in candidates if candidate["eligible"]]
        if not eligible:
            audit["roles"][role] = {"status": "insufficient_tail_clusters", "pot_candidates": candidates}
            continue
        selected = min(eligible, key=lambda candidate: float(candidate["validation_score"]))
        losses = pd.to_numeric(development["standardized_loss"], errors="coerce").dropna().to_numpy()
        threshold = float(np.quantile(losses, float(selected["threshold_quantile"])))
        run_length = int(selected["decluster_run_length"])
        excesses = _decluster_exceedances(development, threshold, run_length)
        shape, scale = _fit_gpd(excesses)
        exceedance_rate = float(np.mean(losses > threshold))
        raw_errors = pd.to_numeric(development[VOLATILITY_SIGNAL], errors="coerce").dropna().to_numpy()
        raw_extreme_threshold = float(-np.quantile(raw_errors, 0.05))
        probabilities, severities, supported = _tail_probability_and_severity(
            rows, losses, raw_extreme_threshold, threshold, exceedance_rate, shape, scale
        )
        caviar_candidates: dict[str, dict[str, Any]] = {}
        for model_type in ("sav", "asymmetric_slope"):
            fitted = _fit_caviar(fit_rows.reset_index(drop=True), model_type)
            validation_loss = -pd.to_numeric(validation_rows[VOLATILITY_SIGNAL], errors="coerce").to_numpy(dtype=float)
            validation_forecast = _caviar_forecasts(
                validation_rows.reset_index(drop=True), fitted["parameters"], model_type, fitted["initial_quantile"]
            )
            fitted["validation_quantile_loss"] = _quantile_loss(validation_loss, validation_forecast)
            caviar_candidates[model_type] = fitted
        selected_type = min(caviar_candidates, key=lambda name: caviar_candidates[name]["validation_quantile_loss"])
        final_caviar = _fit_caviar(development.reset_index(drop=True), selected_type)
        caviar = _caviar_forecasts(rows, final_caviar["parameters"], selected_type, final_caviar["initial_quantile"])
        errors = pd.to_numeric(rows[VOLATILITY_SIGNAL], errors="coerce").to_numpy(dtype=float)
        extreme = errors <= -raw_extreme_threshold
        output.loc[rows["index"], "evt_extreme_probability"] = probabilities
        output.loc[rows["index"], "evt_expected_loss_severity"] = severities
        output.loc[rows["index"], "evt_tail_supported"] = supported
        output.loc[rows["index"], "caviar_var95"] = caviar
        output.loc[rows["index"], "extreme_innovation"] = extreme
        test_mask = rows["year"].eq(TEST_YEAR).to_numpy()
        test_loss = -errors[test_mask]
        test_extreme = extreme[test_mask]
        evt_threshold = float(np.nanquantile(probabilities[rows["year"].isin(TRAIN_YEARS).to_numpy()], 0.90))
        ks = kstest(excesses, lambda value: genpareto.cdf(value, c=shape, loc=0.0, scale=scale))
        audit["roles"][role] = {
            "status": "fit",
            "selected_threshold_quantile": selected["threshold_quantile"],
            "selected_decluster_run_length": run_length,
            "development_clusters": int(len(excesses)),
            "gpd_shape": _number(shape),
            "gpd_scale": _number(scale),
            "gpd_ks_p_value": _number(ks.pvalue),
            "bootstrap": _bootstrap_gpd(excesses),
            "test_evt_supported_rate": _number(supported[test_mask].mean()),
            "test_evt_alert_metrics": _binary_alert_metrics(test_extreme, probabilities[test_mask], evt_threshold),
            "selected_caviar": selected_type,
            "test_caviar_quantile_loss": _number(_quantile_loss(test_loss, caviar[test_mask]), 6),
            "test_caviar_kupiec": _kupiec_test(test_loss > caviar[test_mask]),
        }
    return output, audit


def _eligible_target(panel: pd.DataFrame, role: str, target: str) -> pd.DataFrame:
    rows = panel[panel["role"].eq(role) & panel[target].notna()].copy()
    return _target_rows(rows, target).sort_values(["game_date", "game_pk", "pitcher_id"], kind="stable")


def _fit_forecasts(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    predictions: list[pd.DataFrame] = []
    audit: dict[str, Any] = {"roles": {}}
    for role in ROLES:
        audit["roles"][role] = {}
        for target in TARGETS:
            development = _eligible_target(panel[panel["year"].isin(TRAIN_YEARS)], role, target)
            external = _eligible_target(panel[panel["year"].eq(TEST_YEAR)], role, target)
            splits = _chronological_split(development)
            if any(len(split) == 0 or split[target].nunique() < 2 for split in splits.values()):
                audit["roles"][role][target] = {"status": "insufficient_classes", "rows": int(len(external))}
                continue
            ablations: dict[str, Any] = {}
            fitted: dict[str, tuple[Any, list[str]]] = {}
            for layer in ("A_baseline", "B_latent_state", "C_regime_prior", "D_gas_har", "E_evt"):
                features = _observed_features(splits["train"], _cumulative_features(layer))
                model = _fit_calibrated(_new_logistic(), splits["train"], splits["calibration"], features, target)
                probability = model.predict(splits["validation"], features)
                ablations[layer] = _metrics(splits["validation"][target], probability)
                fitted[layer] = (model, features)
            selected_layer = max(
                ablations,
                key=lambda name: (float(ablations[name]["average_precision"] or -1.0), -float(ablations[name]["brier"] or 1.0)),
            )
            model, features = fitted[selected_layer]
            probability = model.predict(external, features)
            baseline = np.full(len(external), model.prevalence)
            metrics = _metrics(external[target], probability)
            baseline_metrics = _metrics(external[target], baseline)
            calibration_probability = model.predict(splits["calibration"], features)
            alert_threshold = _fixed_false_alert_threshold(
                splits["calibration"][target].astype(int).to_numpy(), calibration_probability
            )
            result = external[["year", "pitcher_id", "pitcher_name", "team", "role", "game_pk", "game_date"]].copy()
            result["target"] = target
            result["probability"] = probability
            result["actual"] = external[target].astype(bool).to_numpy()
            result["alert"] = probability >= alert_threshold
            predictions.append(result)
            audit["roles"][role][target] = {
                "status": "fit",
                "development_rows": int(len(development)),
                "external_rows": int(len(external)),
                "selected_layer": selected_layer,
                "selected_features": features,
                "validation_ablations": ablations,
                "external": metrics,
                "baseline": baseline_metrics,
                "pitcher_cluster_bootstrap": _cluster_bootstrap(
                    result.rename(columns={"actual": "actual"}), probability, model.prevalence
                ),
                "release_gate": _passes_release_gate(metrics, baseline_metrics),
            }
    return pd.concat(predictions, ignore_index=True), audit


def _slice14b(panel: pd.DataFrame, root: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    prepared, thresholds = _prepare_fold(panel, TRAIN_YEARS, TEST_YEAR)
    clean = prepared[prepared["model_eligible"]].copy().reset_index(drop=True)
    clean["stuff_state"] = clean["mean_stuff_plus_z"]
    clean["command_state"] = clean["mean_location_plus_z"]
    clean["result_state"] = clean["result_score"]
    parameters = _fit_state_parameters(clean[clean["year"].isin(TRAIN_YEARS)])
    filtered = _add_advanced_history(_apply_state_space(clean, parameters))
    state_audit = _state_space_audit(filtered, parameters, TEST_YEAR)

    modeling = filtered.copy()
    modeling.loc[modeling["year"].isin(TRAIN_YEARS), "year"] = 2025
    regime_rows, regime_audit = _fit_regime_models(modeling, 2025, TEST_YEAR)
    volatility_rows, gas_audit, gjr_audit = _fit_volatility_models(modeling, 2025, TEST_YEAR)
    advanced = regime_rows.merge(
        volatility_rows, on=["year", "pitcher_id", "role", "game_pk", "game_date"], how="inner", validate="one_to_one"
    )
    advanced = _restore_year(advanced, filtered)
    enriched = filtered.merge(
        advanced.drop(columns=["year", "game_date"]),
        on=["pitcher_id", "role", "game_pk"], how="left", validate="one_to_one",
    )
    error = pd.to_numeric(enriched[VOLATILITY_SIGNAL], errors="coerce")
    variance = pd.to_numeric(enriched["gas_har_variance_forecast"], errors="coerce")
    enriched["standardized_loss"] = -error / np.sqrt(variance.where(variance.gt(0)))
    enriched["sequence_index"] = enriched.groupby(["pitcher_id", "role"], sort=False).cumcount()
    tail_rows, tail_audit = _fit_tail(enriched)
    enriched = enriched.merge(
        tail_rows.drop(columns=["year", "game_date"]),
        on=["pitcher_id", "role", "game_pk"], how="left", validate="one_to_one",
    )
    predictions, forecast_audit = _fit_forecasts(enriched)
    for year in YEARS:
        _write_parquet_atomic(
            enriched[enriched["year"].eq(year)].copy(), slice14_state_path(year, root), f"performance_state_v2_slice14_states_{year}"
        )
    _write_parquet_atomic(predictions, slice14_prediction_path(root), "performance_state_v2_slice14_predictions_2026")
    for section in (regime_audit, gas_audit, gjr_audit):
        section["development_years"] = list(TRAIN_YEARS)
        section["external_diagnostic_year"] = TEST_YEAR
        section["evaluation_status"] = "multiseason_fit_2023_2025_to_2026_diagnostic"
    return {
        "version": SLICE14B_VERSION,
        "training_years": list(TRAIN_YEARS),
        "diagnostic_year": TEST_YEAR,
        "prospective_untouched_year": 2027,
        "thresholds": thresholds,
        "state_space": state_audit,
        "regime": regime_audit,
        "gas_har": gas_audit,
        "gjr_garch": gjr_audit,
        "tail": tail_audit,
        "forecasts": forecast_audit,
        "warnings": [
            "Historical Plus values use the current frozen retrospective models; this is not pristine upstream Plus-model validation.",
            "2026 is diagnostic-only and 2027 remains untouched.",
            "Models estimate performance states, not fatigue, injury, health or medical outcomes.",
        ],
    }, predictions


def refresh_performance_state_v2_slice14(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    panel = _load_warehouses(root)
    slice14a = _slice14a(panel, root)
    slice14b, predictions = _slice14b(panel, root)
    audit = {
        "version": SLICE14_VERSION,
        "status": "research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_modified_at": {
            "slice11a_13": int(v2_audit_path(root).stat().st_mtime_ns),
            **{str(year): int(v2_warehouse_path(year, root).stat().st_mtime_ns) for year in YEARS},
        },
        "slice14a": slice14a,
        "slice14b": slice14b,
        "prediction_rows": int(len(predictions)),
        "dataset_status": "current",
    }
    _write_json_atomic(audit, slice14_audit_path(root))
    return audit


def get_performance_state_v2_slice14_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = slice14_audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slice 14A/B has not been built.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    stale = v2_audit_path(root).stat().st_mtime_ns > int(payload["source_modified_at"]["slice11a_13"])
    stale |= any(
        v2_warehouse_path(year, root).stat().st_mtime_ns > int(payload["source_modified_at"][str(year)])
        for year in YEARS
    )
    payload["dataset_status"] = "stale" if stale else "current"
    return payload
