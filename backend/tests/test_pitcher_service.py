import math

import pandas as pd

from app.services import pitcher_service
from app.services.pitcher_service import build_pitcher_pool, pitcher_pool_to_options


def test_build_pitcher_pool_filters_starters_and_formats_options():
    player_master = pd.DataFrame(
        [
            {"player_id": 1, "player_name": "Ace Starter", "roles": "pitcher", "pitcher_teams_2026": "AAA"},
            {"player_id": 2, "player_name": "Late Reliever", "roles": "pitcher", "pitcher_teams_2026": "BBB"},
            {"player_id": 3, "player_name": "Position Player", "roles": "batter", "pitcher_teams_2026": "CCC"},
        ]
    )
    appearances = pd.DataFrame(
        [
            {"player_id": 1, "G": 10, "GS": 8},
            {"player_id": 2, "G": 20, "GS": 1},
        ]
    )

    pool = build_pitcher_pool(player_master, appearances, year=2026, role="SP")
    options = pitcher_pool_to_options(pool)

    assert len(options) == 1
    assert options[0].value == 1
    assert options[0].label == "Ace Starter (AAA)"
    assert options[0].role == "SP"
    assert math.isclose(options[0].start_rate or 0, 0.8)


def test_list_pitcher_leaderboard_includes_average_starter_game_score(monkeypatch):
    player_master = pd.DataFrame(
        [
            {"player_id": 1, "player_name": "Ace Starter", "roles": "pitcher", "pitcher_teams_2026": "AAA"},
            {"player_id": 2, "player_name": "Long Reliever", "roles": "pitcher", "pitcher_teams_2026": "AAA"},
        ]
    )
    appearances = pd.DataFrame(
        [
            {"player_id": 1, "G": 2, "GS": 2},
            {"player_id": 2, "G": 2, "GS": 0},
        ]
    )
    game_lines = pd.DataFrame(
        [
            {
                "game_pk": 10,
                "team": "AAA",
                "pitcher_id": 1,
                "ip": 6.0,
                "hits": 3,
                "runs": 1,
                "earned_runs": 1,
                "walks": 1,
                "strikeouts": 6,
                "pitches": 90,
                "batters_faced": 24,
            },
            {
                "game_pk": 10,
                "team": "AAA",
                "pitcher_id": 2,
                "ip": 1.0,
                "hits": 0,
                "runs": 0,
                "earned_runs": 0,
                "walks": 0,
                "strikeouts": 1,
                "pitches": 12,
                "batters_faced": 3,
            },
            {
                "game_pk": 11,
                "team": "AAA",
                "pitcher_id": 1,
                "ip": 5.0,
                "hits": 5,
                "runs": 2,
                "earned_runs": 2,
                "walks": 2,
                "strikeouts": 4,
                "pitches": 82,
                "batters_faced": 22,
            },
        ]
    )

    monkeypatch.setattr(
        pitcher_service,
        "load_pitcher_master_and_appearances",
        lambda year, data_dir: (player_master, appearances),
    )
    monkeypatch.setattr(pitcher_service, "_load_pitcher_game_lines", lambda year: game_lines)
    monkeypatch.setattr(
        pitcher_service,
        "_load_pitcher_home_runs",
        lambda year: pd.DataFrame(columns=["pitcher_id", "home_runs"]),
    )

    rows = pitcher_service.list_pitcher_leaderboard(2026, role="SP")

    assert len(rows) == 1
    assert rows[0].name == "Ace Starter"
    assert rows[0].avg_game_score == 59.0
