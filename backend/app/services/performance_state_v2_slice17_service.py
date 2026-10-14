from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from app.core.config import settings
from app.services.performance_state_service import ROLES, _number, _write_json_atomic, _write_parquet_atomic
from app.services.performance_state_v2_service import TARGETS
from app.services.performance_state_v2_slice14_service import slice14_prediction_path
from app.services.performance_state_v2_slice16_service import (
    CONTEXT_FEATURES,
    DIAGNOSTIC_YEAR,
    DEVELOPMENT_YEARS,
    SELECTION_YEAR,
    STABLE_FEATURES,
    _eligible,
    _load_states,
    _metrics,
    _new_model,
    slice16_audit_path,
)


SLICE17_VERSION = "performance_state_v2_calibration_slice17_v1"


def slice17_audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice17.json"


def slice17_prediction_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice17_predictions_2026.parquet"


def _load_frozen(root: Path) -> pd.DataFrame:
    path = slice14_prediction_path(root)
    if not path.exists():
        raise FileNotFoundError(f"Slice 14 prediction artifact not found: {path}")
    with duckdb.connect() as connection:
        return connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchdf()


def _fit_model(train: pd.DataFrame, features: list[str], target: str) -> Any:
    model = _new_model()
    model.fit(train[features], train[target].astype(int))
    return model


def _raw_predict(model: Any, rows: pd.DataFrame, features: list[str]) -> np.ndarray:
    return np.clip(model.predict_proba(rows[features])[:, 1], 1e-6, 1 - 1e-6)


def _fit_calibrator(method: str, probabilities: np.ndarray, truth: pd.Series | np.ndarray) -> Any | None:
    y = np.asarray(truth, dtype=int)
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    if len(y) < 20 or len(np.unique(y)) < 2:
        return None
    if method == "platt":
        logits = np.log(p / (1.0 - p)).reshape(-1, 1)
        calibrator = LogisticRegression(C=1.0, max_iter=1000)
        calibrator.fit(logits, y)
        return calibrator
    if method == "isotonic":
        calibrator = IsotonicRegression(y_min=1e-6, y_max=1 - 1e-6, out_of_bounds="clip")
        calibrator.fit(p, y)
        return calibrator
    raise ValueError(f"Unknown calibration method: {method}")


def _apply_calibrator(method: str, calibrator: Any | None, probabilities: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    if method == "raw" or calibrator is None:
        return p
    if method == "platt":
        logits = np.log(p / (1.0 - p)).reshape(-1, 1)
        return np.clip(calibrator.predict_proba(logits)[:, 1], 1e-6, 1 - 1e-6)
    return np.clip(np.asarray(calibrator.predict(p), dtype=float), 1e-6, 1 - 1e-6)


def _select_calibration(selection_truth: pd.Series, raw: np.ndarray) -> tuple[str, dict[str, dict[str, Any]], dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {"raw": {"calibrator": None}}
    for method in ("platt", "isotonic"):
        candidates[method] = {"calibrator": _fit_calibrator(method, raw, selection_truth)}
    metrics: dict[str, dict[str, Any]] = {}
    for method, value in candidates.items():
        metrics[method] = _metrics(selection_truth, _apply_calibrator(method, value["calibrator"], raw))
    eligible = [name for name, value in candidates.items() if name == "raw" or value["calibrator"] is not None]
    selected = min(eligible, key=lambda name: (float(metrics[name]["log_loss"] or 999.0), float(metrics[name]["brier"] or 999.0)))
    return selected, metrics, candidates[selected]


def _evaluate_target(panel: pd.DataFrame, frozen: pd.DataFrame, role: str, target: str, selected_model: str) -> tuple[dict[str, Any], pd.DataFrame | None]:
    rows = _eligible(panel, role, target)
    development = rows[rows["year"].isin(DEVELOPMENT_YEARS)]
    selection = rows[rows["year"].eq(SELECTION_YEAR)]
    external = rows[rows["year"].eq(DIAGNOSTIC_YEAR)]
    if development.empty or selection.empty or external.empty or development[target].nunique() < 2:
        return {"status": "insufficient_rows_or_classes"}, None
    features = STABLE_FEATURES if selected_model == "stable_ewma_ma5" else CONTEXT_FEATURES
    development_model = _fit_model(development, features, target)
    selection_raw = _raw_predict(development_model, selection, features)
    method, selection_metrics, selected = _select_calibration(selection[target], selection_raw)
    final_model = _fit_model(pd.concat([development, selection], ignore_index=True), features, target)
    external_raw = _raw_predict(final_model, external, features)
    calibrated = _apply_calibrator(method, selected["calibrator"], external_raw)
    raw_metrics = _metrics(external[target], external_raw)
    calibrated_metrics = _metrics(external[target], calibrated)
    frozen_rows = frozen[frozen["role"].eq(role) & frozen["target"].eq(target)].copy()
    frozen_metrics = _metrics(frozen_rows["actual"], frozen_rows["probability"].to_numpy(dtype=float)) if len(frozen_rows) else None
    calibration_status = "retain_calibration" if (
        calibrated_metrics["brier"] is not None
        and raw_metrics["brier"] is not None
        and calibrated_metrics["log_loss"] is not None
        and raw_metrics["log_loss"] is not None
        and calibrated_metrics["brier"] <= raw_metrics["brier"]
        and calibrated_metrics["log_loss"] <= raw_metrics["log_loss"]
    ) else "retain_raw"
    result = external[["year", "pitcher_id", "pitcher_name", "team", "role", "game_pk", "game_date"]].copy()
    result["target"] = target
    result["raw_probability"] = external_raw
    result["calibrated_probability"] = calibrated
    result["probability"] = calibrated if calibration_status == "retain_calibration" else external_raw
    result["actual"] = external[target].astype(bool).to_numpy()
    result["calibration_method"] = method if calibration_status == "retain_calibration" else "raw"
    result["model"] = "slice17_" + selected_model
    audit = {
        "status": "fit",
        "selected_model": selected_model,
        "selected_features": features,
        "development_rows": int(len(development)),
        "selection_rows": int(len(selection)),
        "diagnostic_rows": int(len(external)),
        "selection_calibration": {"selected_method": method, "candidates": selection_metrics},
        "diagnostic_raw": raw_metrics,
        "diagnostic_calibrated": calibrated_metrics,
        "calibration_decision": calibration_status,
        "frozen_slice14": frozen_metrics,
        "warnings": ["Calibration is trained only on the 2025 selection window; 2026 is diagnostic-only."]
    }
    if frozen_metrics and len(frozen_rows) == len(external):
        audit["frozen_comparison"] = {
            "raw_log_loss_delta": _number(float(raw_metrics["log_loss"] or 0.0) - float(frozen_metrics["log_loss"] or 0.0)),
            "calibrated_log_loss_delta": _number(float(calibrated_metrics["log_loss"] or 0.0) - float(frozen_metrics["log_loss"] or 0.0)),
            "same_denominator": True,
        }
    else:
        audit["frozen_comparison"] = {"same_denominator": False, "status": "incomparable_denominator"}
    return audit, result


def refresh_performance_state_v2_slice17(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    slice16_path = slice16_audit_path(root)
    if not slice16_path.exists():
        raise FileNotFoundError("Slice 16 must be built before Slice 17.")
    slice16 = json.loads(slice16_path.read_text(encoding="utf-8"))
    panel = _load_states(root)
    frozen = _load_frozen(root)
    predictions: list[pd.DataFrame] = []
    roles: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        roles[role] = {}
        for target in TARGETS:
            previous = slice16["roles"].get(role, {}).get(target, {})
            selected_model = previous.get("selected_model")
            if selected_model not in {"stable_ewma_ma5", "context_workload"}:
                roles[role][target] = {"status": "slice16_model_unavailable"}
                continue
            audit, result = _evaluate_target(panel, frozen, role, target, selected_model)
            roles[role][target] = audit
            if result is not None:
                predictions.append(result)
    output = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    if not output.empty:
        _write_parquet_atomic(output, slice17_prediction_path(root), "performance_state_v2_slice17_predictions_2026")
    audit = {
        "version": SLICE17_VERSION,
        "status": "research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "development_years": list(DEVELOPMENT_YEARS),
        "selection_year": SELECTION_YEAR,
        "diagnostic_year": DIAGNOSTIC_YEAR,
        "prospective_year": 2027,
        "roles": roles,
        "prediction_rows": int(len(output)),
        "policy": {
            "calibration_candidates": ["raw", "platt", "isotonic"],
            "selection_is_2025_only": True,
            "diagnostic_2026_is_fixed": True,
            "production_integration": "closed",
        },
        "warnings": [
            "Slice 17 calibrates the Slice 16 challenger only; it does not rewrite Slice 14 or Slice 15.",
            "2026 is a fixed diagnostic and 2027 remains untouched.",
        ],
    }
    _write_json_atomic(audit, slice17_audit_path(root))
    return audit


def get_performance_state_v2_slice17_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = slice17_audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slice 17 has not been built.")
    return json.loads(path.read_text(encoding="utf-8"))
