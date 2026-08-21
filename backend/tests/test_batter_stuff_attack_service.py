import pandas as pd

from app.services.batter_stuff_attack_service import build_stuff_attack_response


def _pitch(batter: int, score: float, description: str, rv: float, *, zone: bool = True, launch_speed=None, launch_speed_angle=None, xwoba=None, **tracking):
    row = {
        "batter": batter,
        "game_date": "2026-05-01",
        "pitch_type": "FF",
        "pitch_stuff_plus": score,
        "description": description,
        "balls": 0,
        "strikes": 0,
        "plate_x": 0.0 if zone else 1.2,
        "plate_z": 2.5,
        "sz_top": 3.5,
        "sz_bot": 1.5,
        "stand": "R",
        "p_throws": "R",
        "launch_speed": launch_speed,
        "launch_speed_angle": launch_speed_angle,
        "estimated_woba_using_speedangle": xwoba,
        "delta_run_exp": rv,
    }
    row.update(tracking)
    return row


def test_stuff_attack_separates_seen_swing_and_batted_ball_denominators():
    rows = [
        _pitch(1, 120, "hit_into_play", 0.5, launch_speed=101, launch_speed_angle=6, xwoba=0.72),
        _pitch(1, 118, "swinging_strike", -0.05),
        _pitch(1, 116, "ball", 0.03, zone=False),
        _pitch(2, 117, "foul", -0.02, launch_speed=99),
    ]
    response = build_stuff_attack_response(
        pd.DataFrame(rows),
        identities={1: ("Test Hitter", "SEA"), 2: ("Other Hitter", "BOS")},
        year=2026,
        minimum_pitches=0,
        batter_id=1,
    )

    hitter = next(row for row in response.leaderboard if row.batter_id == 1)
    assert hitter.pitches_seen == 3
    assert hitter.swings == 2
    assert hitter.batted_balls == 1
    assert hitter.swing_pct == 66.667
    assert hitter.contact_pct == 50.0
    assert hitter.hard_hit_pct == 100.0
    assert hitter.barrel_pct == 100.0
    assert hitter.xwoba_contact == 0.72
    assert hitter.rv_per_100_seen == 16.0
    assert response.selected_batter is not None
    assert len(response.response_curve) == 4


def test_stuff_attack_applies_pitch_family_bin_and_minimum():
    rows = [
        _pitch(1, 114.9, "called_strike", -0.03),
        _pitch(1, 115.0, "foul", -0.01),
        _pitch(2, 120.0, "ball", 0.02),
    ]
    response = build_stuff_attack_response(
        pd.DataFrame(rows),
        identities={},
        year=2026,
        stuff_bin="115_plus",
        minimum_pitches=2,
    )

    assert response.matched_pitches == 2
    assert response.matched_batters == 2
    assert response.qualifying_batters == 0
    assert response.leaderboard == []


def test_stuff_attack_exposes_tracking_axes_with_their_own_samples():
    rows = [
        _pitch(1, 120, "hit_into_play", 0.4, launch_speed=100, bat_speed=76, swing_length=7.0, attack_angle=12, swing_path_tilt=30, launch_angle=22),
        _pitch(1, 119, "swinging_strike", -0.1, bat_speed=74, swing_length=6.8, attack_angle=4, swing_path_tilt=28, miss_distance=2.5),
        _pitch(1, 118, "called_strike", -0.02),
    ]
    response = build_stuff_attack_response(pd.DataFrame(rows), identities={}, year=2026, minimum_pitches=0)
    hitter = response.leaderboard[0]

    assert len(response.filters.axis_options) == 20
    assert hitter.axis_metrics["avg_exit_velocity"] == 100.0
    assert hitter.axis_metrics["avg_swing_length"] == 6.9
    assert hitter.axis_metrics["ideal_attack_angle_pct"] == 50.0
    assert hitter.axis_metrics["avg_miss_distance"] == 2.5
    assert hitter.axis_samples["avg_exit_velocity"] == 1
    assert hitter.axis_samples["avg_miss_distance"] == 1


def test_stuff_attack_supports_multi_pitch_selection_and_pitcher_hand():
    rows = [
        _pitch(1, 120, "called_strike", -0.01, pitch_type="FF", p_throws="L"),
        _pitch(1, 121, "swinging_strike", -0.02, pitch_type="SL", p_throws="L"),
        _pitch(1, 122, "ball", 0.01, pitch_type="CH", p_throws="R"),
        _pitch(2, 123, "called_strike", -0.01, pitch_type="CU", p_throws="L"),
    ]
    response = build_stuff_attack_response(
        pd.DataFrame(rows),
        identities={},
        year=2026,
        pitch_types=("FF", "SL", "CH"),
        pitcher_hand="L",
        minimum_pitches=0,
    )

    assert response.selected_pitch_types == ["FF", "SL", "CH"]
    assert response.pitcher_hand == "L"
    assert response.matched_pitches == 2
    assert response.matched_batters == 1
    assert response.filters.pitch_type_groups
