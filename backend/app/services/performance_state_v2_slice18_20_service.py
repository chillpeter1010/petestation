from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
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
from app.services.performance_state_v2_slice17_service import slice17_prediction_path


SLICE18_20_VERSION = "performance_state_v2_partial_pooling_bias_subgroup_slice18_20_v1"
WORKLOAD_FEATURES = [
    "calendar_days_since_prior",
    "workload_pitches_7d",
    "workload_pitches_28d",
    "previous_appearance_pitches",
]


def audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice18_20.json"


def slice18_prediction_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice18_predictions_2026.parquet"


def slice19_prediction_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice19_predictions_2026.parquet"


def _load_frozen(root: Path) -> pd.DataFrame:
    with duckdb.connect() as connection:
        return connection.execute("SELECT * FROM read_parquet(?)", [str(slice14_prediction_path(root))]).fetchdf()


def _fit_model(train: pd.DataFrame, features: list[str], target: str) -> Any:
    model = _new_model()
    model.fit(train[features], train[target].astype(int))
    return model


def _predict(model: Any, rows: pd.DataFrame, features: list[str]) -> np.ndarray:
    return np.clip(model.predict_proba(rows[features])[:, 1], 1e-6, 1 - 1e-6)


def _logit(probability: np.ndarray | float) -> np.ndarray:
    p = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1.0 - p))


def _sigmoid(value: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -30.0, 30.0)))


def _estimate_pitcher_shifts(train: pd.DataFrame, raw: np.ndarray, target: str) -> pd.DataFrame:
    working = train[["pitcher_id", target]].copy().reset_index(drop=True)
    working["raw"] = raw
    overall = float(np.mean(raw)) if len(raw) else 0.5
    rows: list[dict[str, Any]] = []
    for pitcher_id, group in working.groupby("pitcher_id", dropna=True):
        n = len(group)
        mean_raw = float(group["raw"].mean())
        smoothed_rate = float((group[target].astype(int).sum() + 2.0 * overall) / (n + 4.0))
        residual = float(_logit(smoothed_rate) - _logit(mean_raw))
        observation_information = max(n * max(mean_raw * (1.0 - mean_raw), 0.01), 0.01)
        rows.append({"pitcher_id": pitcher_id, "n": n, "raw_residual": residual, "information": observation_information})
    shifts = pd.DataFrame(rows)
    if shifts.empty:
        return pd.DataFrame(columns=["pitcher_id", "shift", "n"])
    prior_variance = float(np.var(shifts["raw_residual"].to_numpy(dtype=float), ddof=1)) if len(shifts) > 1 else 0.0
    prior_variance = max(prior_variance, 0.01)
    shrinkage = prior_variance / (prior_variance + 1.0 / shifts["information"].to_numpy(dtype=float))
    shifts["shift"] = shifts["raw_residual"] * shrinkage
    shifts["prior_variance"] = prior_variance
    return shifts[["pitcher_id", "shift", "n", "prior_variance"]]


def _apply_shifts(rows: pd.DataFrame, raw: np.ndarray, shifts: pd.DataFrame) -> np.ndarray:
    mapping = shifts.set_index("pitcher_id")["shift"].to_dict() if not shifts.empty else {}
    shift = rows["pitcher_id"].map(mapping).fillna(0.0).to_numpy(dtype=float)
    return np.clip(_sigmoid(_logit(raw) + shift), 1e-6, 1 - 1e-6)


def _select_pooling(selection_truth: pd.Series, base: np.ndarray, pooled: np.ndarray) -> str:
    base_metrics = _metrics(selection_truth, base)
    pooled_metrics = _metrics(selection_truth, pooled)
    if (
        pooled_metrics["brier"] is not None
        and base_metrics["brier"] is not None
        and pooled_metrics["log_loss"] is not None
        and base_metrics["log_loss"] is not None
        and pooled_metrics["brier"] <= base_metrics["brier"]
        and pooled_metrics["log_loss"] <= base_metrics["log_loss"]
        and float(pooled_metrics["average_precision"] or 0.0) >= float(base_metrics["average_precision"] or 0.0) - 0.005
    ):
        return "partial_pooling"
    return "global_only"


def _slice18_target(panel: pd.DataFrame, role: str, target: str, selected_model: str) -> tuple[dict[str, Any], pd.DataFrame | None]:
    rows = _eligible(panel, role, target)
    development = rows[rows["year"].isin(DEVELOPMENT_YEARS)]
    selection = rows[rows["year"].eq(SELECTION_YEAR)]
    external = rows[rows["year"].eq(DIAGNOSTIC_YEAR)]
    if development.empty or selection.empty or external.empty or development[target].nunique() < 2:
        return {"status": "insufficient_rows_or_classes"}, None
    features = STABLE_FEATURES if selected_model == "stable_ewma_ma5" else CONTEXT_FEATURES
    development_model = _fit_model(development, features, target)
    development_raw = _predict(development_model, development, features)
    shifts = _estimate_pitcher_shifts(development, development_raw, target)
    selection_raw = _predict(development_model, selection, features)
    selection_pooled = _apply_shifts(selection, selection_raw, shifts)
    decision = _select_pooling(selection[target], selection_raw, selection_pooled)
    final_model = _fit_model(pd.concat([development, selection], ignore_index=True), features, target)
    external_raw = _predict(final_model, external, features)
    external_pooled = _apply_shifts(external, external_raw, shifts)
    final_probability = external_pooled if decision == "partial_pooling" else external_raw
    audit = {
        "status": "fit",
        "selected_model": selected_model,
        "selected_features": features,
        "development_rows": int(len(development)),
        "selection_rows": int(len(selection)),
        "diagnostic_rows": int(len(external)),
        "pitcher_shift_count": int(len(shifts)),
        "pitcher_shift_median_abs": _number(float(shifts["shift"].abs().median())) if len(shifts) else None,
        "selection_global_only": _metrics(selection[target], selection_raw),
        "selection_partial_pooling": _metrics(selection[target], selection_pooled),
        "selected_for_diagnostic": decision,
        "diagnostic_global_only": _metrics(external[target], external_raw),
        "diagnostic_partial_pooling": _metrics(external[target], external_pooled),
        "diagnostic_selected": _metrics(external[target], final_probability),
        "warnings": ["Empirical-Bayes shifts are a research partial-pooling approximation, not a fitted causal random-effects model."],
    }
    output = external[["year", "pitcher_id", "pitcher_name", "team", "role", "game_pk", "game_date"]].copy()
    output["target"] = target
    output["global_probability"] = external_raw
    output["partial_pooling_probability"] = external_pooled
    output["probability"] = final_probability
    output["actual"] = external[target].astype(bool).to_numpy()
    output["model"] = "slice18_" + selected_model
    return audit, output


def _residualize_workload(train: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    means = train.groupby("pitcher_id")[WORKLOAD_FEATURES].mean()
    overall = train[WORKLOAD_FEATURES].mean()
    output = rows.copy()
    for feature in WORKLOAD_FEATURES:
        baseline = output["pitcher_id"].map(means[feature]).fillna(overall[feature])
        output[f"resid_{feature}"] = pd.to_numeric(output[feature], errors="coerce") - pd.to_numeric(baseline, errors="coerce")
    return output


def _slice19_target(panel: pd.DataFrame, role: str, target: str, selected_model: str) -> tuple[dict[str, Any], pd.DataFrame | None]:
    rows = _eligible(panel, role, target)
    development = rows[rows["year"].isin(DEVELOPMENT_YEARS)]
    selection = rows[rows["year"].eq(SELECTION_YEAR)]
    external = rows[rows["year"].eq(DIAGNOSTIC_YEAR)]
    if development.empty or selection.empty or external.empty or development[target].nunique() < 2:
        return {"status": "insufficient_rows_or_classes"}, None
    base_model = _fit_model(development, CONTEXT_FEATURES, target)
    selection_context = _predict(base_model, selection, CONTEXT_FEATURES)
    external_context = _predict(_fit_model(pd.concat([development, selection], ignore_index=True), CONTEXT_FEATURES, target), external, CONTEXT_FEATURES)
    development_resid = _residualize_workload(development, development)
    selection_resid = _residualize_workload(development, selection)
    external_resid = _residualize_workload(development, external)
    residual_features = STABLE_FEATURES + [f"resid_{feature}" for feature in WORKLOAD_FEATURES]
    residual_model = _fit_model(development_resid, residual_features, target)
    selection_residual = _predict(residual_model, selection_resid, residual_features)
    final_residual_model = _fit_model(pd.concat([development_resid, selection_resid], ignore_index=True), residual_features, target)
    external_residual = _predict(final_residual_model, external_resid, residual_features)
    candidate_metrics = {
        "context_workload": _metrics(selection[target], selection_context),
        "residualized_workload": _metrics(selection[target], selection_residual),
    }
    selected = min(candidate_metrics, key=lambda name: (float(candidate_metrics[name]["log_loss"] or 999.0), float(candidate_metrics[name]["brier"] or 999.0)))
    final_probability = external_residual if selected == "residualized_workload" else external_context
    audit = {
        "status": "fit",
        "selected_model": selected_model,
        "development_rows": int(len(development)),
        "selection_rows": int(len(selection)),
        "diagnostic_rows": int(len(external)),
        "selection_candidates": candidate_metrics,
        "selected_for_diagnostic": selected,
        "diagnostic_context_workload": _metrics(external[target], external_context),
        "diagnostic_residualized_workload": _metrics(external[target], external_residual),
        "diagnostic_selected": _metrics(external[target], final_probability),
        "interpretation": "Sensitivity analysis for workload selection bias; residualization does not identify a causal workload effect.",
    }
    output = external[["year", "pitcher_id", "pitcher_name", "team", "role", "game_pk", "game_date"]].copy()
    output["target"] = target
    output["context_probability"] = external_context
    output["residualized_probability"] = external_residual
    output["probability"] = final_probability
    output["actual"] = external[target].astype(bool).to_numpy()
    output["model"] = "slice19_" + selected
    return audit, output


def _calibration_summary(truth: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    y = np.asarray(truth, dtype=int)
    p = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
    if len(y) < 20 or len(np.unique(y)) < 2:
        return {"rows": int(len(y)), "events": int(y.sum()), "ece": None, "slope": None, "intercept": None}
    bins = pd.qcut(pd.Series(p), q=min(10, len(p)), duplicates="drop")
    errors: list[float] = []
    weights: list[int] = []
    for _, positions in pd.Series(np.arange(len(p))).groupby(bins, observed=True):
        index = positions.to_numpy(dtype=int)
        errors.append(abs(float(p[index].mean()) - float(y[index].mean())))
        weights.append(len(index))
    logits = _logit(p).reshape(-1, 1)
    calibration_model = LogisticRegression(C=1e6, max_iter=1000).fit(logits, y)
    return {
        "rows": int(len(y)),
        "events": int(y.sum()),
        "prevalence": _number(float(y.mean())),
        "ece": _number(float(np.average(errors, weights=weights))),
        "slope": _number(float(calibration_model.coef_[0, 0])),
        "intercept": _number(float(calibration_model.intercept_[0])),
    }


def _arsenal(rows: pd.DataFrame) -> pd.Series:
    counts = rows[["fastball_pitches", "breaking_pitches", "offspeed_pitches"]].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    labels = np.array(["Fastball", "Breaking", "Offspeed"])
    values = counts.to_numpy(dtype=float)
    total = values.sum(axis=1)
    return pd.Series(np.where(total > 0, labels[np.argmax(values, axis=1)], "Unknown"), index=rows.index)


def _slice20(panel: pd.DataFrame, root: Path) -> dict[str, Any]:
    prediction_path = slice17_prediction_path(root)
    if not prediction_path.exists():
        raise FileNotFoundError("Slice 17 predictions must be built before Slice 20.")
    with duckdb.connect() as connection:
        predictions = connection.execute("SELECT * FROM read_parquet(?)", [str(prediction_path)]).fetchdf()
        states = connection.execute(
            "SELECT pitcher_id, role, game_pk, fastball_pitches, breaking_pitches, offspeed_pitches FROM read_parquet(?) WHERE year = 2026",
            [str(Path(root) / "derived" / "performance_state_v2_slice14_states_2026.parquet")],
        ).fetchdf()
    predictions = predictions.merge(states, on=["pitcher_id", "role", "game_pk"], how="left", validate="many_to_one")
    predictions["arsenal"] = _arsenal(predictions)
    output: dict[str, Any] = {"roles": {}}
    for role in ROLES:
        output["roles"][role] = {}
        for target in TARGETS:
            subset = predictions[predictions["role"].eq(role) & predictions["target"].eq(target)].copy()
            groups: dict[str, Any] = {}
            for group_name, group in [("All", subset), *list(subset.groupby("arsenal", dropna=False))]:
                if len(group) == 0:
                    continue
                groups[str(group_name)] = _calibration_summary(
                    group["actual"].astype(int).to_numpy(), group["probability"].to_numpy(dtype=float)
                )
                groups[str(group_name)]["status"] = "monitor" if len(group) < 50 or (groups[str(group_name)]["ece"] is not None and groups[str(group_name)]["ece"] > 0.05) else "acceptable_for_research"
            output["roles"][role][target] = {"rows": int(len(subset)), "groups": groups}
    return output


def refresh_performance_state_v2_slice18_20(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    slice16_path = slice16_audit_path(root)
    if not slice16_path.exists():
        raise FileNotFoundError("Slice 16 must be built before Slice 18–20.")
    slice16 = json.loads(slice16_path.read_text(encoding="utf-8"))
    panel = _load_states(root)
    frozen = _load_frozen(root)
    slice18_roles: dict[str, dict[str, Any]] = {}
    slice19_roles: dict[str, dict[str, Any]] = {}
    slice18_predictions: list[pd.DataFrame] = []
    slice19_predictions: list[pd.DataFrame] = []
    for role in ROLES:
        slice18_roles[role] = {}
        slice19_roles[role] = {}
        for target in TARGETS:
            selected_model = slice16["roles"].get(role, {}).get(target, {}).get("selected_model")
            if selected_model not in {"stable_ewma_ma5", "context_workload"}:
                slice18_roles[role][target] = {"status": "slice16_model_unavailable"}
                slice19_roles[role][target] = {"status": "slice16_model_unavailable"}
                continue
            audit18, predictions18 = _slice18_target(panel, role, target, selected_model)
            audit19, predictions19 = _slice19_target(panel, role, target, selected_model)
            slice18_roles[role][target] = audit18
            slice19_roles[role][target] = audit19
            if predictions18 is not None:
                slice18_predictions.append(predictions18)
            if predictions19 is not None:
                slice19_predictions.append(predictions19)
    output18 = pd.concat(slice18_predictions, ignore_index=True) if slice18_predictions else pd.DataFrame()
    output19 = pd.concat(slice19_predictions, ignore_index=True) if slice19_predictions else pd.DataFrame()
    if not output18.empty:
        _write_parquet_atomic(output18, slice18_prediction_path(root), "performance_state_v2_slice18_predictions_2026")
    if not output19.empty:
        _write_parquet_atomic(output19, slice19_prediction_path(root), "performance_state_v2_slice19_predictions_2026")
    audit = {
        "version": SLICE18_20_VERSION,
        "status": "research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "development_years": list(DEVELOPMENT_YEARS),
        "selection_year": SELECTION_YEAR,
        "diagnostic_year": DIAGNOSTIC_YEAR,
        "prospective_year": 2027,
        "slice18_partial_pooling": {"roles": slice18_roles, "prediction_rows": int(len(output18))},
        "slice19_workload_bias_sensitivity": {"roles": slice19_roles, "prediction_rows": int(len(output19))},
        "slice20_subgroup_calibration": _slice20(panel, root),
        "policy": {
            "2026_is_fixed_diagnostic_only": True,
            "2027_remains_untouched": True,
            "production_integration": "closed",
        },
        "warnings": [
            "Slice 18 partial pooling is empirical-Bayes shrinkage, not a causal random-effects estimate.",
            "Slice 19 is workload selection-bias sensitivity, not an identification of causal workload effects.",
            "Slice 20 subgroup calibration is diagnostic and does not retune probabilities automatically.",
        ],
    }
    _write_json_atomic(audit, audit_path(root))
    return audit


def get_performance_state_v2_slice18_20_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slices 18–20 have not been built.")
    return json.loads(path.read_text(encoding="utf-8"))
