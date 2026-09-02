from __future__ import annotations

import duckdb
import pandas as pd

from app.services import batter_service


def test_list_batter_leaderboard_reads_savant_csv(tmp_path, monkeypatch):
    batter_dir = tmp_path / "Batter"
    batter_dir.mkdir()
    (batter_dir / "2026_batter_savant.csv").write_text(
        "\n".join(
                [
                    '"last_name, first_name",player_id,year,pa,ab,hit,home_run,walk,strikeout,batting_avg,on_base_percent,slg_percent,on_base_plus_slg,woba,xba,xslg,xwoba,exit_velocity_avg,hard_hit_percent,barrel_batted_rate,whiff_percent,k_percent,bb_percent',
                    '"Smith, John",1,2026,100,90,30,8,10,20,.333,.400,.600,1.000,.420,.310,.560,.390,91.2,50.0,12.5,25.0,20.0,10.0',
                ]
            ),
        encoding="utf-8",
    )
    monkeypatch.setattr(batter_service.settings, "data_dir", tmp_path)
    monkeypatch.setattr(
        batter_service,
        "_load_batter_pitch_supplement",
        lambda year: pd.DataFrame([{"player_id": 1, "team": "AZ", "games": 22, "pitches": 350, "max_ev": 113.4}]),
    )

    rows = batter_service.list_batter_leaderboard(2026)

    assert rows[0]["name"] == "John Smith"
    assert rows[0]["team"] == "AZ"
    assert rows[0]["games"] == 22
    assert rows[0]["plate_appearances"] == 100
    assert rows[0]["hard_hit_rate"] == 0.5
    assert rows[0]["barrel_rate"] == 0.125


def test_list_batter_options_filters_team(monkeypatch):
    monkeypatch.setattr(
        batter_service,
        "list_batter_leaderboard",
        lambda year, team="All": [
            {"player_id": 1, "name": "John Smith", "team": "AZ", "games": 12, "plate_appearances": 52},
            {"player_id": 2, "name": "Jane Doe", "team": "SEA", "games": 9, "plate_appearances": 41},
        ]
        if team == "All"
        else [{"player_id": 1, "name": "John Smith", "team": "AZ", "games": 12, "plate_appearances": 52}],
    )

    options = batter_service.list_batter_options(2026, "AZ")

    assert options == [
        {
            "value": 1,
            "label": "John Smith (AZ)",
            "name": "John Smith",
            "team": "AZ",
            "games": 12,
            "plate_appearances": 52,
        }
    ]


def test_list_batter_leaderboard_prefers_current_duckdb_calculations(tmp_path, monkeypatch):
    mlb_dir = tmp_path / "MLB2026"
    mlb_dir.mkdir()
    stale = pd.DataFrame(
        [{"last_name, first_name": "Smith, John", "player_id": 1, "year": 2026, "pa": 100}]
    )
    stale.to_csv(mlb_dir / "2026_all_batter_standard.csv", index=False)

    pitches = pd.DataFrame(
        [
            _test_batter_pitch(1, 1, "single", "hit_into_play", 96.0, 4, 0.8, 1.2, 0.9, 0.9, 1.0),
            _test_batter_pitch(1, 2, "double", "hit_into_play", 101.0, 5, 0.7, 1.6, 1.0, 1.25, 1.0),
            _test_batter_pitch(1, 3, "home_run", "hit_into_play", 105.0, 6, 0.9, 3.2, 1.7, 2.0, 1.0),
            _test_batter_pitch(1, 4, "walk", "ball", None, None, None, None, None, 0.7, 1.0),
            _test_batter_pitch(2, 1, "strikeout", "swinging_strike", None, None, None, None, None, 0.0, 1.0),
            _test_batter_pitch(2, 2, "sac_fly", "hit_into_play", 88.0, 3, None, None, None, 0.0, 0.0),
            _test_batter_pitch(2, 3, "truncated_pa", "ball", None, None, None, None, None, 0.0, 0.0),
        ]
    )
    with duckdb.connect(str(mlb_dir / "mlb_2026.duckdb")) as conn:
        conn.register("pitches_frame", pitches)
        conn.execute("CREATE TABLE pitches AS SELECT * FROM pitches_frame")
        conn.execute(
            "CREATE TABLE player_master AS SELECT 1::BIGINT AS player_id, 'John Smith'::VARCHAR AS player_name"
        )

    monkeypatch.setattr(batter_service.settings, "data_dir", tmp_path)
    row = batter_service.list_batter_leaderboard(2026)[0]

    assert row["name"] == "John Smith"
    assert row["team"] == "AZ"
    assert row["games"] == 2
    assert row["plate_appearances"] == 6
    assert row["at_bats"] == 4
    assert row["hits"] == 3
    assert row["home_runs"] == 1
    assert row["walks"] == 1
    assert row["strikeouts"] == 1
    assert row["avg"] == 0.75
    assert round(row["obp"], 3) == 0.667
    assert row["slg"] == 1.75
    assert round(row["hard_hit_rate"], 3) == 0.75
    assert round(row["barrel_rate"], 3) == 0.25
    assert round(row["whiff_rate"], 3) == 0.2


def test_batter_name_falls_back_to_official_game_lookup(tmp_path, monkeypatch):
    mlb_dir = tmp_path / "MLB2026"
    mlb_dir.mkdir()
    pitches = pd.DataFrame([_test_batter_pitch(1, 1, "single", "hit_into_play", 96.0, 4, 0.8, 1.2, 0.9, 0.9, 1.0)])
    with duckdb.connect(str(mlb_dir / "mlb_2026.duckdb")) as conn:
        conn.register("pitches_frame", pitches)
        conn.execute("CREATE TABLE pitches AS SELECT * FROM pitches_frame")
        conn.execute("CREATE TABLE player_master AS SELECT 1::BIGINT AS player_id, 'Unknown'::VARCHAR AS player_name")
        conn.execute(
            """
            CREATE TABLE game_player_lookup AS
            SELECT 1::BIGINT AS game_pk, 1::BIGINT AS player_id,
                   'Official Rookie'::VARCHAR AS player_name, 'batter'::VARCHAR AS role
            """
        )

    monkeypatch.setattr(batter_service.settings, "data_dir", tmp_path)

    assert batter_service.list_batter_leaderboard(2026)[0]["name"] == "Official Rookie"


def test_batter_location_points_keep_video_and_plus_scores(monkeypatch):
    raw = pd.DataFrame(
        [
            {
                **_test_batter_pitch(1, 1, "", "ball", None, None, None, None, None, 0.0, 0.0),
                "pitcher": 99,
                "pitch_name": "4-Seam Fastball",
                "pitch_type": "FF",
                "plate_x": 0.2,
                "plate_z": 2.8,
                "play_id": "test-play-id",
                "video_url": "",
                "bat_speed": 74.2,
            }
        ]
    )
    monkeypatch.setattr(batter_service, "load_pitch_stuff_scores", lambda frame: pd.Series([112.4], index=frame.index))
    monkeypatch.setattr(batter_service, "load_pitch_location_scores", lambda frame: pd.Series([96.8], index=frame.index))

    normalized = batter_service._normalize_batter_pitch_rows(raw)
    point = batter_service._build_batter_location_points(normalized).rows[0]

    assert point["video_url"].endswith("playId=test-play-id")
    assert point["pitch_stuff_plus"] == 112.4
    assert point["location_plus_pitch"] == 96.8
    assert point["bat_speed"] == 74.2
    assert point["is_swing"] is False


def test_batter_filters_accept_checkbox_csv_values():
    rows = pd.DataFrame(
        [
            {"stand": "L", "count": "0-0", "pitch_name": "Slider", "pitch_type": "SL", "description": "ball", "is_swing": False, "is_whiff": False, "is_in_play": False, "game_date": "2026-04-01"},
            {"stand": "R", "count": "1-0", "pitch_name": "Changeup", "pitch_type": "CH", "description": "swinging_strike", "is_swing": True, "is_whiff": True, "is_in_play": False, "game_date": "2026-04-02"},
            {"stand": "R", "count": "2-0", "pitch_name": "Curveball", "pitch_type": "CU", "description": "hit_into_play", "is_swing": True, "is_whiff": False, "is_in_play": True, "game_date": "2026-04-03"},
        ]
    )

    filtered = batter_service._apply_batter_filters(
        rows,
        stand="L,R",
        count="0-0,1-0",
        pitch="Slider,Changeup",
        pitch_result="Swing,ball",
        start_date=None,
        end_date=None,
    )

    assert filtered["pitch_type"].tolist() == ["SL", "CH"]


def test_batter_game_log_exposes_batter_wpa_and_woba(monkeypatch):
    raw = pd.DataFrame(
        [
            {
                **_test_batter_pitch(1, 1, "single", "hit_into_play", 96.0, 4, 0.8, 1.2, 0.9, 0.9, 1.0),
                "home_team": "AZ",
                "away_team": "LAD",
                "delta_home_win_exp": 0.04,
            },
            {
                **_test_batter_pitch(1, 2, "walk", "ball", None, None, None, None, None, 0.7, 1.0),
                "home_team": "AZ",
                "away_team": "LAD",
                "delta_home_win_exp": 0.01,
            },
        ]
    )
    monkeypatch.setattr(batter_service, "load_pitch_stuff_scores", lambda frame: pd.Series(index=frame.index, dtype=float))
    monkeypatch.setattr(batter_service, "load_pitch_location_scores", lambda frame: pd.Series(index=frame.index, dtype=float))

    row = batter_service._build_batter_game_log(batter_service._normalize_batter_pitch_rows(raw)).rows[0]

    assert row["Game WPA"] == 0.05
    assert row["wOBA"] == 0.8


def _test_batter_pitch(
    game_pk: int,
    at_bat_number: int,
    event: str,
    description: str,
    launch_speed: float | None,
    launch_speed_angle: int | None,
    estimated_ba: float | None,
    estimated_slg: float | None,
    estimated_woba: float | None,
    woba_value: float,
    woba_denom: float,
) -> dict[str, object]:
    return {
        "batter": 1,
        "game_pk": game_pk,
        "game_date": f"2026-04-0{game_pk}",
        "game_type": "R",
        "events": event,
        "description": description,
        "at_bat_number": at_bat_number,
        "pitch_number": 1,
        "offense_team": "AZ",
        "launch_speed": launch_speed,
        "launch_speed_angle": launch_speed_angle,
        "estimated_ba_using_speedangle": estimated_ba,
        "estimated_slg_using_speedangle": estimated_slg,
        "estimated_woba_using_speedangle": estimated_woba,
        "woba_value": woba_value,
        "woba_denom": woba_denom,
    }
