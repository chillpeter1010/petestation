from __future__ import annotations

from pathlib import Path

from app.api.schemas.performance_state import PerformanceStateV2Slice21To22AuditResponse
from app.services import performance_state_v2_slice21_22_service as service


def test_slice22_never_replaces_formal_model() -> None:
    source = {
        "roles": {
            "SP": {
                "process_collapse": {
                    "status": "fit",
                    "candidate_summary": {
                        "partial_pooling": {"consistent_across_at_least_two_folds": False, "non_worse_and_nonnegative_ap_folds": 1},
                        "residualized_workload": {"consistent_across_at_least_two_folds": True, "non_worse_and_nonnegative_ap_folds": 2},
                    },
                }
            }
        }
    }
    result = service._slice22(source)
    decision = result["decisions"]["SP"]["process_collapse"]
    assert decision["decision"] == "retain_research_challenger"
    assert result["formal_model_replaced"] is False
    assert result["production_integration"] == "closed"


def test_real_slice21_22_audit_is_schema_valid_and_forward_only() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    path = service.audit_path(root)
    if not path.exists():
        service.refresh_performance_state_v2_slice21_22(root)
    audit = service.get_performance_state_v2_slice21_22_audit(root)
    parsed = PerformanceStateV2Slice21To22AuditResponse(**audit)
    assert [(fold["train_years"], fold["test_year"]) for fold in parsed.folds] == [
        ([2023], 2024),
        ([2023, 2024], 2025),
        ([2023, 2024, 2025], 2026),
    ]
    assert parsed.slice22_freeze_decision["formal_model_replaced"] is False
    assert parsed.slice22_freeze_decision["production_integration"] == "closed"
