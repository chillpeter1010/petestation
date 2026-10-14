from __future__ import annotations

from pathlib import Path

from app.api.schemas.performance_state import PerformanceStateV2Slice18To20AuditResponse
from app.services import performance_state_v2_slice18_20_service as service


def test_partial_pooling_selection_requires_non_worse_selection_metrics() -> None:
    base = service._metrics([0, 0, 1, 1], [0.2, 0.3, 0.7, 0.8])
    pooled = service._metrics([0, 0, 1, 1], [0.25, 0.25, 0.75, 0.75])
    assert service._select_pooling([0, 0, 1, 1], [0.2, 0.3, 0.7, 0.8], [0.25, 0.25, 0.75, 0.75]) == "partial_pooling"
    assert base["brier"] is not None and pooled["brier"] is not None


def test_real_slice18_20_audit_is_schema_valid_and_closed() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    path = service.audit_path(root)
    if not path.exists():
        service.refresh_performance_state_v2_slice18_20(root)
    audit = service.get_performance_state_v2_slice18_20_audit(root)
    parsed = PerformanceStateV2Slice18To20AuditResponse(**audit)
    assert parsed.development_years == [2023, 2024]
    assert parsed.selection_year == 2025
    assert parsed.diagnostic_year == 2026
    assert parsed.policy["production_integration"] == "closed"
    assert parsed.slice18_partial_pooling["prediction_rows"] > 0
    assert parsed.slice19_workload_bias_sensitivity["prediction_rows"] > 0
