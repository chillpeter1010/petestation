from __future__ import annotations

from pathlib import Path

from app.api.schemas.performance_state import PerformanceStateV2Slice16AuditResponse
from app.services import performance_state_v2_slice16_service as service


def test_baseline_only_can_never_pass_release_gate() -> None:
    metrics = {"average_precision": 0.20, "brier": 0.16, "log_loss": 0.50}
    baseline = {"average_precision": 0.20, "brier": 0.16, "log_loss": 0.50}
    result = service._gate(
        metrics,
        baseline,
        variation=0.0,
        bootstrap={"average_precision_delta_95_interval": [0.0, 0.0], "brier_delta_95_interval": [0.0, 0.0]},
    )
    assert result["status"] == "baseline_only_not_supported"
    assert result["passed"] is False


def test_real_slice16_audit_is_schema_valid_and_diagnostic_only() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    path = service.slice16_audit_path(root)
    if not path.exists():
        service.refresh_performance_state_v2_slice16(root)
    audit = service.get_performance_state_v2_slice16_audit(root)
    parsed = PerformanceStateV2Slice16AuditResponse(**audit)
    assert parsed.development_years == [2023, 2024]
    assert parsed.selection_year == 2025
    assert parsed.diagnostic_year == 2026
    assert parsed.gate_policy["baseline_only_is_not_success"] is True
    assert parsed.gate_policy["production_integration"] == "closed"
    assert parsed.prediction_rows > 0
