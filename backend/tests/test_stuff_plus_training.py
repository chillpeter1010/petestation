import numpy as np
import pandas as pd

from app.ml.stuff_plus import STATCAST_ZONES, build_training_frame, score_pitch_types, standard_context_grid


def _raw_pitch(season: int, speed: float, pitch_type: str = "FF") -> dict[str, object]:
    return {
        "season": season,
        "pitcher": 1,
        "pitch_type": pitch_type,
        "pitch_name": "4-Seam Fastball" if pitch_type == "FF" else "Slider",
        "release_speed": speed,
        "pfx_x": -0.5,
        "pfx_z": 1.3,
        "release_spin_rate": 2300,
        "spin_axis": 190,
        "release_extension": 6.4,
        "release_pos_x": -1.7,
        "release_pos_z": 5.8,
        "arm_angle": 50,
        "plate_x": 0.1,
        "plate_z": 2.6,
        "zone": 5,
        "sz_top": 3.5,
        "sz_bot": 1.5,
        "balls": 0,
        "strikes": 0,
        "outs_when_up": 0,
        "on_1b": np.nan,
        "on_2b": np.nan,
        "on_3b": np.nan,
        "stand": "R",
        "p_throws": "R",
        "delta_run_exp": -0.05,
        "description": "swinging_strike",
        "events": np.nan,
        "launch_speed_angle": np.nan,
    }


def test_fastball_reference_is_isolated_by_pitcher_and_season():
    raw = pd.DataFrame([
        _raw_pitch(2024, 90.0),
        _raw_pitch(2024, 80.0, "SL"),
        _raw_pitch(2025, 100.0),
        _raw_pitch(2025, 80.0, "SL"),
    ])

    frame = build_training_frame(raw)
    slider_2024 = frame[(frame["season"] == 2024) & (frame["pitch_type"] == "SL")].iloc[0]
    slider_2025 = frame[(frame["season"] == 2025) & (frame["pitch_type"] == "SL")].iloc[0]

    assert slider_2024["velo_diff_from_fastball"] == -10.0
    assert slider_2025["velo_diff_from_fastball"] == -20.0


def test_standard_context_grid_builds_312_deterministic_weighted_tests():
    rows = []
    for stand in ["L", "R"]:
        for balls in range(4):
            for strikes in range(3):
                for zone in STATCAST_ZONES:
                    rows.append({
                        "stand": stand,
                        "balls": balls,
                        "strikes": strikes,
                        "zone": zone,
                        "plate_x": float(zone),
                        "plate_z_norm": float(zone) / 10.0,
                        "pitch_type": "FF" if zone <= 9 else "SL",
                    })
    frame = pd.DataFrame(rows)

    contexts, pitch_weights, global_weights = standard_context_grid(frame)

    assert len(contexts) == 2 * 12 * 13
    assert {int(row["zone_id"]) for row in contexts} == set(STATCAST_ZONES)
    assert np.isclose(sum({(row["stand"], row["balls"], row["strikes"]): row["stand_count_weight"] for row in contexts}.values()), 1.0)
    assert np.isclose(sum(pitch_weights["FF"].values()), 1.0)
    assert np.isclose(sum(pitch_weights["SL"].values()), 1.0)
    assert np.isclose(sum(global_weights.values()), 1.0)


class _ClassifierHead:
    classes_ = np.array([0, 1])


class _ConstantModel:
    named_steps = {"model": _ClassifierHead()}

    def predict_proba(self, frame):
        return np.tile(np.array([[0.25, 0.75]]), (len(frame), 1))


def test_score_pitch_types_shrinks_small_samples_toward_100():
    shapes = pd.DataFrame([
        {"Pitch": "Slider", "pitches": 10, "pitch_type": "SL", "p_throws": "R"},
        {"Pitch": "4-Seam", "pitches": 100, "pitch_type": "FF", "p_throws": "R"},
    ])
    for column in [
        "release_speed", "ivb", "adj_hb", "release_spin_rate", "release_extension",
        "release_pos_z", "adj_release_pos_x", "velo_diff_from_fastball",
        "ivb_diff_from_fastball", "hb_diff_from_fastball", "spin_axis_x", "spin_axis_y", "arm_angle",
    ]:
        shapes[column] = 1.0
    metadata = {
        "standard_contexts": [{
            "plate_x": 0.0, "plate_z_norm": 0.5, "balls": 0, "strikes": 0,
            "outs_when_up": 0, "on_1b": 0, "on_2b": 0, "on_3b": 0, "stand": "R",
        }],
        "stuff_plus_scale": {
            "mean_pitcher_value": 0.0, "sd_pitcher_value": 0.1,
            "season_shrinkage_pitches": 50, "outing_shrinkage_pitches": 10,
        },
        "temperature": 1.0,
        "run_values": {"ball": 0.05, "called_strike": -0.05},
    }

    scored = score_pitch_types(_ConstantModel(), metadata, shapes)

    assert scored.iloc[0]["stuff_plus"] < scored.iloc[1]["stuff_plus"]
    assert scored.iloc[0]["stuff_plus"] > 100


def test_score_pitch_types_uses_each_pitch_types_own_baseline():
    shapes = pd.DataFrame([
        {"Pitch": "Slider", "pitches": 100, "pitch_type": "SL", "p_throws": "R"},
        {"Pitch": "4-Seam", "pitches": 100, "pitch_type": "FF", "p_throws": "R"},
    ])
    for column in [
        "release_speed", "ivb", "adj_hb", "release_spin_rate", "release_extension",
        "release_pos_z", "adj_release_pos_x", "velo_diff_from_fastball",
        "ivb_diff_from_fastball", "hb_diff_from_fastball", "spin_axis_x", "spin_axis_y", "arm_angle",
    ]:
        shapes[column] = 1.0
    metadata = {
        "standard_contexts": [{
            "plate_x": 0.0, "plate_z_norm": 0.5, "balls": 0, "strikes": 0,
            "outs_when_up": 0, "on_1b": 0, "on_2b": 0, "on_3b": 0, "stand": "R",
        }],
        "stuff_plus_scale": {
            "mean_pitcher_value": 0.0, "sd_pitcher_value": 0.1,
            "season_shrinkage_pitches": 50, "outing_shrinkage_pitches": 10,
            "pitch_type_scales": {
                "SL": {"mean_pitcher_value": 0.025, "sd_pitcher_value": 0.1},
                "FF": {"mean_pitcher_value": 0.025, "sd_pitcher_value": 0.1},
            },
        },
        "temperature": 1.0,
        "run_values": {"ball": 0.05, "called_strike": -0.05},
    }

    scored = score_pitch_types(_ConstantModel(), metadata, shapes)

    assert scored["raw_stuff_plus"].tolist() == [100.0, 100.0]
    assert scored["scale_source"].tolist() == ["pitch_type:SL", "pitch_type:FF"]
