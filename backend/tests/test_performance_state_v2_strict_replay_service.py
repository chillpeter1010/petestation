from __future__ import annotations

from pathlib import Path

from app.api.schemas.performance_state import PerformanceStateV2StrictReplayResponse
from app.services import performance_state_v2_strict_replay_service as service


def test_strict_replay_spec_is_deterministically_fingerprinted() -> None:
    payload = {"train_years": [2023, 2024], "calibration_year": 2025, "test_year": 2026}
    assert service._sha256_payload(payload) == service._sha256_payload(payload)
    assert service.STRICT_TEST_YEAR == 2026


def test_real_strict_replay_is_labeled_retrospective_and_closed() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    path = service.audit_path(root)
    if not path.exists():
        service.refresh_strict_2026_replay(root)
    audit = service.get_strict_2026_replay_audit(root)
    parsed = PerformanceStateV2StrictReplayResponse(**audit)
    assert parsed.status == "retrospective_holdout_replay"
    assert parsed.no_2026_model_selection is True
    assert parsed.integration_gate == "CLOSED"
    assert parsed.prediction_rows > 0
    assert any("not an untouched test" in warning for warning in parsed.warnings)
