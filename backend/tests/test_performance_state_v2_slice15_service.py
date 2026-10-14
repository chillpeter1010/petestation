from __future__ import annotations

from pathlib import Path

from app.api.schemas.performance_state import PerformanceStateV2Slice15AuditResponse
from app.services import performance_state_v2_slice15_service as service


def test_real_slice15_readiness_is_frozen_and_closed() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    audit = service.refresh_performance_state_v2_slice15(root)
    parsed = PerformanceStateV2Slice15AuditResponse(**audit)
    assert parsed.source_year == 2027
    assert parsed.frozen_model["model_refit_allowed"] is False
    assert parsed.frozen_model["thresholds_locked"] is True
    assert parsed.integration_gate["status"] == "CLOSED"
    assert parsed.prospective["prediction_rows"] == 0
    assert parsed.prospective["observation_mode"] == "prospective_append_only"


def test_slice15_audit_detects_frozen_input_changes(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    source_audit = service.slice14_audit_path(root)
    target_derived = tmp_path / "derived"
    target_derived.mkdir()
    (target_derived / source_audit.name).write_bytes(source_audit.read_bytes())
    audit = service.refresh_performance_state_v2_slice15(tmp_path)
    assert audit["dataset_status"] == "stale"
