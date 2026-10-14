from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.core.config import settings
from app.services.performance_state_service import ROLES, _number, _write_json_atomic, _write_parquet_atomic
from app.services.performance_state_v2_service import TARGETS, YEARS
from app.services.performance_state_forecast_service import FEATURE_LAYERS, _cumulative_features, _observed_features
from app.services.performance_state_v2_slice16_service import _eligible, _metrics


STRICT_REPLAY_VERSION = "performance_state_v2_strict_2026_replay_lock_v1"
STRICT_TRAIN_YEARS = (2023, 2024)
STRICT_CALIBRATION_YEAR = 2025
STRICT_TEST_YEAR = 2026

# This map is intentionally fixed in source. It is not selected from 2026.
LOCKED_LAYER_MAP: dict[str, dict[str, str]] = {
    "SP": {
        "process_collapse": "D_gas_har",
        "result_collapse": "C_regime_prior",
        "onset_process_collapse": "D_gas_har",
        "persistent_process_collapse": "A_baseline",
        "return_to_baseline": "B_latent_state",
        "strong_rebound": "B_latent_state",
    },
    "RP": {
        "process_collapse": "D_gas_har",
        "result_collapse": "B_latent_state",
        "onset_process_collapse": "D_gas_har",
        "persistent_process_collapse": "C_regime_prior",
        "return_to_baseline": "C_regime_prior",
        "strong_rebound": "E_evt",
    },
}


def audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_strict_2026_replay.json"


def prediction_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_strict_2026_replay_predictions.parquet"


def _load_states(root: Path, years: tuple[int, ...]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year in years:
        path = root / "derived" / f"performance_state_v2_slice14_states_{year}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Strict replay state artifact not found: {path}")
        with duckdb.connect() as connection:
            frame = connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchdf()
        frame["year"] = int(year)
        frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).sort_values(
        ["pitcher_id", "role", "game_date", "game_pk"], kind="stable"
    ).reset_index(drop=True)


def _fit_model(train: pd.DataFrame, features: list[str], target: str) -> Any:
    model = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(max_iter=2000, C=0.5),
    )
    model.fit(train[features], train[target].astype(int))
    return model


def _predict(model: Any, rows: pd.DataFrame, features: list[str]) -> np.ndarray:
    return np.clip(model.predict_proba(rows[features])[:, 1], 1e-6, 1 - 1e-6)


def _platt(raw: np.ndarray, truth: pd.Series) -> LogisticRegression | None:
    if len(raw) < 20 or truth.astype(int).nunique() < 2:
        return None
    logits = np.log(np.clip(raw, 1e-6, 1 - 1e-6) / np.clip(1.0 - raw, 1e-6, 1 - 1e-6)).reshape(-1, 1)
    calibrator = LogisticRegression(C=1.0, max_iter=1000)
    calibrator.fit(logits, truth.astype(int))
    return calibrator


def _apply_platt(raw: np.ndarray, calibrator: LogisticRegression | None) -> np.ndarray:
    if calibrator is None:
        return np.clip(raw, 1e-6, 1 - 1e-6)
    logits = np.log(np.clip(raw, 1e-6, 1 - 1e-6) / np.clip(1.0 - raw, 1e-6, 1 - 1e-6)).reshape(-1, 1)
    return np.clip(calibrator.predict_proba(logits)[:, 1], 1e-6, 1 - 1e-6)


def _sha256_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fit_locked_target(rows: pd.DataFrame, role: str, target: str, layer: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    development = rows[rows["year"].isin(STRICT_TRAIN_YEARS)].copy()
    calibration = rows[rows["year"].eq(STRICT_CALIBRATION_YEAR)].copy()
    if development.empty or calibration.empty or development[target].nunique() < 2:
        return {"status": "insufficient_rows_or_classes"}, None
    features = _observed_features(development, _cumulative_features(layer))
    if not features:
        return {"status": "no_observed_locked_features"}, None
    model = _fit_model(development, features, target)
    calibration_raw = _predict(model, calibration, features)
    calibrator = _platt(calibration_raw, calibration[target])
    negative = calibration_probability = _apply_platt(calibration_raw, calibrator)
    negative_scores = calibration_probability[calibration[target].astype(int).to_numpy() == 0]
    threshold = float(np.quantile(negative_scores, 0.90)) if len(negative_scores) else 1.0
    return {
        "status": "fit",
        "locked_layer": layer,
        "locked_features": features,
        "train_years": list(STRICT_TRAIN_YEARS),
        "calibration_year": STRICT_CALIBRATION_YEAR,
        "test_year": STRICT_TEST_YEAR,
        "train_rows": int(len(development)),
        "calibration_rows": int(len(calibration)),
        "calibration_method": "platt_if_2025_has_two_classes",
        "calibration_metrics": _metrics(calibration[target], calibration_probability),
        "fixed_false_alert_threshold": _number(threshold),
    }, {
        "model": model,
        "calibrator": calibrator,
        "features": features,
        "target": target,
        "threshold": threshold,
        "development_prevalence": float(development[target].mean()),
    }


def _score_locked_target(bundle: dict[str, Any], test: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame | None]:
    if test.empty:
        return {"status": "no_test_rows"}, None
    target = str(bundle["target"])
    features = list(bundle["features"])
    test_raw = _predict(bundle["model"], test, features)
    test_probability = _apply_platt(test_raw, bundle["calibrator"])
    threshold = float(bundle["threshold"])
    output = test[["year", "pitcher_id", "pitcher_name", "team", "role", "game_pk", "game_date"]].copy()
    output["target"] = target
    output["probability"] = test_probability
    output["raw_probability"] = test_raw
    output["actual"] = test[target].astype(bool).to_numpy()
    output["alert"] = test_probability >= threshold
    output["locked_layer"] = bundle["layer"]
    output["calibration"] = "platt_2025" if bundle["calibrator"] is not None else "raw_no_calibration"
    return {
        "status": "scored",
        "test_year": STRICT_TEST_YEAR,
        "test_rows": int(len(test)),
        "test_metrics": _metrics(test[target], test_probability),
        "test_raw_metrics": _metrics(test[target], test_raw),
        "test_prevalence_baseline": _metrics(test[target], np.full(len(test), bundle["development_prevalence"])),
    }, output


def refresh_strict_2026_replay(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    spec = {
        "version": STRICT_REPLAY_VERSION,
        "train_years": list(STRICT_TRAIN_YEARS),
        "calibration_year": STRICT_CALIBRATION_YEAR,
        "test_year": STRICT_TEST_YEAR,
        "layer_map": LOCKED_LAYER_MAP,
        "calibration_policy": "Platt if the 2025 calibration window has >=20 rows and both classes; otherwise raw",
        "threshold_policy": "90th percentile of negative 2025 calibrated probabilities",
        "no_2026_model_selection": True,
    }
    fingerprint = _sha256_payload(spec)
    # This is the lock boundary: all model specifications are serialized before 2026 is read.
    development = _load_states(root, (*STRICT_TRAIN_YEARS, STRICT_CALIBRATION_YEAR))
    roles: dict[str, dict[str, Any]] = {}
    bundles: dict[tuple[str, str], dict[str, Any]] = {}
    predictions: list[pd.DataFrame] = []
    for role in ROLES:
        roles[role] = {}
        for target in TARGETS:
            layer = LOCKED_LAYER_MAP[role][target]
            role_rows = _eligible(development, role, target)
            result, bundle = _fit_locked_target(role_rows, role, target, layer)
            roles[role][target] = result
            if bundle is not None:
                bundle["layer"] = layer
                bundles[(role, target)] = bundle
    # 2026 is loaded only after the fixed spec and all development/calibration models are fitted.
    evaluation = _load_states(root, (STRICT_TEST_YEAR,))
    for role in ROLES:
        for target in TARGETS:
            bundle = bundles.get((role, target))
            if bundle is None:
                continue
            test_rows = _eligible(evaluation, role, target)
            result, output = _score_locked_target(bundle, test_rows.copy())
            roles[role][target].update(result)
            if output is not None:
                predictions.append(output)
    output = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    if not output.empty:
        _write_parquet_atomic(output, prediction_path(root), "performance_state_v2_strict_2026_replay_predictions")
    audit = {
        **spec,
        "status": "retrospective_holdout_replay",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_fingerprint": fingerprint,
        "roles": roles,
        "prediction_rows": int(len(output)),
        "integration_gate": "CLOSED",
        "warnings": [
            "2026 was previously inspected by this project; this is not an untouched test.",
            "This replay freezes model specification before scoring 2026 and is intended to prevent further 2026-driven tuning.",
            "Upstream Plus/state artifacts are retrospective and do not provide pristine upstream Plus-model validation.",
            "2027 remains the only untouched prospective validation year.",
        ],
    }
    _write_json_atomic(audit, audit_path(root))
    return audit


def get_strict_2026_replay_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Strict 2026 replay has not been built.")
    return json.loads(path.read_text(encoding="utf-8"))
