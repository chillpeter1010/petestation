import pandas as pd
import pytest

from app.services.personal_service import build_game_log, build_pitcher_wpa_games


def test_build_game_log_groups_by_game():
    frame = pd.DataFrame(
        [
            {"game_date": "2025-01-01", "game_pk": 1, "release_speed": 90, "release_spin_rate": 2200, "at_bat_number": 1},
            {"game_date": "2025-01-01", "game_pk": 1, "release_speed": 92, "release_spin_rate": 2300, "at_bat_number": 2},
        ]
    )

    log = build_game_log(frame)

    assert log.loc[0, "pitches"] == 2
    assert log.loc[0, "batters"] == 2


def test_build_pitcher_wpa_games_flips_away_pitcher_home_wpa():
    frame = pd.DataFrame(
        [
            {
                "game_date": "2025-01-01",
                "game_pk": 1,
                "pitcher_team": "AWY",
                "home_team": "HME",
                "away_team": "AWY",
                "at_bat_number": 1,
                "pa_home_wpa": 0.1,
            }
        ]
    )

    games = build_pitcher_wpa_games(frame)

    assert games.loc[0, "game_wpa"] == pytest.approx(-0.1030875)
