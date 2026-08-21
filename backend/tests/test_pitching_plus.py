from __future__ import annotations

import pandas as pd

from app.ml.pitching_plus import build_pitching_frame


def test_sequence_features_do_not_cross_plate_appearance_boundaries() -> None:
    rows = []
    for at_bat, speeds in [(1, [90.0, 92.0]), (2, [80.0])]:
        for pitch_number, speed in enumerate(speeds, start=1):
            rows.append(
                {
                    "season": 2026,
                    "game_pk": 1,
                    "at_bat_number": at_bat,
                    "pitch_number": pitch_number,
                    "pitch_uid": f"1-{at_bat}-{pitch_number}",
                    "game_date": "2026-04-01",
                    "game_type": "R",
                    "pitcher": 10,
                    "pitch_type": "FF",
                    "pitch_name": "4-Seam Fastball",
                    "release_speed": speed,
                    "pfx_x": -0.5,
                    "pfx_z": 1.2,
                    "release_spin_rate": 2300,
                    "spin_axis": 200,
                    "release_extension": 6.5,
                    "release_pos_x": -2.0,
                    "release_pos_z": 5.8,
                    "arm_angle": 45,
                    "plate_x": 0.1,
                    "plate_z": 2.5,
                    "sz_top": 3.5,
                    "sz_bot": 1.5,
                    "balls": 0,
                    "strikes": 0,
                    "outs_when_up": 0,
                    "on_1b": None,
                    "on_2b": None,
                    "on_3b": None,
                    "stand": "R",
                    "p_throws": "R",
                    "delta_run_exp": 0.01,
                    "description": "called_strike",
                    "events": None,
                    "launch_speed_angle": None,
                    "zone": 5,
                }
            )
    frame = build_pitching_frame(pd.DataFrame(rows))
    starts = frame[frame["sequence_position"].eq(1)]
    assert starts["previous_pitch_type"].tolist() == ["START", "START"]
    assert starts["delta_release_speed_from_previous"].tolist() == [0.0, 0.0]
    second = frame[frame["sequence_position"].eq(2)].iloc[0]
    assert second["previous_pitch_type"] == "FF"
    assert second["delta_release_speed_from_previous"] == 2.0
