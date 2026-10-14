from __future__ import annotations

from pathlib import Path

from app.api.schemas.performance_state import PerformanceStateV2LabResponse
from app.services import performance_state_v2_lab_service as service


def test_v2_lab_uses_slice14_primary_and_shadow_artifacts() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    response = PerformanceStateV2LabResponse(**service.get_performance_state_v2_lab(data_dir=root))
    assert response.status == "research_primary"
    assert response.selected_primary_layer == "D_gas_har"
    assert response.rows
    assert response.primary_source["slice"] == "14"
    assert response.shadow["slice18"]["prediction_rows"] > 0
    assert response.shadow["slice19"]["prediction_rows"] > 0
    assert response.freeze_decision["decision"] == "keep_slice14"
    assert response.fallback["available"] is True


def test_v2_lab_rejects_non_diagnostic_year() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    try:
        service.get_performance_state_v2_lab(year=2025, data_dir=root)
    except FileNotFoundError as exc:
        assert "frozen 2026" in str(exc)
    else:
        raise AssertionError("The v2 lab should not present 2025 as a frozen primary board.")
