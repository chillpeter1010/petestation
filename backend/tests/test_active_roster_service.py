from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.active_roster_service import (
    ACTIVE_ROSTER_STALE_AFTER_SECONDS,
    get_team_active_roster,
)


NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def official_payload() -> dict[str, object]:
    return {
        "roster": [
            {
                "person": {"id": 592450, "fullName": "Aaron Judge"},
                "jerseyNumber": "99",
                "position": {"code": "9", "name": "Outfielder", "type": "Outfielder"},
                "status": {"code": "A", "description": "Active"},
            },
            {
                "person": {"id": 543037, "fullName": "Gerrit Cole"},
                "jerseyNumber": "45",
                "position": {"code": "1", "name": "Pitcher", "type": "Pitcher"},
                "status": {"code": "A", "description": "Active"},
            },
        ]
    }


def test_live_active_roster_is_normalized_and_cached(tmp_path: Path) -> None:
    requested: list[str] = []

    def fetcher(url: str, timeout: int) -> dict[str, object]:
        requested.append(url)
        assert timeout == 12
        return official_payload()

    result = get_team_active_roster(2026, "nyy", data_dir=tmp_path, fetcher=fetcher, now=NOW)

    assert result.freshness == "fresh"
    assert result.team_id == 147
    assert result.roster_type == "active"
    assert result.source_as_of is None
    assert [player.player_id for player in result.players] == [592450, 543037]
    assert result.players[1].position_type == "Pitcher"
    assert result.players[1].status_code == "A"
    assert "rosterType=active" in requested[0]
    assert "season=2026" in requested[0]
    assert (tmp_path / "MLB2026" / "official_active_rosters" / "NYY.json").exists()


def test_fresh_disk_cache_avoids_duplicate_fetch(tmp_path: Path) -> None:
    get_team_active_roster(2026, "NYY", data_dir=tmp_path, fetcher=lambda *_args, **_kwargs: official_payload(), now=NOW)

    def unexpected_fetch(*_args, **_kwargs):
        raise AssertionError("fresh cache should not fetch")

    cached = get_team_active_roster(
        2026,
        "NYY",
        data_dir=tmp_path,
        fetcher=unexpected_fetch,
        now=NOW + timedelta(seconds=ACTIVE_ROSTER_STALE_AFTER_SECONDS),
    )
    assert cached.freshness == "fresh"
    assert cached.cache_age_seconds == ACTIVE_ROSTER_STALE_AFTER_SECONDS


def test_failed_refresh_uses_explicit_stale_cache(tmp_path: Path) -> None:
    get_team_active_roster(2026, "NYY", data_dir=tmp_path, fetcher=lambda *_args, **_kwargs: official_payload(), now=NOW)

    def failed_fetch(*_args, **_kwargs):
        raise TimeoutError("source timeout")

    stale = get_team_active_roster(
        2026,
        "NYY",
        data_dir=tmp_path,
        fetcher=failed_fetch,
        now=NOW + timedelta(hours=2),
    )
    assert stale.freshness == "stale"
    assert len(stale.players) == 2
    assert stale.cache_age_seconds == 7200
    assert "source timeout" in stale.meta.warnings[0]


def test_failed_refresh_without_cache_is_unavailable(tmp_path: Path) -> None:
    def failed_fetch(*_args, **_kwargs):
        raise TimeoutError("offline")

    unavailable = get_team_active_roster(2026, "AZ", data_dir=tmp_path, fetcher=failed_fetch, now=NOW)
    assert unavailable.freshness == "unavailable"
    assert unavailable.players == []
    assert unavailable.retrieved_at is None


def test_season_participant_data_cannot_enter_active_roster_contract(tmp_path: Path) -> None:
    malformed_season_data = {"players": [{"player_id": 1, "games": 20}]}
    result = get_team_active_roster(
        2026,
        "AZ",
        data_dir=tmp_path,
        fetcher=lambda *_args, **_kwargs: malformed_season_data,
        now=NOW,
    )
    assert result.freshness == "unavailable"
    assert result.players == []
    assert "does not contain a roster list" in result.meta.warnings[0]
