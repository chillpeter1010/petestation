from __future__ import annotations

import json
from datetime import datetime, timezone
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

from app.core.config import settings
from app.services.performance_state_service import ROLES, _number, _write_json_atomic, _write_parquet_atomic
from app.services.performance_state_v2_service import TARGETS, YEARS
from app.services.performance_state_v2_slice14_service import (
    _cluster_bootstrap,
    slice14_prediction_path,
    slice14_state_path,
)


SLICE16_VERSION = "performance_state_v2_optimization_slice16_v1"
DEVELOPMENT_YEARS = (2023, 2024)
SELECTION_YEAR = 2025
DIAGNOSTIC_YEAR = 2026

STABLE_FEATURES = [
    "lag_process_score",
    "process_ma5",
    "process_ewm",
    "lag_process_volatility",
]
CONTEXT_FEATURES = STABLE_FEATURES + [
    "calendar_days_since_prior",
    "workload_pitches_7d",
    "workload_pitches_28d",
    "previous_appearance_pitches",
]


def slice16_audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice16.json"


def slice16_prediction_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice16_predictions_2026.parquet"


def _load_states(root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year in YEARS:
        path = slice14_state_path(year, root)
        if not path.exists():
            raise FileNotFoundError(f"Slice 14 state artifact not found: {path}")
        with duckdb.connect() as connection:
            frame = connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchdf()
        frame["year"] = int(year)
        frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).sort_values(
        ["pitcher_id", "role", "game_date", "game_pk"], kind="stable"
    ).reset_index(drop=True)


def _eligible(rows: pd.DataFrame, role: str, target: str) -> pd.DataFrame:
    output = rows[rows["role"].eq(role) & rows["model_eligible"].fillna(False) & rows[target].notna()].copy()
    if target in {"return_to_baseline", "strong_rebound"}:
        output = output[output["lag_process_collapse"].fillna(False)].copy()
    return output.sort_values(["game_date", "game_pk", "pitcher_id"], kind="stable")


def _metrics(truth: pd.Series | np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    y = np.asarray(truth, dtype=int)
    p = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
    if len(y) == 0 or len(np.unique(y)) < 2:
        return {
            "rows": int(len(y)),
            "events": int(y.sum()),
            "prevalence": _number(float(y.mean())) if len(y) else None,
            "average_precision": None,
            "brier": None,
            "log_loss": None,
        }
    return {
        "rows": int(len(y)),
        "events": int(y.sum()),
        "prevalence": _number(float(y.mean())),
        "average_precision": _number(average_precision_score(y, p)),
        "brier": _number(brier_score_loss(y, p)),
        "log_loss": _number(log_loss(y, p, labels=[0, 1])),
    }


def _new_model() -> Any:
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(max_iter=2000, C=0.5),
    )


def _fit_and_predict(train: pd.DataFrame, score: pd.DataFrame, features: list[str], target: str) -> np.ndarray:
    if train.empty or train[target].nunique() < 2 or score.empty:
        return np.full(len(score), float(train[target].mean()) if len(train) else 0.5)
    model = _new_model()
    model.fit(train[features], train[target].astype(int))
    return np.clip(model.predict_proba(score[features])[:, 1], 1e-6, 1 - 1e-6)


def _gate(model: dict[str, Any], baseline: dict[str, Any], variation: float, bootstrap: dict[str, Any]) -> dict[str, Any]:
    if model["average_precision"] is None or model["brier"] is None or model["log_loss"] is None:
        return {"status": "insufficient_classes", "passed": False}
    if variation <= 1e-8:
        return {
            "status": "baseline_only_not_supported",
            "passed": False,
            "reason": "Predictions have effectively zero variance; prevalence ranking cannot demonstrate incremental skill.",
        }
    ap_gain = float(model["average_precision"]) - float(baseline["average_precision"] or 0.0)
    brier_gain = float(model["brier"]) - float(baseline["brier"] or 0.0)
    log_gain = float(model["log_loss"]) - float(baseline["log_loss"] or 0.0)
    ap_interval = bootstrap.get("average_precision_delta_95_interval", [None, None])
    brier_interval = bootstrap.get("brier_delta_95_interval", [None, None])
    supported = (
        ap_gain >= 0.01
        and brier_gain <= 0
        and log_gain <= 0
        and ap_interval[0] is not None
        and ap_interval[0] > 0
        and brier_interval[1] is not None
        and brier_interval[1] <= 0
    )
    return {
        "status": "candidate_supported" if supported else "research_only",
        "passed": bool(supported),
        "average_precision_gain": _number(ap_gain),
        "brier_delta": _number(brier_gain),
        "log_loss_delta": _number(log_gain),
        "minimum_average_precision_gain": 0.01,
        "cluster_interval_required": True,
    }


def _evaluate_target(panel: pd.DataFrame, frozen: pd.DataFrame, role: str, target: str) -> tuple[dict[str, Any], pd.DataFrame | None]:
    rows = _eligible(panel, role, target)
    development = rows[rows["year"].isin(DEVELOPMENT_YEARS)]
    selection = rows[rows["year"].eq(SELECTION_YEAR)]
    external = rows[rows["year"].eq(DIAGNOSTIC_YEAR)]
    if development.empty or selection.empty or external.empty:
        return {"status": "insufficient_rows", "development_rows": int(len(development)), "selection_rows": int(len(selection)), "diagnostic_rows": int(len(external))}, None

    selection_metrics: dict[str, Any] = {}
    for name, features in (("stable_ewma_ma5", STABLE_FEATURES), ("context_workload", CONTEXT_FEATURES)):
        probability = _fit_and_predict(development, selection, features, target)
        selection_metrics[name] = _metrics(selection[target], probability)
    selected_name = min(
        selection_metrics,
        key=lambda name: (
            float(selection_metrics[name]["log_loss"] or 999.0),
            float(selection_metrics[name]["brier"] or 999.0),
        ),
    )
    selected_features = STABLE_FEATURES if selected_name == "stable_ewma_ma5" else CONTEXT_FEATURES
    train_all = rows[rows["year"].isin((*DEVELOPMENT_YEARS, SELECTION_YEAR))]
    probability = _fit_and_predict(train_all, external, selected_features, target)
    baseline_probability = float(train_all[target].mean()) if len(train_all) else 0.5
    baseline_probability = np.clip(baseline_probability, 1e-6, 1 - 1e-6)
    baseline = np.full(len(external), baseline_probability)
    model_metrics = _metrics(external[target], probability)
    baseline_metrics = _metrics(external[target], baseline)
    bootstrap_rows = external[["pitcher_id", target]].rename(columns={target: "actual"}).copy()
    bootstrap = _cluster_bootstrap(bootstrap_rows, probability, baseline_probability, samples=100)

    frozen_rows = frozen[frozen["role"].eq(role) & frozen["target"].eq(target)].copy()
    frozen_metrics = _metrics(frozen_rows["actual"], frozen_rows["probability"].to_numpy(dtype=float)) if len(frozen_rows) else None
    result = external[["year", "pitcher_id", "pitcher_name", "team", "role", "game_pk", "game_date"]].copy()
    result["target"] = target
    result["probability"] = probability
    result["actual"] = external[target].astype(bool).to_numpy()
    result["model"] = "slice16_" + selected_name
    audit = {
        "status": "fit",
        "development_years": list(DEVELOPMENT_YEARS),
        "selection_year": SELECTION_YEAR,
        "diagnostic_year": DIAGNOSTIC_YEAR,
        "development_rows": int(len(development)),
        "selection_rows": int(len(selection)),
        "diagnostic_rows": int(len(external)),
        "selected_model": selected_name,
        "selected_features": selected_features,
        "selection_metrics": selection_metrics,
        "diagnostic": model_metrics,
        "prevalence_baseline": baseline_metrics,
        "frozen_slice14": frozen_metrics,
        "prediction_variation_std": _number(float(np.std(probability))),
        "cluster_bootstrap": bootstrap,
    }
    audit["release_gate"] = _gate(model_metrics, baseline_metrics, float(np.std(probability)), bootstrap)
    if frozen_metrics and len(frozen_rows) == len(external):
        frozen_ap_delta = float(model_metrics["average_precision"] or 0.0) - float(frozen_metrics["average_precision"] or 0.0)
        frozen_brier_delta = float(model_metrics["brier"] or 0.0) - float(frozen_metrics["brier"] or 0.0)
        frozen_log_delta = float(model_metrics["log_loss"] or 0.0) - float(frozen_metrics["log_loss"] or 0.0)
        audit["frozen_comparison"] = {
            "status": "improves_frozen" if frozen_ap_delta >= 0.01 and frozen_brier_delta <= 0 and frozen_log_delta <= 0 else "keep_frozen",
            "average_precision_delta": _number(frozen_ap_delta),
            "brier_delta": _number(frozen_brier_delta),
            "log_loss_delta": _number(frozen_log_delta),
            "minimum_average_precision_gain": 0.01,
        }
    else:
        audit["frozen_comparison"] = {
            "status": "incomparable_denominator",
            "reason": "Slice 14 and Slice 16 do not expose the same eligible keys for this target.",
            "slice14_rows": int(len(frozen_rows)),
            "slice16_rows": int(len(external)),
        }
    return audit, result


def refresh_performance_state_v2_slice16(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    panel = _load_states(root)
    frozen_path = slice14_prediction_path(root)
    if not frozen_path.exists():
        raise FileNotFoundError(f"Slice 14 prediction artifact not found: {frozen_path}")
    with duckdb.connect() as connection:
        frozen = connection.execute("SELECT * FROM read_parquet(?)", [str(frozen_path)]).fetchdf()
    predictions: list[pd.DataFrame] = []
    roles: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        roles[role] = {}
        for target in TARGETS:
            audit, result = _evaluate_target(panel, frozen, role, target)
            roles[role][target] = audit
            if result is not None:
                predictions.append(result)
    output = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    if not output.empty:
        _write_parquet_atomic(output, slice16_prediction_path(root), "performance_state_v2_slice16_predictions_2026")
    audit = {
        "version": SLICE16_VERSION,
        "status": "research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "development_years": list(DEVELOPMENT_YEARS),
        "selection_year": SELECTION_YEAR,
        "diagnostic_year": DIAGNOSTIC_YEAR,
        "prospective_year": 2027,
        "roles": roles,
        "prediction_rows": int(len(output)),
        "gate_policy": {
            "baseline_only_is_not_success": True,
            "minimum_average_precision_gain": 0.01,
            "require_cluster_interval": True,
            "2026_is_fixed_diagnostic_only": True,
            "production_integration": "closed",
        },
        "warnings": [
            "This is a research-only challenger and does not overwrite Slice 14 or Slice 15.",
            "2026 is a fixed diagnostic, not untouched prospective validation.",
            "A baseline prevalence model can be reported but can never pass the incremental release gate.",
        ],
    }
    _write_json_atomic(audit, slice16_audit_path(root))
    return audit


def get_performance_state_v2_slice16_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = slice16_audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slice 16 has not been built.")
    return json.loads(path.read_text(encoding="utf-8"))
