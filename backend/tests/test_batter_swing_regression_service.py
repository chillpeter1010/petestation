import duckdb
import pandas as pd
import pytest

from app.api.schemas.batter_swing_timing import SwingTimingLeaderboardRow, SwingTimingResponse
from app.services import batter_swing_regression_service as service
from app.services.batter_stuff_attack_service import AXIS_OPTIONS, _add_metric_flags, _aggregate_batters


def _frame():
    rows = []
    for player, pitch_type, hand, team, opponent in [(1, 'FF', 'R', 'DET', 'NYY'), (2, 'FF', 'R', 'BOS', 'NYY'), (1, 'SL', 'L', 'DET', 'BOS')]:
        for index, description in enumerate(['ball', 'swinging_strike', 'hit_into_play']):
            rows.append(dict(batter=player, game_type='R', game_pk=len(rows) + 1,
                at_bat_number=1, pitch_number=1, pitch_type=pitch_type, description=description,
                p_throws=hand, stand='L', batter_team=team, pitcher_team=opponent,
                balls=0, strikes=0, plate_x=1.1 if index == 0 else .1, plate_z=2.5,
                sz_top=3.5, sz_bot=1.5, launch_speed=100.0 if index == 2 else None,
                launch_speed_angle=6 if index == 2 else None,
                estimated_woba_using_speedangle=.6 if index == 2 else None,
                delta_run_exp=.4 if index == 2 else -.03, bat_speed=75.0 if index else None,
                swing_length=7.0, attack_angle=12.0, swing_path_tilt=30.0,
                miss_distance=3.0 if index == 1 else None, launch_angle=20.0))
    return pd.DataFrame(rows)


def test_vectorized_axes_match_existing_stuff_attack_formulas():
    data = _add_metric_flags(_frame())
    expected = _aggregate_batters(data, {})
    actual = service._grouped_axes(data)
    for row in expected:
        for option in AXIS_OPTIONS:
            key = option['key']
            assert actual[row.batter_id][0][key] == pytest.approx(row.axis_metrics[key]) if row.axis_metrics[key] is not None else actual[row.batter_id][0][key] is None


def test_regression_union_uses_exact_filters_and_copies_models(tmp_path, monkeypatch):
    path = tmp_path / 'axes.duckdb'
    frame = _frame()
    with duckdb.connect(str(path)) as conn:
        conn.register('source', frame)
        conn.execute('CREATE TABLE pitches AS SELECT * FROM source')
    monkeypatch.setattr(service, 'get_season_duckdb_path', lambda *args: path)
    service._cached_regression_axes.cache_clear()
    row = SwingTimingLeaderboardRow(batter_id=1, name='Test', avg_bat_speed=72.3,
        n_swings=100, context_pa=20, k_pct=10, bb_pct=15, k_bb_pct=-5,
        miss_distance=2.5, on_time_pct=70, avg_late_ms=-12)
    base = SwingTimingResponse(year=2026, pitch_type='FF', pitcher_hand='R', batter_team='DET',
        pitcher_team='NYY', batter_side='L', leaderboard=[row])
    enriched = service.add_swing_timing_regression(base, tmp_path)
    keys = [o['key'] for o in enriched.filters.axis_options]
    assert len(keys) == len(set(keys)) == 45
    assert {o['key'] for o in AXIS_OPTIONS}.issubset(keys)
    result = enriched.leaderboard[0]
    assert result.axis_metrics['on_time_pct'] == 70
    assert result.axis_metrics['avg_late_ms'] == 12
    assert result.axis_metrics['k_bb_pct'] == -5
    assert result.axis_metrics['avg_bat_speed'] == 72.3
    assert result.axis_metrics['avg_miss_distance'] == 2.5
    assert result.axis_metrics['avg_exit_velocity'] == 100
    assert result.axis_metrics['over_pct'] is None
    assert result.axis_samples['swing_pct'] == 3  # Only DET / NYY / FF / R / L.
    assert base.leaderboard[0].axis_metrics == {}
    assert base.filters.axis_options == []


def test_unavailable_event_axes_stay_missing_but_timing_summary_remains(tmp_path):
    row = SwingTimingLeaderboardRow(batter_id=1, name='Test', perfect_pct=30)
    result = service.add_swing_timing_regression(SwingTimingResponse(year=1999, leaderboard=[row]), tmp_path)
    assert result.leaderboard[0].axis_metrics['perfect_pct'] == 30
    assert result.leaderboard[0].axis_metrics.get('avg_exit_velocity') is None
