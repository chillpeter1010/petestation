from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.performance_state_v2_slice14_service import (
    slice14_audit_path,
    slice14_prediction_path,
    slice14_state_path,
)
from app.services.performance_state_v2_service import YEARS, v2_warehouse_path, v2_audit_path


SLICE15_VERSION = "performance_state_2027_prospective_shadow_v1"
SOURCE_YEAR = 2027
MINIMUM_PROSPECTIVE_ROWS_PER_ROLE_TARGET = 250


def slice15_audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice15.json"


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def _frozen_inputs(root: Path) -> dict[str, Any]:
    paths = {
        "slice14_audit": slice14_audit_path(root),
        "slice14_predictions_2026": slice14_prediction_path(root),
        **{f"slice14_states_{year}": slice14_state_path(year, root) for year in YEARS},
        "slice11a_13_audit": v2_audit_path(root),
        **{f"warehouse_{year}": v2_warehouse_path(year, root) for year in YEARS},
    }
    return {
        key: {
            "path": str(path),
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else None,
            "modified_at_ns": path.stat().st_mtime_ns if path.exists() else None,
            "sha256": _sha256(path),
        }
        for key, path in paths.items()
    }


def _source_status(root: Path) -> dict[str, Any]:
    raw_path = get_season_duckdb_path(SOURCE_YEAR, root)
    warehouse = v2_warehouse_path(SOURCE_YEAR, root)
    return {
        "year": SOURCE_YEAR,
        "raw_pitch_source": str(raw_path),
        "raw_pitch_source_exists": raw_path.exists(),
        "v2_warehouse": str(warehouse),
        "v2_warehouse_exists": warehouse.exists(),
        "status": (
            "ready_for_materialization"
            if raw_path.exists() and not warehouse.exists()
            else "materialized_pending_frozen_scoring"
            if raw_path.exists() and warehouse.exists()
            else "awaiting_untouched_2027_source"
        ),
    }


def refresh_performance_state_v2_slice15(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    audit14 = slice14_audit_path(root)
    if not audit14.exists():
        raise FileNotFoundError("Performance State Slice 14A/B must be built before Slice 15.")
    source = _source_status(root)
    frozen_inputs = _frozen_inputs(root)
    missing_frozen = [key for key, value in frozen_inputs.items() if not value["exists"]]
    source_available = bool(source["raw_pitch_source_exists"])
    audit = {
        "version": SLICE15_VERSION,
        "status": "research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_status": source["status"],
        "source_year": SOURCE_YEAR,
        "source": source,
        "frozen_model": {
            "slice14_version": json.loads(audit14.read_text(encoding="utf-8")).get("version"),
            "training_years": [2023, 2024, 2025],
            "diagnostic_year": 2026,
            "prospective_year": SOURCE_YEAR,
            "model_refit_allowed": False,
            "thresholds_locked": True,
            "calibration_locked": True,
            "frozen_inputs": frozen_inputs,
        },
        "prospective": {
            "prediction_rows": 0,
            "observed_rows": 0,
            "role_target_rows": {},
            "minimum_rows_per_role_target": MINIMUM_PROSPECTIVE_ROWS_PER_ROLE_TARGET,
            "observation_mode": "prospective_append_only",
            "no_midseason_retuning": True,
        },
        "integration_gate": {
            "status": "CLOSED",
            "untouched_2027_required": True,
            "source_available": source_available,
            "frozen_inputs_complete": not missing_frozen,
            "minimum_rows_per_role_target": MINIMUM_PROSPECTIVE_ROWS_PER_ROLE_TARGET,
            "reason": (
                "2027 source is not available yet."
                if not source_available
                else "2027 source exists, but frozen scoring/materialization has not been run."
            ),
        },
        "warnings": [
            "This readiness refresh never fits or retunes a model.",
            "2027 must remain untouched until prospective append and post-game observation.",
            "Performance State estimates performance states; it does not diagnose fatigue, injury or health.",
        ],
        "dataset_status": "current" if not missing_frozen else "stale",
    }
    _write_json_atomic(audit, slice15_audit_path(root))
    return audit


def get_performance_state_v2_slice15_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = slice15_audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slice 15 has not been initialized.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    current_inputs = _frozen_inputs(root)
    saved_inputs = payload.get("frozen_model", {}).get("frozen_inputs", {})
    payload["dataset_status"] = "current" if current_inputs == saved_inputs else "stale"
    if payload["dataset_status"] == "stale":
        payload.setdefault("warnings", []).append("A frozen Slice 14 input changed after Slice 15 initialization; rebuild readiness before appending observations.")
    return payload
