import pandas as pd
import pytest

import app.services.personal_service as personal_service
from app.services.personal_service import (
    apply_stuff_filters,
    apply_sequence_filters,
    annotate_sequence_context,
    build_count_pitch_mix,
    build_conditioned_count_subset,
    build_conditioned_wpa_summary_table,
    build_count_state_detail_table,
    build_catcher_options,
    build_count_pitch_followup_table,
    build_next_count_state_detail_table,
    build_discipline_summary,
    build_discipline_count_panels,
    build_discipline_result_panels,
    build_movement_comparison_table,
    build_outing_summary,
    build_pitch_location_scatter,
    build_pitch_movement_summary,
    build_pitch_type_run_value_table,
    build_sequence_outcome_tables,
    get_personal_discipline,
)


def test_build_pitch_movement_summary_converts_feet_to_inches():
    frame = pd.DataFrame(
        [
            {"pitch_name": "Sinker", "pfx_x": -1.0, "pfx_z": 0.5, "release_speed": 94},
            {"pitch_name": "Sinker", "pfx_x": -0.5, "pfx_z": 0.7, "release_speed": 96},
        ]
    )

    summary = build_pitch_movement_summary(frame)

    assert summary.loc[0, "pitches"] == 2
    assert summary.loc[0, "h_break"] == 9.0
    assert summary.loc[0, "v_break"] == pytest.approx(7.2)


def test_build_discipline_summary_counts_basic_rates():
    frame = pd.DataFrame(
        [
            {"description": "called_strike", "zone": 5, "pitch_number": 1},
            {"description": "swinging_strike", "zone": 14, "pitch_number": 2},
            {"description": "ball", "zone": 11, "pitch_number": 1},
        ]
    )

    summary = build_discipline_summary(frame)

    assert summary.loc[0, "Pitches"] == 3
    assert round(summary.loc[0, "Swing%"], 1) == 33.3
    assert round(summary.loc[0, "CSW%"], 1) == 66.7


def test_build_outing_summary_prefers_official_earned_runs_when_available():
    frame = pd.DataFrame(
        [
            {"game_date": "2026-01-01", "description": "called_strike", "events": "", "at_bat_number": 1, "zone": 5},
            {"game_date": "2026-01-01", "description": "hit_into_play", "events": "single", "at_bat_number": 2, "zone": 5},
            {"game_date": "2026-01-01", "description": "ball", "events": "walk", "at_bat_number": 3, "zone": 14},
        ]
    )

    summary = build_outing_summary(
        frame,
        {
            "ip": "5.1",
            "hits": 6,
            "runs": 2,
            "earned_runs": 1,
            "walks": 3,
            "strikeouts": 7,
            "pitches": 91,
            "batters_faced": 24,
        },
    )
    by_key = {item.key: item.value for item in summary}

    assert by_key["ip"] == "5.1"
    assert by_key["earned_runs"] == 1
    assert by_key["hits"] == 6
    assert by_key["official_line_status"] == "matched"


def test_build_pitch_location_scatter_returns_clean_points():
    frame = pd.DataFrame(
        [
            {"game_pk": 1, "at_bat_number": 2, "pitch_number": 3, "plate_x": 0.1, "plate_z": 2.4, "pitch_name": "Sinker", "description": "called_strike"},
            {"plate_x": None, "plate_z": 2.2, "pitch_name": "Slider", "description": "ball"},
        ]
    )

    points = build_pitch_location_scatter(frame)

    assert points == [{
        "game_pk": 1.0,
        "at_bat_number": 2.0,
        "pitch_number": 3.0,
        "plate_x": 0.1,
        "plate_z": 2.4,
        "pitch_name": "Sinker",
        "description": "called_strike",
        "pitch_stuff_plus": None,
        "location_plus_pitch": None,
    }]


def test_build_pitch_location_scatter_does_not_sample_points():
    frame = pd.DataFrame(
        [
            {"plate_x": i / 100, "plate_z": 2.4, "pitch_name": "Sinker", "description": "called_strike"}
            for i in range(1200)
        ]
    )

    points = build_pitch_location_scatter(frame)

    assert len(points) == 1200


def test_apply_stuff_filters_filters_count_pitch_and_result():
    frame = pd.DataFrame(
        [
            {"stand": "R", "balls": 0, "strikes": 0, "pitch_name": "Sinker", "description": "called_strike"},
            {"stand": "L", "balls": 1, "strikes": 0, "pitch_name": "Slider", "description": "ball"},
            {"stand": "R", "balls": 0, "strikes": 0, "pitch_name": "Slider", "description": "swinging_strike"},
        ]
    )

    filtered = apply_stuff_filters(frame, stand="R", count="0-0", pitch="Sinker", pitch_result="called_strike")

    assert filtered.shape[0] == 1
    assert filtered.iloc[0]["pitch_name"] == "Sinker"


def test_apply_stuff_filters_treats_all_as_no_filter():
    frame = pd.DataFrame(
        [
            {"stand": "R", "balls": 0, "strikes": 0, "pitch_name": "Sinker", "description": "called_strike", "catcher_name": "A"},
            {"stand": "L", "balls": 1, "strikes": 0, "pitch_name": "Slider", "description": "ball", "catcher_name": "B"},
        ]
    )

    filtered = apply_stuff_filters(frame, stand="All", count="All", pitch="All", pitch_result="All", catcher="All")

    assert filtered.shape[0] == frame.shape[0]


def test_apply_stuff_filters_accepts_four_seam_aliases():
    frame = pd.DataFrame(
        [
            {"pitch_name": "4-Seam", "description": "called_strike"},
            {"pitch_name": "4-Seam Fastball", "description": "ball"},
            {"pitch_name": "Four-Seam Fastball", "description": "foul"},
            {"pitch_name": "Fastball", "description": "hit_into_play"},
            {"pitch_name": "Sinker", "description": "called_strike"},
        ]
    )

    filtered = apply_stuff_filters(frame, pitch="4-Seam")

    assert filtered["pitch_name"].tolist() == ["4-Seam", "4-Seam Fastball", "Four-Seam Fastball", "Fastball"]


def test_apply_stuff_filters_filters_in_play_and_pa_results():
    frame = pd.DataFrame(
        [
            {"description": "hit_into_play", "events": "single", "launch_speed": 101, "launch_angle": 24},
            {"description": "hit_into_play", "events": "field_out", "launch_speed": 80, "launch_angle": -8},
            {"description": "called_strike", "events": "", "launch_speed": None, "launch_angle": None},
        ]
    )

    barrel_single = apply_stuff_filters(frame, in_play_result="barrel", pa_result="pa_single")
    no_result = apply_stuff_filters(frame, in_play_result="not_in_play", pa_result="pa_no_result")

    assert barrel_single.shape[0] == 1
    assert barrel_single.iloc[0]["events"] == "single"
    assert no_result.shape[0] == 1
    assert no_result.iloc[0]["description"] == "called_strike"


def test_apply_sequence_filters_can_filter_catcher():
    frame = pd.DataFrame(
        [
            {"stand": "R", "balls": 0, "strikes": 0, "pitch_name": "Sinker", "description": "called_strike", "catcher_name": "A"},
            {"stand": "R", "balls": 0, "strikes": 0, "pitch_name": "Sinker", "description": "called_strike", "catcher_name": "B"},
        ]
    )

    filtered = apply_sequence_filters(frame, stand="R", catcher="A")

    assert filtered.shape[0] == 1
    assert filtered.iloc[0]["catcher_name"] == "A"


def test_apply_sequence_filters_can_filter_catcher_id_fallback(monkeypatch):
    monkeypatch.setattr(
        personal_service,
        "load_mlbam_name_lookup",
        lambda player_ids: {"123456": "Test Catcher", "543510": "James McCann"},
    )
    frame = pd.DataFrame(
        [
            {"stand": "R", "balls": 0, "strikes": 0, "pitch_name": "Sinker", "description": "called_strike", "fielder_2": 543510},
            {"stand": "R", "balls": 0, "strikes": 0, "pitch_name": "Sinker", "description": "called_strike", "fielder_2": 123456},
        ]
    )

    assert build_catcher_options(frame) == ["James McCann", "Test Catcher"]

    filtered = apply_sequence_filters(frame, stand="R", catcher="James McCann")

    assert filtered.shape[0] == 1
    assert int(filtered.iloc[0]["fielder_2"]) == 543510


def test_catcher_options_use_season_player_master_before_external_lookup(monkeypatch):
    monkeypatch.setattr(personal_service, "load_season_catcher_lookup", lambda year: {"543510": "James McCann"})
    monkeypatch.setattr(
        personal_service,
        "load_mlbam_name_lookup",
        lambda player_ids: (_ for _ in ()).throw(AssertionError("external lookup should not run")),
    )
    frame = pd.DataFrame([{"fielder_2": 543510}])

    assert build_catcher_options(frame, year=2026) == ["James McCann"]


def test_build_discipline_panels_return_location_payloads():
    frame = pd.DataFrame(
        [
            {"plate_x": 0.1, "plate_z": 2.4, "pitch_name": "Sinker", "description": "called_strike", "balls": 0, "strikes": 0},
            {"plate_x": 0.2, "plate_z": 2.8, "pitch_name": "Slider", "description": "swinging_strike", "balls": 0, "strikes": 2},
        ]
    )

    result_panels = build_discipline_result_panels(frame)
    count_panels = build_discipline_count_panels(frame)

    assert len(result_panels["called_strike"]) == 1
    assert len(count_panels["0-0"]) == 1
    assert len(count_panels["two_strikes"]) == 1


def test_personal_discipline_payload_includes_starter_style_panel_groups(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "plate_x": 0.1,
                "plate_z": 2.4,
                "pitch_name": "Sinker",
                "description": "called_strike",
                "events": "",
                "zone": 5,
                "balls": 0,
                "strikes": 0,
            },
            {
                "plate_x": -0.2,
                "plate_z": 2.8,
                "pitch_name": "Slider",
                "description": "hit_into_play",
                "events": "home_run",
                "bb_type": "fly_ball",
                "zone": 14,
                "balls": 3,
                "strikes": 0,
            },
        ]
    )
    monkeypatch.setattr("app.services.personal_service.load_personal_pitch_df", lambda **_: frame)

    response = get_personal_discipline(year=2026, pitcher_id=1)
    panel_groups = response.charts["panel_groups"]

    assert panel_groups["result"]["pa_result"][2]["key"] == "pa_home_run"
    assert panel_groups["result"]["pa_result"][2]["pitches"] == 1
    assert panel_groups["result"]["batted_ball"][1]["key"] == "fly_ball"
    assert response.charts["pa_result_panels"][2]["pitches"] == 1
    assert response.charts["batted_ball_panels"][1]["pitches"] == 1
    assert panel_groups["discipline"]["count_swing"][0]["key"] == "count_0_0"
    assert len(panel_groups["situation"]["exact_count"]) == 12


def test_build_pitch_type_run_value_table_summarizes_pitch_metrics():
    frame = pd.DataFrame(
        [
            {"pitch_name": "Sinker", "description": "swinging_strike", "events": "", "delta_run_exp": -0.02, "strikes": 1, "pitch_number": 2},
            {"pitch_name": "Sinker", "description": "hit_into_play", "events": "single", "delta_run_exp": 0.1, "strikes": 2, "pitch_number": 3, "woba_value": 0.9, "launch_speed": 96},
            {"pitch_name": "Slider", "description": "ball", "events": "", "delta_run_exp": 0.03, "strikes": 0, "pitch_number": 1},
        ]
    )

    table = build_pitch_type_run_value_table(frame, team="ATH", year=2026)

    sinker = table[table["Pitch Type"] == "Sinker"].iloc[0]
    assert sinker["Pitches"] == 2
    assert sinker["Whiff%"] == pytest.approx(50.0)
    assert sinker["Hard Hit %"] == pytest.approx(100.0)


def test_build_count_pitch_mix_groups_by_count_and_pitch():
    frame = pd.DataFrame(
        [
            {"balls": 0, "strikes": 0, "pitch_name": "Sinker"},
            {"balls": 0, "strikes": 0, "pitch_name": "Sinker"},
            {"balls": 0, "strikes": 0, "pitch_name": "Slider"},
            {"balls": 1, "strikes": 1, "pitch_name": "Slider"},
        ]
    )

    rows = build_count_pitch_mix(frame)

    sinker = next(row for row in rows if row["count"] == "0-0" and row["pitch_name"] == "Sinker")
    assert sinker["pitches"] == 2
    assert sinker["rate"] == pytest.approx(2 / 3)


def test_build_conditioned_count_subset_tracks_downstream_branch():
    frame = pd.DataFrame(
        [
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 1, "balls": 0, "strikes": 0, "pitch_name": "Sinker", "delta_home_win_exp": 0.01},
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 2, "balls": 0, "strikes": 1, "pitch_name": "Slider", "delta_home_win_exp": -0.02},
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 3, "balls": 0, "strikes": 2, "pitch_name": "Slider", "delta_home_win_exp": -0.03},
            {"game_pk": 1, "at_bat_number": 2, "pitch_number": 1, "balls": 0, "strikes": 0, "pitch_name": "Slider", "delta_home_win_exp": 0.04},
        ]
    )

    conditioned = build_conditioned_count_subset(frame, "0-0", "Sinker")
    summary = build_conditioned_wpa_summary_table(frame, "0-0")

    assert conditioned.shape[0] == 3
    assert set(conditioned["count"]) == {"0-0", "0-1", "0-2"}
    assert summary.loc[summary["Pitch"].eq("Sinker"), "downstream_pitches"].iloc[0] == 3


def test_build_count_detail_tables_summarize_current_and_next_counts():
    frame = pd.DataFrame(
        [
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 1, "balls": 0, "strikes": 0, "pitch_name": "Sinker", "description": "called_strike", "events": ""},
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 2, "balls": 0, "strikes": 1, "pitch_name": "Slider", "description": "swinging_strike", "events": ""},
            {"game_pk": 1, "at_bat_number": 2, "pitch_number": 1, "balls": 0, "strikes": 0, "pitch_name": "Sinker", "description": "ball", "events": ""},
            {"game_pk": 1, "at_bat_number": 2, "pitch_number": 2, "balls": 1, "strikes": 0, "pitch_name": "Sinker", "description": "called_strike", "events": ""},
        ]
    )

    current = build_count_state_detail_table(frame[(frame["balls"] == 0) & (frame["strikes"] == 0)])
    next_table = build_next_count_state_detail_table(frame, "0-0")

    assert current.loc[current["Pitch"].eq("Sinker"), "pitches"].iloc[0] == 2
    assert set(next_table["Pitch"]) == {"Slider", "Sinker"}


def test_build_count_pitch_followup_table_summarizes_next_events():
    frame = pd.DataFrame(
        [
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 1, "balls": 0, "strikes": 0, "pitch_name": "Sinker", "description": "called_strike", "events": ""},
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 2, "balls": 0, "strikes": 1, "pitch_name": "Slider", "description": "swinging_strike", "events": ""},
            {"game_pk": 1, "at_bat_number": 2, "pitch_number": 1, "balls": 0, "strikes": 0, "pitch_name": "Sinker", "description": "hit_into_play", "events": "field_out"},
        ]
    )

    followup = build_count_pitch_followup_table(frame, "0-0", "Sinker")

    assert set(followup["followup_event"]) == {"Next Count: 0-1", "PA Ends: Ball in Play Out"}
    assert followup["pitches"].sum() == 2


def test_sequence_annotations_preserve_true_next_pitch_after_anchor_filter():
    frame = pd.DataFrame(
        [
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 1, "balls": 0, "strikes": 0, "pitch_name": "Sinker", "description": "called_strike", "events": ""},
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 2, "balls": 0, "strikes": 1, "pitch_name": "Changeup", "description": "ball", "events": ""},
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 3, "balls": 1, "strikes": 1, "pitch_name": "Slider", "description": "swinging_strike", "events": ""},
            {"game_pk": 1, "at_bat_number": 2, "pitch_number": 1, "balls": 0, "strikes": 0, "pitch_name": "Slider", "description": "hit_into_play", "events": "field_out"},
        ]
    )

    annotated = annotate_sequence_context(frame)
    filtered = annotated[annotated["pitch_name"].isin(["Sinker", "Slider"])].copy()
    followup = build_count_pitch_followup_table(filtered, "0-0", "Sinker")

    assert followup.iloc[0]["followup_event"] == "Next Count: 0-1"
    assert followup.iloc[0]["next_pitch"] == "Changeup"
    assert "Slider" not in followup["next_pitch"].tolist()


def test_build_movement_comparison_table_compares_same_hand_league():
    pitcher = pd.DataFrame(
        [
            {"pitch_name": "Sinker", "pfx_x": -1.0, "pfx_z": 0.8, "release_speed": 94},
            {"pitch_name": "Sinker", "pfx_x": -0.5, "pfx_z": 0.6, "release_speed": 96},
        ]
    )
    league = pd.DataFrame(
        [
            {
                "p_throws": "R",
                "pitch_name": "Sinker",
                "league_usage_pct": 20.0,
                "league_h_break": 8.0,
                "league_v_break": 9.0,
                "league_release_speed": 93.0,
            }
        ]
    )

    comparison = build_movement_comparison_table(pitcher, "R", league)

    assert comparison.loc[0, "Pitch"] == "Sinker"
    assert comparison.loc[0, "HB Diff"] == pytest.approx(1.0)
    assert comparison.loc[0, "Velo Diff"] == pytest.approx(2.0)


def test_build_sequence_outcome_tables_returns_shallow_sequences():
    rows = []
    for at_bat_number in [1, 2, 3]:
        rows.extend(
            [
                {"game_pk": 1, "at_bat_number": at_bat_number, "pitch_number": 1, "pitch_name": "Sinker", "description": "called_strike", "game_date": "2025-01-01", "balls": 0, "strikes": 0, "events": "", "launch_speed": None},
                {"game_pk": 1, "at_bat_number": at_bat_number, "pitch_number": 2, "pitch_name": "Slider", "description": "swinging_strike", "game_date": "2025-01-01", "balls": 0, "strikes": 1, "events": "", "launch_speed": None},
                {"game_pk": 1, "at_bat_number": at_bat_number, "pitch_number": 3, "pitch_name": "Slider", "description": "swinging_strike", "game_date": "2025-01-01", "balls": 0, "strikes": 2, "events": "strikeout", "launch_speed": None},
            ]
        )
    frame = pd.DataFrame(rows)

    shallow, two_strike = build_sequence_outcome_tables(frame)

    assert not shallow.empty
    assert not two_strike.empty
