import pandas as pd
import pytest

from app.services import batter_period_comparison_service as service


def _row(date: str, at_bat: int, pitch: int, description: str, event: str, **overrides):
    row = {
        "game_date": date,
        "game_pk": 1,
        "at_bat_number": at_bat,
        "pitch_number": pitch,
        "balls": 0,
        "strikes": 0,
        "events": event,
        "description": description,
        "stand": "L",
        "p_throws": "R",
        "pitch_type": "FF",
        "pitch_name": "4-Seam Fastball",
        "zone": 5,
        "plate_x": 0.1,
        "plate_z": 2.5,
        "launch_speed": None,
        "launch_angle": None,
        "launch_speed_angle": None,
        "bat_speed": None,
        "swing_length": None,
        "attack_angle": None,
        "attack_direction": None,
        "swing_path_tilt": None,
        "intercept_ball_minus_batter_pos_x_inches": None,
        "intercept_ball_minus_batter_pos_y_inches": None,
        "miss_distance": None,
        "estimated_woba_using_speedangle": None,
        "woba_value": 0.0,
        "woba_denom": 1.0,
    }
    row.update(overrides)
    return row


def sample_rows() -> pd.DataFrame:
    return service.normalize_batter_period_rows(pd.DataFrame([
        _row("2026-04-01", 1, 1, "ball", "", zone=11),
        _row(
            "2026-04-01", 1, 2, "hit_into_play", "single", launch_speed=100,
            launch_angle=15, launch_speed_angle=6, bat_speed=75,
            estimated_woba_using_speedangle=0.7, woba_value=0.9,
        ),
        _row("2026-04-02", 2, 1, "ball", "walk", zone=12, woba_value=0.7),
        _row("2026-07-01", 3, 1, "swinging_strike", "strikeout", bat_speed=65),
        _row(
            "2026-07-02", 4, 1, "hit_into_play", "sac_fly", launch_speed=90,
            launch_angle=30, launch_speed_angle=4, bat_speed=80, woba_denom=0,
        ),
    ]))


def test_core_metrics_keep_baseball_denominators_and_percent_units():
    metrics = service.compute_batter_period_metrics(sample_rows())

    assert metrics["pa"] == (4, 4)
    assert metrics["ab"] == (2, 4)
    assert metrics["avg"] == (0.5, 2)
    assert metrics["obp"] == (0.5, 4)
    assert metrics["slg"] == (0.5, 2)
    assert metrics["barrel_pct"] == (50.0, 2)
    assert metrics["hard_hit_pct"] == (50.0, 2)
    assert metrics["sweet_spot_pct"] == (100.0, 2)
    assert metrics["swing_pct"][1] == 5
    assert metrics["whiff_pct"] == (pytest.approx(100 / 3), 3)
    assert metrics["k_bb_pct"] == (0.0, 4)


def test_comparison_uses_shared_bat_speed_domain_and_b_minus_a_delta(monkeypatch):
    rows = sample_rows()
    monkeypatch.setattr(service, "load_batter_period_rows", lambda year, batter_id: rows.copy())
    monkeypatch.setattr(service, "list_batter_options", lambda year: [{
        "value": 10, "label": "Test Batter (TST)", "name": "Test Batter", "team": "TST",
        "games": 2, "plate_appearances": 4,
    }])

    payload = service.get_batter_period_comparison(
        batter_id=10,
        left_year=2026,
        right_year=2026,
        left_start="2026-04-01",
        left_end="2026-04-30",
        right_start="2026-07-01",
        right_end="2026-07-31",
    )

    pa = next(metric for metric in payload.metrics if metric.key == "pa")
    k_rate = next(metric for metric in payload.metrics if metric.key == "k_pct")
    assert (pa.period_a, pa.period_b, pa.delta) == (2, 2, 0)
    assert k_rate.delta_unit == "pp"
    assert k_rate.delta == 50.0
    assert payload.bat_speed_domain == [75.0, 80.0]
    assert payload.heatmaps["left"][1]["bat_speed"] == 75.0
    assert payload.heatmaps["right"][0]["bat_speed"] is None
    assert payload.heatmaps["right"][1]["bat_speed"] == 80.0


def test_filters_apply_the_same_context_to_each_period():
    rows = sample_rows()
    filtered = service.apply_batter_period_filters(
        rows,
        start_date="2026-01-01",
        end_date="2026-12-31",
        batter_side="L",
        pitcher_hand="R",
        count="0-0",
        pitch="4-Seam Fastball",
        pitch_result="In Play",
    )

    assert len(filtered) == 2
    assert filtered["description"].eq("hit_into_play").all()


def test_tracking_and_miss_distance_use_tracked_denominators():
    rows = sample_rows()
    rows.loc[rows["description"].eq("swinging_strike"), "miss_distance"] = 4.25
    rows.loc[rows["is_swing"], "swing_length"] = [7.0, 6.5, 7.2]

    metrics = service.compute_tracking_period_metrics(rows, cutoff=70)

    assert metrics["avg_bat_speed"] == (77.5, 2)
    assert metrics["fast_swing_pct"] == (100.0, 2)
    assert metrics["competitive_pct"] == (pytest.approx(200 / 3), 3)
    assert metrics["avg_swing_length"][1] == 3
    assert metrics["avg_miss_distance"] == (4.25, 1)
    assert metrics["squared_up_pct"] == (None, 0)
