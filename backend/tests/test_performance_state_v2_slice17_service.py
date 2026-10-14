from __future__ import annotations

from pathlib import Path

from app.api.schemas.performance_state import PerformanceStateV2Slice17AuditResponse
from app.services import performance_state_v2_slice17_service as service


def test_calibration_candidates_are_temporally_selected() -> None:
    truth = [0, 0, 0, 1, 1, 1] * 10
    raw = [0.10, 0.20, 0.30, 0.60, 0.70, 0.80] * 10
    selected, metrics, fitted = service._select_calibration(truth, raw)
    assert selected in {"raw", "platt", "isotonic"}
    assert set(metrics) == {"raw", "platt", "isotonic"}
    assert "calibrator" in fitted


def test_real_slice17_audit_is_schema_valid_and_diagnostic_only() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    path = service.slice17_audit_path(root)
    if not path.exists():
        service.refresh_performance_state_v2_slice17(root)
    audit = service.get_performance_state_v2_slice17_audit(root)
    parsed = PerformanceStateV2Slice17AuditResponse(**audit)
    assert parsed.development_years == [2023, 2024]
    assert parsed.selection_year == 2025
    assert parsed.diagnostic_year == 2026
    assert parsed.policy["production_integration"] == "closed"
    assert parsed.prediction_rows > 0
