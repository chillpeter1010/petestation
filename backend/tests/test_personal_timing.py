import pandas as pd

from app.services.personal_service import build_timing_axis_points, build_timing_pitch_table


def test_build_timing_pitch_table_aggregates_swings():
    frame = pd.DataFrame(
        [
            {"pitch_name": "Sinker", "pitch_code": "SI", "n_swings": 10, "whiff_swings": 2, "miss_distance": 1.0},
            {"pitch_name": "Sinker", "pitch_code": "SI", "n_swings": 20, "whiff_swings": 4, "miss_distance": 2.0},
        ]
    )

    table = build_timing_pitch_table(frame)

    assert table.loc[0, "n_swings"] == 30
    assert table.loc[0, "whiff_rate"] == 0.2


def test_build_timing_axis_points_returns_weighted_points():
    frame = pd.DataFrame(
        [
            {"pitch_name": "Sinker", "n_swings": 10, "avg_x_tied_up": -5, "tied_up_percent": 0.2, "centered_percent": 0.7, "avg_x_flail": 5, "flailed_percent": 0.1},
        ]
    )

    points = build_timing_axis_points(frame, "x")

    assert {point["category"] for point in points} == {"Tied Up", "Centered", "Flail"}


def test_build_timing_axis_points_handles_missing_swings_column():
    frame = pd.DataFrame(
        [
            {"pitch_name": "Sinker", "avg_x_tied_up": -5, "tied_up_percent": 0.2},
        ]
    )

    points = build_timing_axis_points(frame, "x")

    assert points == []
