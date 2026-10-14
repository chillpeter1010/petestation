from pathlib import Path

from app.api.schemas.common import PitcherLeaderboardRow
from app.api.schemas.pitcher_metric_explorer import PitcherMetricExplorerResponse
from app.services import pitcher_metric_explorer_service as service


def _basic_row(player_id: int, role: str = "SP") -> PitcherLeaderboardRow:
    return PitcherLeaderboardRow(
        player_id=player_id,
        name="Test Pitcher",
        team="SEA",
        role=role,
        games=20,
        starts=20 if role == "SP" else 0,
        relief_games=0 if role == "SP" else 20,
        ip=100.0,
        era=3.25,
        hits=80,
        runs=40,
        earned_runs=36,
        walks=25,
        strikeouts=120,
        home_runs=12,
        pitches=1600,
        batters_faced=400,
        avg_game_score=56.0,
        avg_pitches=80.0,
        whip=1.05,
        strikeout_rate=0.30,
        walk_rate=0.0625,
    )


def test_metric_explorer_joins_same_pitcher_season_and_keeps_missing_null(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(service, "list_pitcher_leaderboard", lambda **_: [_basic_row(1), _basic_row(2, "RP")])
    monkeypatch.setattr(service, "_load_dashboard_metrics", lambda *_: {1: {"fip": 3.10, "war": 2.5}})
    monkeypatch.setattr(service, "get_stuff_leaderboard", lambda **_: {
        "data_as_of": "2026-09-30", "cache_status": "current", "warnings": [],
        "rows": [{"player_id": 1, "stuff_plus": 110, "location_plus": 102, "pitching_plus": 106}],
    })
    monkeypatch.setattr(service, "get_stamina_leaderboard", lambda **_: {
        "data_as_of": "2026-09-30",
        "rows": [{"pitcher_id": 1, "stamina_plus": 104, "quality_game_stamina_plus": 103,
                  "physical_stability_plus": 99, "command_retention_plus": 101,
                  "fastball_stamina_plus": 105, "breaking_stamina_plus": None,
                  "offspeed_stamina_plus": 100, "reliability": 0.91}],
    })

    payload = service._build_metric_explorer(2026, tmp_path)
    parsed = PitcherMetricExplorerResponse(**payload)

    assert len(parsed.rows) == 2
    starter = parsed.rows[0]
    reliever = parsed.rows[1]
    assert starter.metrics["k_pct"] == 30.0
    assert starter.metrics["k_minus_bb_pct"] == 23.75
    assert starter.metrics["fip"] == 3.10
    assert starter.metrics["stuff_plus"] == 110.0
    assert starter.metrics["stamina_plus"] == 104.0
    assert starter.metrics["breaking_stamina_plus"] is None
    assert reliever.metrics["fip"] is None
    assert reliever.metrics["stuff_plus"] is None
    assert reliever.metrics["stamina_plus"] is None


def test_number_preserves_percent_scale_and_nulls():
    assert service._number("78.2%", percent=True) == 78.2
    assert service._number(0.782, percent=True) == 78.2
    assert service._number("-") is None
