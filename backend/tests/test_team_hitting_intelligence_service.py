from __future__ import annotations

from app.services.team_hitting_intelligence_service import get_team_hitting_intelligence


def test_team_hitting_intelligence_builds_compact_team_payload() -> None:
    payload = get_team_hitting_intelligence(2026, "AZ")

    assert payload.team_id == "AZ"
    assert 1 <= len(payload.lineup) <= 9
    assert len(payload.hitters) >= len(payload.lineup)
    assert [family.family for family in payload.pitch_families] == ["fastball", "breaking", "offspeed"]
    assert payload.team_profile.swings > 0
    assert payload.league_profile.swings >= payload.team_profile.swings
    assert all(row.batter_id > 0 and row.name for row in payload.hitters)


def test_team_hitting_intelligence_rejects_unknown_team() -> None:
    try:
        get_team_hitting_intelligence(2026, "NOPE")
    except ValueError as exc:
        assert "Unsupported MLB team" in str(exc)
    else:
        raise AssertionError("Expected an unsupported team to raise ValueError")
