from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.services import game_pitcher_analysis_service
from app.services.game_pitcher_analysis_service import (
    build_game_pitch_replay_response,
    build_game_pitch_shape_response,
    build_pitch_trajectory,
    get_game_pitcher_tags,
)


def _write_slice3_roster(data_dir: Path) -> None:
    derived = data_dir / "derived"
    derived.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "population": "pitcher",
                "year": 2025,
                "player_id": 2,
                "role": "RP",
                "display_name": "Low Sample Reliever",
                "team": "TST",
                "sample_size": 310,
                "sample_reliability": 0.61,
                "sample_status": "qualified",
                "tag_1": "Two-Pitch RP",
                "tag_1_dimension": "arsenal_depth",
                "tag_2": "FF / SL Primary",
                "tag_2_dimension": "primary_pair",
                "tag_3": None,
                "tag_3_dimension": None,
                "tag_4": None,
                "tag_4_dimension": None,
                "tag_count": 2,
                "supplemental_tags": "[]",
                "support_status": "supported",
            },
            {
                "population": "pitcher",
                "year": 2026,
                "player_id": 1,
                "role": "SP",
                "display_name": "Test Starter",
                "team": "TST",
                "sample_size": 640,
                "sample_reliability": 0.82,
                "sample_status": "qualified",
                "tag_1": "Versatile SP",
                "tag_1_dimension": "arsenal_depth",
                "tag_2": "FF / SL Primary",
                "tag_2_dimension": "primary_pair",
                "tag_3": "High 3/4",
                "tag_3_dimension": "arm_slot",
                "tag_4": "Above-Average Command",
                "tag_4_dimension": "command",
                "tag_count": 4,
                "supplemental_tags": "[]",
                "support_status": "supported",
            },
            {
                "population": "pitcher",
                "year": 2026,
                "player_id": 2,
                "role": "RP",
                "display_name": "Low Sample Reliever",
                "team": "TST",
                "sample_size": 45,
                "sample_reliability": 0.2,
                "sample_status": "limited",
                "tag_1": None,
                "tag_1_dimension": None,
                "tag_2": None,
                "tag_2_dimension": None,
                "tag_3": None,
                "tag_3_dimension": None,
                "tag_4": None,
                "tag_4_dimension": None,
                "tag_count": 0,
                "supplemental_tags": "[]",
                "support_status": "unassigned",
            },
        ]
    ).to_parquet(derived / "player_archetype_slice3_roster.parquet", index=False)


def _write_practical_roster(data_dir: Path) -> None:
    pd.DataFrame(
        [
            {
                "year": 2026,
                "player_id": 1,
                "role": "SP",
                "practical_tags": json.dumps(
                    [
                        {
                            "code": "pronation",
                            "label": "Pronation",
                            "dimension": "mechanics",
                            "description": "Hand-normalized movement profile.",
                            "evidence": {"pronation_strong_types": ["FF", "SI"]},
                        },
                        {
                            "code": "platoon_lhb_more_offspeed",
                            "label": "LHB More Offspeed",
                            "dimension": "platoon_strategy",
                            "description": "Full-season pitch-family usage tendency.",
                            "evidence": {"gap_pp": 18.0},
                        },
                    ]
                ),
            }
        ]
    ).to_parquet(data_dir / "derived" / "player_archetype_practical_tags_v1.parquet", index=False)


def test_game_pitcher_tags_use_existing_slice3_snapshot(tmp_path: Path):
    _write_slice3_roster(tmp_path)
    _write_practical_roster(tmp_path)

    payload = get_game_pitcher_tags(2026, 100, 1, "SP", data_dir=tmp_path)

    assert payload["status"] == "supported"
    assert payload["support"] == {
        "pitches": 640,
        "label": "supported",
        "reliability": 0.82,
        "sample_status": "qualified",
    }
    assert [tag["label"] for tag in payload["tags"]] == [
        "Versatile SP",
        "High 3/4",
        "Above-Average Command",
        "Pronation",
        "LHB More Offspeed",
    ]
    assert payload["tags"][-1]["source"] == "practical_v1"
    assert payload["time_scope"] == "full-season descriptive snapshot"
    assert payload["reference"] is None
    assert "complete season" in payload["warnings"][0]


def test_game_pitcher_tags_keep_old_unassigned_state(tmp_path: Path):
    _write_slice3_roster(tmp_path)

    payload = get_game_pitcher_tags(2026, 100, 2, "RP", data_dir=tmp_path)

    assert payload["status"] == "unassigned"
    assert payload["support"]["pitches"] == 45
    assert payload["tags"] == []
    assert payload["reference"]["year"] == 2025
    assert [tag["label"] for tag in payload["reference"]["tags"]] == ["Two-Pitch RP"]
    assert any("No released Slice 3 tag" in warning for warning in payload["warnings"])


def test_game_pitch_shape_returns_one_shared_filterable_payload(monkeypatch):
    pitches = pd.DataFrame(
        [
            {
                "game_date": "2026-09-27",
                "game_pk": 824948,
                "pitcher": 1,
                "at_bat_number": 1,
                "pitch_number": 1,
                "pitch_name": "Four-Seam",
                "pitch_type": "FF",
                "description": "called_strike",
                "events": None,
                "stand": "L",
                "balls": 0,
                "strikes": 0,
                "fielder_2": 10,
                "pfx_x": -0.5,
                "pfx_z": 1.25,
                "release_pos_x": -2.0,
                "release_pos_z": 6.0,
                "release_extension": 6.4,
                "release_speed": 95.2,
                "p_throws": "R",
                "play_id": "play-1",
                "video_url": "https://example.test/play-1",
                "pitch_stuff_plus": 111.0,
            },
            {
                "game_date": "2026-09-27",
                "game_pk": 824948,
                "pitcher": 1,
                "at_bat_number": 1,
                "pitch_number": 2,
                "pitch_name": "Slider",
                "pitch_type": "SL",
                "description": "hit_into_play",
                "events": "single",
                "stand": "R",
                "balls": 0,
                "strikes": 1,
                "fielder_2": 10,
                "pfx_x": 0.25,
                "pfx_z": 0.1,
                "release_pos_x": -1.8,
                "release_pos_z": 5.9,
                "release_extension": 6.2,
                "release_speed": 85.0,
                "p_throws": "R",
                "play_id": "play-2",
                "video_url": "https://example.test/play-2",
                "pitch_stuff_plus": 98.0,
            },
            {
                "game_date": "2026-09-27",
                "game_pk": 824948,
                "pitcher": 1,
                "at_bat_number": 2,
                "pitch_number": 1,
                "pitch_name": "Slider",
                "pitch_type": "SL",
                "description": "swinging_strike",
                "events": "strikeout",
                "stand": "R",
                "balls": 1,
                "strikes": 2,
                "fielder_2": 10,
                "pfx_x": 0.4,
                "pfx_z": 0.2,
                "release_pos_x": None,
                "release_pos_z": None,
                "release_speed": 86.0,
                "p_throws": "R",
                "play_id": "play-3",
                "video_url": None,
                "pitch_stuff_plus": 102.0,
            },
        ]
    )
    monkeypatch.setattr(
        game_pitcher_analysis_service,
        "catcher_lookup_rows",
        lambda data, year=None: [{"catcher_id": "10", "catcher_name": "Test Catcher"}],
    )

    payload = build_game_pitch_shape_response(pitches, year=2026, game_pk=824948, pitcher_id=1)
    rows = payload.charts["pitch_shape_scatter"]

    assert len(rows) == 3
    assert rows[0]["h_break"] == 6.0
    assert rows[0]["v_break"] == 15.0
    assert rows[0]["release_pos_x_in"] == -24.0
    assert rows[0]["release_pos_z_in"] == 72.0
    assert rows[0]["pitch_result_group"] == "Called Strike"
    assert rows[0]["catcher_name"] == "Test Catcher"
    assert rows[0]["video_url"] == "https://example.test/play-1"
    assert rows[1]["in_play_result_group"] == "Hit"
    assert rows[2]["pa_result_group"] == "Strikeout"
    assert payload.charts["filter_options"] == {
        "pitch_names": ["4-Seam", "Slider"],
        "catchers": ["Test Catcher"],
        "stands": ["L", "R"],
        "counts": ["0-0", "0-1", "1-2"],
    }
    assert {item.key: item.value for item in payload.summary} == {
        "pitches": 3,
        "pitcher_hand": "R",
        "movement_pitches": 3,
        "release_point_pitches": 2,
    }
    assert len(payload.tables["movement_summary"].rows) == 2
    assert len(payload.tables["release_point_summary"].rows) == 2


def _trajectory_pitch(**overrides):
    row = {
        "game_date": "2026-09-27",
        "game_pk": 824948,
        "pitcher": 837227,
        "batter": 695720,
        "at_bat_number": 80,
        "pitch_number": 1,
        "pitch_uid": "824948-80-1",
        "pitch_name": "4-Seam Fastball",
        "pitch_type": "FF",
        "description": "ball",
        "events": None,
        "stand": "R",
        "p_throws": "R",
        "balls": 0,
        "strikes": 0,
        "fielder_2": 673237,
        "release_speed": 91.3,
        "release_pos_x": -2.24,
        "release_pos_y": 54.97,
        "release_pos_z": 5.56,
        "vx0": 8.635542820240069,
        "vy0": -132.81907845632853,
        "vz0": 1.0886556260115177,
        "ax": -12.43664221826421,
        "ay": 26.563604616098026,
        "az": -20.45967368935164,
        "plate_x": 0.494763461276511,
        "plate_z": 4.512311904524872,
        "sz_top": 3.194553806,
        "sz_bot": 1.612204724,
        "play_id": "play-replay-1",
        "video_url": "https://example.test/replay-1",
    }
    row.update(overrides)
    return row


def test_pitch_trajectory_back_projects_release_to_fifty_foot_state():
    trajectory = build_pitch_trajectory(pd.Series(_trajectory_pitch()))

    assert trajectory["trajectory_status"] == "supported"
    assert len(trajectory["trajectory_points"]) == 31
    assert trajectory["trajectory_points"][0]["y_ft"] == 54.97
    assert abs(trajectory["trajectory_points"][-1]["y_ft"] - (17 / 12)) < 0.001
    assert trajectory["flight_time_seconds"] > 0.4
    assert trajectory["closure_error_x_in"] < 1
    assert trajectory["closure_error_z_in"] < 2


def test_pitch_trajectory_accepts_slow_pitch_positive_root():
    trajectory = build_pitch_trajectory(
        pd.Series(
            _trajectory_pitch(
                game_pk=824652,
                pitcher=656716,
                batter=664023,
                at_bat_number=60,
                pitch_number=3,
                pitch_name="Eephus",
                pitch_type="EP",
                release_speed=34.9,
                release_pos_x=-0.69,
                release_pos_y=57.33,
                release_pos_z=7.47,
                vx0=2.0797625046020967,
                vy0=-49.40565298699235,
                vz0=9.482849324321329,
                ax=-0.6231232077030943,
                ay=2.706857465702176,
                az=-31.078989552862943,
                plate_x=1.4313529185399865,
                plate_z=2.569872677434436,
            )
        )
    )

    assert trajectory["trajectory_status"] in {"supported", "limited_trajectory"}
    assert trajectory["flight_time_seconds"] > 1.0
    assert trajectory["trajectory_points"][-1]["y_ft"] == round(17 / 12, 4)


def test_game_pitch_replay_scopes_rows_and_preserves_unavailable_and_limited(monkeypatch):
    pitches = pd.DataFrame(
        [
            _trajectory_pitch(),
            _trajectory_pitch(pitch_number=2, pitch_uid="824948-80-2", release_pos_y=None),
            _trajectory_pitch(pitch_number=3, pitch_uid="824948-80-3", plate_x=10.0),
            _trajectory_pitch(game_pk=999999, pitch_uid="other-game"),
            _trajectory_pitch(pitcher=999999, pitch_uid="other-pitcher"),
            _trajectory_pitch(pitch_number=4, pitch_uid="pitch-out", pitch_type="PO", pitch_name="Pitch Out"),
            _trajectory_pitch(pitch_number=5, pitch_uid="pitchless", pitch_type=None, pitch_name=None),
        ]
    )
    monkeypatch.setattr(
        game_pitcher_analysis_service,
        "catcher_lookup_rows",
        lambda data, year=None: [{"catcher_id": "673237", "catcher_name": "Test Catcher"}],
    )

    payload = build_game_pitch_replay_response(pitches, year=2026, game_pk=824948, pitcher_id=837227)
    rows = payload.charts["pitch_replay"]

    assert len(rows) == 3
    assert [row["trajectory_status"] for row in rows] == ["supported", "unavailable", "limited_trajectory"]
    assert rows[0]["catcher_name"] == "Test Catcher"
    assert rows[0]["video_url"] == "https://example.test/replay-1"
    assert rows[1]["trajectory_points"] == []
    assert rows[2]["closure_error_x_in"] > 3
    assert payload.charts["game_scope"] == {"game_pk": 824948, "pitcher_id": 837227}
    assert payload.charts["contract_version"] == "pitch_trajectory_statcast_v1"
    assert {item.key: item.value for item in payload.summary} == {
        "pitches": 3,
        "supported_pitches": 1,
        "limited_pitches": 1,
        "unavailable_pitches": 1,
        "pitcher_hand": "R",
    }
