import pandas as pd
import pytest

from app.services.discipline_service import (
    build_discipline_panel_groups,
    build_pitcher_discipline_table,
    build_pitcher_panel_metrics,
    build_starter_style_discipline_payload,
    meatball_zone_mask,
    red_strike_zone_mask,
)


def location_rows(frame: pd.DataFrame) -> list[dict]:
    return frame[["plate_x", "plate_z", "pitch_name"]].to_dict(orient="records") if not frame.empty else []


def test_build_pitcher_discipline_table_summarizes_overall_and_pitch_rows():
    frame = pd.DataFrame(
        [
            {"pitch_name": "Sinker", "description": "called_strike", "zone": 5, "pitch_number": 1},
            {"pitch_name": "Sinker", "description": "swinging_strike", "zone": 14, "pitch_number": 2},
            {"pitch_name": "Slider", "description": "hit_into_play", "zone": 7, "pitch_number": 1},
        ]
    )

    table = build_pitcher_discipline_table(frame, player_name="A Pitcher", team="ATH")

    assert table["Pitch"].tolist() == ["Overall", "Sinker", "Slider"]
    assert table.loc[0, "Pitches"] == 3
    assert table.loc[0, "Strike%"] == pytest.approx(100.0)
    assert table.loc[0, "Whiff%"] == pytest.approx(50.0)
    assert table.loc[0, "CSW%"] == pytest.approx(66.6666667)


def test_build_pitcher_panel_metrics_returns_starter_side_info():
    frame = pd.DataFrame(
        [
            {"description": "ball", "zone": 14, "events": ""},
            {"description": "swinging_strike", "zone": 14, "events": ""},
            {"description": "hit_into_play", "zone": 5, "events": "single"},
        ]
    )

    metrics = {item["label"]: item["value"] for item in build_pitcher_panel_metrics(frame)}

    assert metrics["Zone%"] == pytest.approx(33.3333333)
    assert metrics["Swing%"] == pytest.approx(66.6666667)
    assert metrics["O-Swing%"] == pytest.approx(50.0)
    assert metrics["Whiff%"] == pytest.approx(50.0)
    assert metrics["AVG"] == pytest.approx(1.0)


def test_zone_metrics_use_red_strike_zone_coordinates_before_statcast_zone():
    frame = pd.DataFrame(
        [
            {"description": "called_strike", "zone": 5, "plate_x": 0.0, "plate_z": 2.5, "events": ""},
            {"description": "swinging_strike", "zone": 5, "plate_x": 1.2, "plate_z": 2.5, "events": ""},
            {"description": "ball", "zone": 14, "plate_x": 0.1, "plate_z": 3.7, "events": ""},
        ]
    )

    metrics = {item["label"]: item["value"] for item in build_pitcher_panel_metrics(frame)}

    assert red_strike_zone_mask(frame).tolist() == [True, False, False]
    assert metrics["Zone%"] == pytest.approx(33.3333333)
    assert metrics["O-Swing%"] == pytest.approx(50.0)


def test_meatball_uses_statcast_zone_five_and_coordinate_fallback_only_when_zone_missing():
    frame = pd.DataFrame(
        [
            {"zone": 5, "plate_x": 1.2, "plate_z": 4.0, "sz_bot": 1.5, "sz_top": 3.5},
            {"zone": 1, "plate_x": 0.0, "plate_z": 2.5, "sz_bot": 1.5, "sz_top": 3.5},
            {"zone": None, "plate_x": 0.0, "plate_z": 2.5, "sz_bot": 1.5, "sz_top": 3.5},
            {"zone": None, "plate_x": 0.5, "plate_z": 2.5, "sz_bot": 1.5, "sz_top": 3.5},
        ]
    )

    assert meatball_zone_mask(frame).tolist() == [True, False, True, False]


def test_discipline_table_exposes_meatball_not_legacy_heart_alias():
    frame = pd.DataFrame(
        [
            {"pitch_name": "Sinker", "description": "called_strike", "zone": 5},
            {"pitch_name": "Sinker", "description": "called_strike", "zone": 1},
        ]
    )

    table = build_pitcher_discipline_table(frame)

    assert table.loc[0, "Meatball%"] == pytest.approx(50.0)
    assert "Heart Ball%" not in table.columns


def test_build_discipline_panel_groups_matches_starter_panel_structure():
    frame = pd.DataFrame(
        [
            {"plate_x": 0.1, "plate_z": 2.4, "pitch_name": "Sinker", "description": "called_strike", "events": "", "balls": 0, "strikes": 0, "bb_type": ""},
            {"plate_x": 0.2, "plate_z": 2.8, "pitch_name": "Slider", "description": "swinging_strike", "events": "strikeout", "balls": 0, "strikes": 2, "bb_type": ""},
            {"plate_x": -0.1, "plate_z": 3.0, "pitch_name": "Sinker", "description": "hit_into_play", "events": "home_run", "balls": 3, "strikes": 0, "bb_type": "fly_ball"},
        ]
    )

    groups = build_discipline_panel_groups(frame, location_rows)

    assert [panel["key"] for panel in groups["result"]["pitch_result"]] == ["called_strike", "swing_strike", "in_play", "foul_ball"]
    assert groups["result"]["pitch_result"][0]["pitches"] == 1
    assert groups["result"]["pa_result"][2]["key"] == "pa_home_run"
    assert groups["result"]["pa_result"][2]["pitches"] == 1
    assert groups["result"]["batted_ball"][1]["key"] == "fly_ball"
    assert groups["discipline"]["count_situation"][0]["key"] == "count_0_0"
    assert groups["discipline"]["count_swing"][3]["key"] == "count_two_strikes"
    assert len(groups["situation"]["exact_count"]) == 12
    assert next(panel for panel in groups["situation"]["exact_count"] if panel["key"] == "count_3_0")["pitches"] == 1


def test_build_starter_style_discipline_payload_returns_table_and_panel_groups():
    frame = pd.DataFrame(
        [
            {"plate_x": 0.1, "plate_z": 2.4, "pitch_name": "Sinker", "description": "called_strike", "events": "", "balls": 0, "strikes": 0},
        ]
    )

    payload = build_starter_style_discipline_payload(frame, location_rows, player_name="A Pitcher", team="ATH")

    assert payload["tables"]["pitcher_discipline"].rows[0]["Pitch"] == "Overall"
    assert payload["charts"]["panel_groups"]["result"]["pitch_result"][0]["rows"] == [
        {"plate_x": 0.1, "plate_z": 2.4, "pitch_name": "Sinker"}
    ]
