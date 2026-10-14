from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.core.config import settings
from app.services.performance_state_service import ROLES
from app.services.performance_state_v2_service import TARGETS
from app.services.performance_state_v2_slice14_service import (
    SLICE14_VERSION,
    slice14_audit_path,
    slice14_prediction_path,
)
from app.services.performance_state_v2_slice18_20_service import (
    SLICE18_20_VERSION,
    audit_path as slice18_20_audit_path,
    slice18_prediction_path,
    slice19_prediction_path,
)
from app.services.performance_state_v2_slice21_22_service import audit_path as slice21_22_audit_path
from app.services.performance_state_v2_strict_replay_service import audit_path as strict_replay_audit_path


LAB_MODEL_VERSION = "performance_state_v2_lab_primary_slice14_shadow18_19_v1"
TARGET_LABELS = {
    "process_collapse": "Process Collapse",
    "result_collapse": "Result Collapse",
    "return_to_baseline": "Return to Baseline",
    "strong_rebound": "Strong Rebound",
    "onset_collapse": "Onset Collapse",
    "persistent_collapse": "Persistent Collapse",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Performance State v2 lab artifact not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_predictions(path: Path, year: int, role: str, target: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Performance State v2 lab prediction artifact not found: {path}")
    with duckdb.connect() as connection:
        frame = connection.execute(
            "SELECT * FROM read_parquet(?) WHERE year = ? AND role = ? AND target = ?",
            [str(path), int(year), role, target],
        ).fetchdf()
    if frame.empty:
        return frame
    frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce")
    return frame.sort_values(["pitcher_id", "game_date", "game_pk"], kind="stable").reset_index(drop=True)


def _finite(value: Any) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return float(numeric) if pd.notna(numeric) and np.isfinite(float(numeric)) else None


def _aggregate(frame: pd.DataFrame, probability_column: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for pitcher_id, group in frame.groupby("pitcher_id", sort=False):
        group = group.sort_values(["game_date", "game_pk"], kind="stable")
        probabilities = pd.to_numeric(group[probability_column], errors="coerce")
        actual = group["actual"].fillna(False).astype(bool)
        latest = group.iloc[-1]
        rows.append({
            "pitcher_id": int(pitcher_id),
            "pitcher_name": str(latest.get("pitcher_name") or f"Pitcher {pitcher_id}"),
            "team": None if pd.isna(latest.get("team")) else str(latest.get("team")),
            "role": str(latest.get("role")),
            "appearances": int(group["game_pk"].nunique()),
            "eligible_forecasts": int(probabilities.notna().sum()),
            "latest_game_date": pd.Timestamp(latest["game_date"]).date().isoformat(),
            "latest_probability": _finite(latest[probability_column]) or 0.0,
            "season_mean_probability": _finite(probabilities.mean()) or 0.0,
            "actual_events": int(actual.sum()),
            "actual_rate": _finite(actual.mean()) or 0.0,
            "latest_actual": bool(latest.get("actual", False)),
        })
    return pd.DataFrame(rows)


def _latest_probability_map(frame: pd.DataFrame, probability_column: str) -> pd.DataFrame:
    aggregate = _aggregate(frame, probability_column)
    if aggregate.empty:
        return aggregate
    return aggregate[[
        "pitcher_id", "latest_probability", "season_mean_probability"
    ]].rename(columns={
        "latest_probability": "latest",
        "season_mean_probability": "mean",
    })


def _selected_layer(audit: dict[str, Any], role: str, target: str) -> str:
    return str(
        audit.get("slice14b", {})
        .get("forecasts", {})
        .get("roles", {})
        .get(role, {})
        .get(target, {})
        .get("selected_layer", "D_gas_har")
    )


def _role_target(audit: dict[str, Any], section: str, role: str, target: str) -> dict[str, Any]:
    return (
        audit.get(section, {})
        .get("roles", {})
        .get(role, {})
        .get(target, {})
    )


def _freeze_target(audit: dict[str, Any], role: str, target: str) -> dict[str, Any]:
    return (
        audit.get("slice22_freeze_decision", {})
        .get("decisions", {})
        .get(role, {})
        .get(target, {})
    )


def get_performance_state_v2_lab(
    year: int = 2026,
    role: str = "SP",
    target: str = "process_collapse",
    minimum_forecasts: int = 1,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    role = role.upper()
    target = target.lower()
    if role not in ROLES:
        raise ValueError(f"Unsupported role: {role}. Expected one of {sorted(ROLES)}.")
    if target not in TARGETS:
        raise ValueError(f"Unsupported target: {target}. Expected one of {sorted(TARGETS)}.")
    if int(year) != 2026:
        raise FileNotFoundError("The v2 lab primary currently has a frozen 2026 diagnostic only; use the v1 fallback for other years.")
    if minimum_forecasts < 1:
        raise ValueError("minimum_forecasts must be at least 1")

    audit14 = _read_json(slice14_audit_path(root))
    primary = _read_predictions(slice14_prediction_path(root), year, role, target)
    primary_rows = _aggregate(primary, "probability")
    if primary_rows.empty:
        raise FileNotFoundError(f"No Slice 14 rows are available for {year} {role} {target}.")
    primary_rows = primary_rows[primary_rows["eligible_forecasts"].ge(int(minimum_forecasts))].copy()

    shadow_frames: dict[str, pd.DataFrame] = {}
    for name, path in (("slice18", slice18_prediction_path(root)), ("slice19", slice19_prediction_path(root))):
        try:
            shadow_frames[name] = _read_predictions(path, year, role, target)
        except FileNotFoundError:
            shadow_frames[name] = pd.DataFrame()

    for name, frame in shadow_frames.items():
        shadow = _latest_probability_map(frame, "probability")
        if shadow.empty:
            continue
        primary_rows = primary_rows.merge(shadow, on="pitcher_id", how="left", suffixes=("", f"_{name}"))
        primary_rows = primary_rows.rename(columns={
            "latest": f"shadow_{name}_latest_probability",
            "mean": f"shadow_{name}_season_mean_probability",
        })
        primary_rows[f"shadow_{name}_delta"] = (
            primary_rows[f"shadow_{name}_latest_probability"] - primary_rows["latest_probability"]
        )
    for name in ("slice18", "slice19"):
        for column in (
            f"shadow_{name}_latest_probability",
            f"shadow_{name}_season_mean_probability",
            f"shadow_{name}_delta",
        ):
            if column not in primary_rows:
                primary_rows[column] = None

    primary_rows = primary_rows.sort_values(
        ["latest_probability", "season_mean_probability", "pitcher_name"],
        ascending=[False, False, True],
        kind="stable",
    ).reset_index(drop=True)
    primary_rows.insert(0, "rank", np.arange(1, len(primary_rows) + 1, dtype=int))
    primary_rows["latest_game_date"] = primary_rows["latest_game_date"].astype(str)
    rows = primary_rows.to_dict(orient="records")

    audit1820 = _read_json(slice18_20_audit_path(root))
    audit2122 = _read_json(slice21_22_audit_path(root))
    strict = _read_json(strict_replay_audit_path(root))
    max_date = primary["game_date"].max()
    subgroup = _role_target(audit1820, "slice20_subgroup_calibration", role, target)
    freeze = _freeze_target(audit2122, role, target)
    warnings = [
        "Research lab only: this does not change /leaderboards, formal player pages, or production model contracts.",
        "Primary probabilities come from Slice 14 role-target-specific selection; Slice 18 and Slice 19 are displayed as shadow challengers.",
        "The existing player timeline remains the v1 endpoint fallback until a v2 point-in-time player artifact is exposed.",
        "2026 is a retrospective diagnostic in this lab; it is not untouched prospective evidence.",
    ]
    return {
        "year": int(year),
        "role": role,
        "target": target,
        "target_label": TARGET_LABELS.get(target, target.replace("_", " ").title()),
        "model_version": LAB_MODEL_VERSION,
        "status": "research_primary",
        "data_as_of": max_date.date().isoformat() if pd.notna(max_date) else None,
        "evaluation_status": "slice14_primary_with_slice18_19_shadow",
        "selected_primary_layer": _selected_layer(audit14, role, target),
        "rows": rows,
        "primary_source": {
            "slice": "14",
            "version": audit14.get("slice14b", {}).get("version", SLICE14_VERSION),
            "artifact": slice14_prediction_path(root).name,
            "prediction_rows": int(len(primary)),
            "eligible_pitchers": int(len(primary_rows)),
            "selection": (
                audit14.get("slice14b", {})
                .get("forecasts", {})
                .get("roles", {})
                .get(role, {})
                .get(target, {})
            ),
        },
        "shadow": {
            "slice18": {
                "version": SLICE18_20_VERSION,
                "artifact": slice18_prediction_path(root).name,
                "prediction_rows": int(len(shadow_frames["slice18"])),
            },
            "slice19": {
                "version": SLICE18_20_VERSION,
                "artifact": slice19_prediction_path(root).name,
                "prediction_rows": int(len(shadow_frames["slice19"])),
            },
        },
        "subgroup_monitor": subgroup,
        "freeze_decision": freeze,
        "strict_replay": {
            "status": strict.get("status"),
            "integration_gate": strict.get("integration_gate"),
            "model_fingerprint": strict.get("model_fingerprint"),
            "prediction_rows": strict.get("prediction_rows"),
        },
        "fallback": {
            "available": True,
            "endpoint": "/api/performance-state/player",
            "model_version": "collapse_rebound_forecast_v1",
        },
        "warnings": warnings,
    }
