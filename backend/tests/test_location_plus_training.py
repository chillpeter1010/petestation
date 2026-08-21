import numpy as np
import pandas as pd

from app.ml.location_plus import (
    MODEL_FEATURES,
    apply_temperature,
    build_training_frame,
    classify_outcome,
)


def _raw_frame() -> pd.DataFrame:
    base = {
        "game_date": "2026-04-01",
        "game_type": "R",
        "pitcher": 1,
        "pitch_type": "FF",
        "pitch_name": "4-Seam Fastball",
        "plate_x": 0.2,
        "plate_z": 2.5,
        "sz_top": 3.5,
        "sz_bot": 1.5,
        "balls": 1,
        "strikes": 1,
        "outs_when_up": 1,
        "on_1b": np.nan,
        "on_2b": 123,
        "on_3b": np.nan,
        "stand": "L",
        "p_throws": "R",
        "events": None,
        "delta_run_exp": -0.03,
        "season": 2026,
    }
    rows = []
    for description, contact in [("called_strike", np.nan), ("hit_into_play", 6)]:
        row = dict(base)
        row["description"] = description
        row["launch_speed_angle"] = contact
        rows.append(row)
    return pd.DataFrame(rows)


def test_outcome_mapping_includes_called_strike_and_barrel():
    assert classify_outcome(_raw_frame()).tolist() == ["called_strike", "barrel"]


def test_training_features_exclude_pitcher_identity_and_stuff():
    frame = build_training_frame(_raw_frame())
    assert set(MODEL_FEATURES).issubset(frame.columns)
    assert "pitcher" not in MODEL_FEATURES
    assert "release_speed" not in MODEL_FEATURES
    assert frame["plate_x_batter"].tolist() == [-0.2, -0.2]


def test_temperature_scaling_preserves_probability_rows():
    probabilities = np.array([[0.7, 0.3], [0.2, 0.8]])
    scaled = apply_temperature(probabilities, 1.2)
    assert np.allclose(scaled.sum(axis=1), 1.0)
