import json

import pandas as pd

from app.services import batter_swing_timing_service as service


def _row(player_id: int, pitch: str, swings: int, **values):
    return {
        "id": player_id,
        "player_id": player_id,
        "name": "Example, Hitter",
        "team_name": "Yankees",
        "api_pitch_type": pitch,
        "pitch_code": pitch,
        "bat_side_formatted": "R",
        "batter_side": "R",
        "n_swings": swings,
        "miss_distance": values.get("miss_distance", 2.0),
        "whiff_rate": values.get("whiff_rate", 0.2),
        "perfect_percent": values.get("perfect_percent", 0.2),
        "flawed_percent": values.get("flawed_percent", 0.1),
        "competitive_percent": values.get("competitive_percent", 0.9),
        "tied_up_percent": values.get("tied_up_percent", 0.1),
        "avg_x_tied_up": values.get("avg_x_tied_up", -6.0),
        "centered_percent": values.get("centered_percent", 0.7),
        "flailed_percent": values.get("flailed_percent", 0.2),
        "avg_x_flail": values.get("avg_x_flail", 7.0),
        "early_percent": values.get("early_percent", 0.2),
        "avg_y_early": values.get("avg_y_early", 10.0),
        "on_time_percent": values.get("on_time_percent", 0.6),
        "late_percent": values.get("late_percent", 0.2),
        "avg_y_late": values.get("avg_y_late", -10.0),
        "over_percent": values.get("over_percent", 0.1),
        "avg_z_over": values.get("avg_z_over", -3.0),
        "lined_up_percent": values.get("lined_up_percent", 0.5),
        "under_percent": values.get("under_percent", 0.4),
        "avg_z_under": values.get("avg_z_under", 3.0),
    }


def test_aggregate_batters_uses_metric_specific_weights():
    frame = pd.DataFrame([
        _row(1, "FF", 100, miss_distance=2.0, whiff_rate=0.1, perfect_percent=0.3, early_percent=0.1, avg_y_early=8.0),
        _row(1, "SL", 50, miss_distance=8.0, whiff_rate=0.4, perfect_percent=0.1, early_percent=0.4, avg_y_early=14.0),
    ])

    row = service._aggregate_batters(frame, {1: ("Hitter Example", "NYY", 240)})[0]

    assert row.n_swings == 150
    assert row.perfect_pct == 23.333
    assert row.miss_distance == 6.0
    assert row.avg_early_ms == 12.0
    assert row.pitch_types == ["FF", "SL"]
    assert row.team == "NYY"
    assert row.plate_appearances == 240


def test_aggregate_batters_ignores_placeholder_identity_name():
    frame = pd.DataFrame([_row(1, "FF", 100)])

    row = service._aggregate_batters(frame, {1: ("Batter 1", "NYY", 240)})[0]

    assert row.name == "Hitter Example"


def test_get_batter_swing_timing_filters_and_qualifies(tmp_path, monkeypatch):
    data_dir = tmp_path
    cache = service.timing_cache_path(2025, "R", data_dir)
    cache.parent.mkdir(parents=True)
    pd.DataFrame([
        _row(1, "FF", 80),
        _row(1, "SL", 40),
        _row(2, "FF", 30),
    ]).drop(columns=["player_id", "pitch_code", "batter_side"]).to_csv(cache, index=False)
    service.timing_meta_path(2025, "R", data_dir).write_text(
        json.dumps({"generated_at": "2026-08-22T10:00:00", "source_url": "https://example.test"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(service, "list_batter_leaderboard", lambda year: [
        {"player_id": 1, "name": "First Hitter", "team": "NYY", "plate_appearances": 180},
        {"player_id": 2, "name": "Second Hitter", "team": "BOS", "plate_appearances": 80},
    ])

    response = service.get_batter_swing_timing(
        year=2025,
        pitch_group="fastball",
        pitcher_hand="R",
        batter_side="R",
        minimum_swings=50,
        minimum_plate_appearances=100,
        data_dir=data_dir,
    )

    assert response.matched_swings == 110
    assert response.matched_hitters == 2
    assert response.qualified_hitters == 1
    assert response.leaderboard[0].name == "First Hitter"
    assert response.data_updated_at == "2026-08-22"
    assert response.leaderboard[0].plate_appearances == 180

    team_response = service.get_batter_swing_timing(
        year=2025,
        pitch_group="fastball",
        pitcher_hand="R",
        batter_side="R",
        batter_team="BOS",
        minimum_swings=0,
        minimum_plate_appearances=100,
        data_dir=data_dir,
    )
    assert team_response.matched_swings == 30
    assert team_response.matched_hitters == 1
    assert team_response.qualified_hitters == 0
    assert team_response.league is not None


def test_missing_cache_returns_warning(tmp_path):
    response = service.get_batter_swing_timing(year=2024, data_dir=tmp_path)

    assert response.leaderboard == []
    assert response.warnings == ["No batter Swing Timing cache is available for 2024 (All pitchers)."]


def test_apply_player_context_adds_age_and_all_season_teams(tmp_path, monkeypatch):
    row = service.SwingTimingLeaderboardRow(batter_id=1, name="Example Hitter", team="LAD")
    monkeypatch.setattr(service, "_load_player_context", lambda *_: {1: (29, ("AZ", "LAD"))})

    enriched = service._apply_player_context([row], 2026, tmp_path)[0]

    assert enriched.age == 29
    assert enriched.teams == ["AZ", "LAD"]
    assert row.age is None
    assert row.teams == []
