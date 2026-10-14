from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np

from app.core.config import settings
from app.services.performance_state_service import ROLES, _number, _write_json_atomic
from app.services.performance_state_v2_service import TARGETS
from app.services.performance_state_v2_slice16_service import (
    CONTEXT_FEATURES,
    DEVELOPMENT_YEARS,
    STABLE_FEATURES,
    _eligible,
    _fit_and_predict,
    _load_states,
    _metrics,
)
from app.services.performance_state_v2_slice18_20_service import (
    WORKLOAD_FEATURES,
    _apply_shifts,
    _estimate_pitcher_shifts,
    _fit_model,
    _predict,
    _residualize_workload,
)


SLICE21_22_VERSION = "performance_state_v2_rolling_robustness_freeze_slice21_22_v1"
FOLDS = [
    ((2023,), 2024),
    ((2023, 2024), 2025),
    ((2023, 2024, 2025), 2026),
]


def audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice21_22.json"


def _candidate_features(selected_model: str) -> list[str]:
    return STABLE_FEATURES if selected_model == "stable_ewma_ma5" else CONTEXT_FEATURES


def _score_candidate(train: pd.DataFrame, test: pd.DataFrame, target: str, selected_model: str, candidate: str) -> np.ndarray:
    base_features = _candidate_features(selected_model)
    if candidate == "residualized_workload":
        train_resid = _residualize_workload(train, train)
        test_resid = _residualize_workload(train, test)
        features = STABLE_FEATURES + [f"resid_{feature}" for feature in WORKLOAD_FEATURES]
        model = _fit_model(train_resid, features, target)
        return _predict(model, test_resid, features)
    model = _fit_model(train, base_features, target)
    raw_train = _predict(model, train, base_features)
    raw_test = _predict(model, test, base_features)
    if candidate == "partial_pooling":
        shifts = _estimate_pitcher_shifts(train, raw_train, target)
        return _apply_shifts(test, raw_test, shifts)
    return raw_test


def _fold_audit(rows: pd.DataFrame, role: str, target: str, selected_model: str, train_years: tuple[int, ...], test_year: int) -> dict[str, Any]:
    eligible = _eligible(rows, role, target)
    train = eligible[eligible["year"].isin(train_years)].copy()
    test = eligible[eligible["year"].eq(test_year)].copy()
    if train.empty or test.empty or train[target].nunique() < 2 or test[target].nunique() < 2:
        return {"status": "insufficient_rows_or_classes", "train_rows": int(len(train)), "test_rows": int(len(test))}
    train_prevalence = float(train[target].mean())
    baseline = np.full(len(test), train_prevalence)
    candidates: dict[str, dict[str, Any]] = {"global": _metrics(test[target], baseline)}
    predictions: dict[str, np.ndarray] = {}
    for candidate in ("global", "partial_pooling", "residualized_workload"):
        predictions[candidate] = _score_candidate(train, test, target, selected_model, candidate)
        candidates[candidate] = _metrics(test[target], predictions[candidate])
    for candidate in ("partial_pooling", "residualized_workload"):
        ap_delta = float(candidates[candidate]["average_precision"] or 0.0) - float(candidates["global"]["average_precision"] or 0.0)
        brier_delta = float(candidates[candidate]["brier"] or 0.0) - float(candidates["global"]["brier"] or 0.0)
        log_delta = float(candidates[candidate]["log_loss"] or 0.0) - float(candidates["global"]["log_loss"] or 0.0)
        candidates[candidate]["vs_global"] = {
            "average_precision_delta": _number(ap_delta),
            "brier_delta": _number(brier_delta),
            "log_loss_delta": _number(log_delta),
            "non_worse_probability_error": bool(brier_delta <= 0 and log_delta <= 0),
        }
    return {
        "status": "fit",
        "train_years": list(train_years),
        "test_year": test_year,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_prevalence": _number(train_prevalence),
        "candidates": candidates,
    }


def _slice21(panel: pd.DataFrame, role: str, target: str, selected_model: str) -> dict[str, Any]:
    folds: list[dict[str, Any]] = []
    for train_years, test_year in FOLDS:
        fold = _fold_audit(panel, role, target, selected_model, train_years, test_year)
        folds.append(fold)
    candidate_summary: dict[str, Any] = {}
    for candidate in ("partial_pooling", "residualized_workload"):
        valid = [fold for fold in folds if fold.get("status") == "fit" and fold["candidates"].get(candidate)]
        wins = [
            fold["candidates"][candidate]["vs_global"]["non_worse_probability_error"]
            and float(fold["candidates"][candidate]["vs_global"]["average_precision_delta"] or 0.0) >= 0
            for fold in valid
        ]
        candidate_summary[candidate] = {
            "valid_folds": len(valid),
            "non_worse_and_nonnegative_ap_folds": int(sum(wins)),
            "consistent_across_at_least_two_folds": bool(sum(wins) >= 2),
        }
    return {"status": "fit", "selected_model": selected_model, "folds": folds, "candidate_summary": candidate_summary}


def _slice22(slice21: dict[str, Any]) -> dict[str, Any]:
    decisions: dict[str, dict[str, Any]] = {}
    for role, targets in slice21["roles"].items():
        decisions[role] = {}
        for target, audit in targets.items():
            if audit.get("status") != "fit":
                decisions[role][target] = {"decision": "insufficient_evidence", "reason": audit.get("status")}
                continue
            summary = audit["candidate_summary"]
            eligible = [name for name, value in summary.items() if value["consistent_across_at_least_two_folds"]]
            if not eligible:
                decisions[role][target] = {
                    "decision": "keep_slice14",
                    "candidate": None,
                    "reason": "No challenger was non-worse than global across at least two rolling-origin folds.",
                }
                continue
            candidate = min(
                eligible,
                key=lambda name: -summary[name]["non_worse_and_nonnegative_ap_folds"],
            )
            decisions[role][target] = {
                "decision": "retain_research_challenger",
                "candidate": candidate,
                "reason": "Candidate is robust across at least two forward folds, but remains research-only pending 2027 prospective validation.",
                "supporting_folds": summary[candidate]["non_worse_and_nonnegative_ap_folds"],
            }
    return {
        "status": "research_only_decision",
        "decisions": decisions,
        "production_integration": "closed",
        "formal_model_replaced": False,
        "prospective_2027_required": True,
        "policy": {
            "minimum_supporting_folds": 2,
            "require_non_worse_brier_and_log_loss": True,
            "require_nonnegative_average_precision_delta": True,
            "no_2026_only_promotion": True,
        },
    }


def refresh_performance_state_v2_slice21_22(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    panel = _load_states(root)
    slice21_roles: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        slice21_roles[role] = {}
        for target in TARGETS:
            selected_model = "context_workload"
            try:
                slice16 = json.loads((root / "derived" / "performance_state_v2_slice16.json").read_text(encoding="utf-8"))
                selected_model = slice16["roles"][role][target].get("selected_model", selected_model)
            except (FileNotFoundError, KeyError, json.JSONDecodeError):
                pass
            slice21_roles[role][target] = _slice21(panel, role, target, selected_model)
    slice21 = {"status": "research_only", "roles": slice21_roles}
    audit = {
        "version": SLICE21_22_VERSION,
        "status": "research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "development_years": list(DEVELOPMENT_YEARS),
        "folds": [{"train_years": list(train), "test_year": test} for train, test in FOLDS],
        "diagnostic_year": 2026,
        "prospective_year": 2027,
        "slice21_rolling_origin": slice21,
        "slice22_freeze_decision": _slice22(slice21),
        "warnings": [
            "The 2026 fold is a fixed diagnostic, not untouched prospective validation.",
            "Slice 22 is a research decision report; it does not replace Slice 14 or open production integration.",
        ],
    }
    _write_json_atomic(audit, audit_path(root))
    return audit


def get_performance_state_v2_slice21_22_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slices 21–22 have not been built.")
    return json.loads(path.read_text(encoding="utf-8"))
