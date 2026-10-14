import pandas as pd

from app.api.schemas.comparison import ComparisonMetric

from app.services import personal_service
from app.services.personal_service import build_pitch_type_matrix, find_pitcher_row, normalize_personal_name_frame


def test_normalize_personal_name_frame_handles_last_first_names():
    frame = pd.DataFrame([{"last_name, first_name": "Webb, Logan", "player_id": 657277}])

    normalized = normalize_personal_name_frame(frame)

    assert normalized.loc[0, "Name"] == "Logan Webb"
    assert normalized.loc[0, "MLBAMID"] == 657277
    assert normalized.loc[0, "name_key"] == "logan webb"


def test_build_pitch_type_matrix_uses_pitcher_id_match():
    frame = pd.DataFrame(
        [
            {
                "Name": "Logan Webb",
                "MLBAMID": 657277,
                "name_key": "logan webb",
                "Stf+ FA": 101.5,
                "Loc+ FA": 99.2,
                "Pit+ FA": 102.1,
            }
        ]
    )

    matrix = build_pitch_type_matrix(frame, pitcher_id=657277, pitcher_name=None, value_label="Stuff+")

    assert matrix.loc[matrix["Pitch"] == "Four-Seam", "Stuff+"].iloc[0] == 101.5
    assert matrix.loc[matrix["Pitch"] == "Four-Seam", "Location+"].iloc[0] == 99.2
    assert matrix.loc[matrix["Pitch"] == "Four-Seam", "Pitching+"].iloc[0] == 102.1


def test_find_pitcher_row_falls_back_to_name_key():
    frame = pd.DataFrame([{"Name": "Logan Webb", "name_key": "logan webb"}])

    row = find_pitcher_row(frame, pitcher_id=1, pitcher_name="Logan Webb")

    assert len(row) == 1


def test_build_overview_percentile_profile_reuses_period_comparison_metrics(monkeypatch):
    pool = pd.DataFrame([{"player_id": 7}])
    metric = ComparisonMetric(
        key="whiff_pct",
        label="Whiff %",
        value=31.2,
        formatted_value="31.2%",
        percentile=84,
        higher_is_better=True,
    )

    from app.services import comparison_service

    monkeypatch.setattr(comparison_service, "load_comparison_pool", lambda year: pool)
    monkeypatch.setattr(comparison_service, "build_metric_card", lambda row, year: [metric])

    profile = personal_service.build_overview_percentile_profile(2026, 7)

    assert profile == [metric.model_dump()]


def test_build_overview_game_log_adds_pitch_mix_game_score_and_hard_hits(monkeypatch):
    game_lines = pd.DataFrame(
        [
            {
                "game_pk": 10,
                "game_date": "2026-04-01",
                "team": "AAA",
                "pitcher_id": 1,
                "pitcher_name": "Ace Starter",
                "ip": 6.0,
                "hits": 3,
                "runs": 1,
                "earned_runs": 1,
                "walks": 1,
                "strikeouts": 6,
                "pitches": 90,
                "batters_faced": 24,
            }
        ]
    )
    pitches = pd.DataFrame(
        [
            {"game_pk": 10, "pitch_name": "4-Seam Fastball", "events": "", "launch_speed": None},
            {"game_pk": 10, "pitch_name": "4-Seam Fastball", "events": "home_run", "launch_speed": 101.0},
            {"game_pk": 10, "pitch_name": "Slider", "events": "", "launch_speed": 96.0},
        ]
    )

    monkeypatch.setattr(personal_service, "_load_season_pitcher_game_lines", lambda year: game_lines)
    monkeypatch.setattr(personal_service, "load_pitcher_cached_season", lambda year, pitcher_id, data_dir: pitches)

    log = personal_service.build_overview_game_log(2026, pitcher_id=1, pitcher_name="Ace Starter")

    assert log.loc[0, "Name"] == "Ace Starter"
    assert log.loc[0, "GS"] == 67
    assert log.loc[0, "HR"] == 1
    assert log.loc[0, "HH"] == 2
    assert "4-Seam 67%" in log.loc[0, "Pitch Types"]


def test_movement_scatter_keeps_video_and_pitch_identity_fields():
    pitches = pd.DataFrame([{
        "game_date": "2026-09-08",
        "game_pk": 99,
        "at_bat_number": 4,
        "pitch_number": 2,
        "pitch_name": "4-Seam Fastball",
        "pitch_type": "FF",
        "description": "swinging_strike",
        "balls": 1,
        "strikes": 1,
        "plate_x": 0.2,
        "plate_z": 2.8,
        "pfx_x": -0.5,
        "pfx_z": 1.25,
        "release_speed": 97.1,
        "play_id": "play-99",
        "video_url": "https://example.test/video",
    }])

    rows = personal_service.build_movement_scatter_rows(pitches)

    assert rows[0]["game_pk"] == 99
    assert rows[0]["play_id"] == "play-99"
    assert rows[0]["video_url"] == "https://example.test/video"
    assert rows[0]["h_break"] == 6.0
    assert rows[0]["v_break"] == 15.0
