from pathlib import Path

import pandas as pd

from app.services.starter_reference_service import build_starter_br, build_starter_dashboard


def sample_sources():
    official = pd.DataFrame([{
        "MLBAMID": 10, "Name": "Test Starter", "Team": "NYY", "Age": 28,
        "W": 1, "L": 0, "SV": 0, "G": 2, "GS": 2, "IP": 12.0,
        "K/9": 9.0, "BB/9": 1.5, "HR/9": 0.75, "ERA": 2.25, "CG": 0, "SHO": 0,
    }])
    pitches = pd.DataFrame([
        {"game_pk": 1, "game_date": "2026-04-01", "pitcher": 10, "player_name": "Starter, Test", "pitcher_team": "NYY", "home_team": "NYY", "away_team": "BOS", "inning": 1, "inning_topbot": "Top", "at_bat_number": 1, "pitch_number": 1, "pitch_type": "FF", "release_speed": 95.0, "events": "field_out", "bb_type": "ground_ball", "post_home_score": 5, "post_away_score": 2},
        {"game_pk": 1, "game_date": "2026-04-01", "pitcher": 10, "player_name": "Starter, Test", "pitcher_team": "NYY", "home_team": "NYY", "away_team": "BOS", "inning": 6, "inning_topbot": "Top", "at_bat_number": 20, "pitch_number": 1, "pitch_type": "FF", "release_speed": 94.0, "events": "strikeout", "bb_type": None, "post_home_score": 5, "post_away_score": 2},
        {"game_pk": 2, "game_date": "2026-04-07", "pitcher": 10, "player_name": "Starter, Test", "pitcher_team": "NYY", "home_team": "TOR", "away_team": "NYY", "inning": 1, "inning_topbot": "Bottom", "at_bat_number": 1, "pitch_number": 1, "pitch_type": "FF", "release_speed": 96.0, "events": "home_run", "bb_type": "fly_ball", "post_home_score": 3, "post_away_score": 4},
    ])
    lines = pd.DataFrame([
        {"game_pk": 1, "game_date": "2026-04-01", "team": "NYY", "home_away": "home", "pitcher_id": 10, "pitcher_name": "Test Starter", "ip": "6.0", "hits": 4, "runs": 2, "earned_runs": 2, "walks": 1, "strikeouts": 7, "pitches": 92, "batters_faced": 23},
        {"game_pk": 2, "game_date": "2026-04-07", "team": "NYY", "home_away": "away", "pitcher_id": 10, "pitcher_name": "Test Starter", "ip": "5.2", "hits": 5, "runs": 3, "earned_runs": 3, "walks": 2, "strikeouts": 6, "pitches": 101, "batters_faced": 24},
    ])
    return official, pitches, lines


def test_starter_reference_uses_local_data_through_date(tmp_path: Path):
    official, pitches, lines = sample_sources()

    dashboard = build_starter_dashboard(2026, official, pitches, lines, tmp_path)
    starter_br = build_starter_br(2026, official, pitches, lines)

    assert dashboard.iloc[0]["GS"] == 2
    assert dashboard.iloc[0]["IP"] == "11.2"
    assert starter_br.iloc[0]["QS"] == 1
    assert starter_br.iloc[0]["80-99"] == 1
    assert starter_br.iloc[0]["100-119"] == 1
    assert starter_br.iloc[0]["Max"] == 101
