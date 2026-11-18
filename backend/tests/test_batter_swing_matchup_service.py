from pathlib import Path

import duckdb
import pytest

from app.services import batter_swing_matchup_service as service


def _database(path: Path, include_miss: bool = True) -> None:
    miss_column = ", miss_distance DOUBLE" if include_miss else ""
    conn = duckdb.connect(str(path))
    conn.execute(f"""
        CREATE TABLE pitches_enriched (
            batter_id BIGINT, pitch_type VARCHAR, pitch_name VARCHAR, description VARCHAR,
            pitcher_team VARCHAR, batter_team VARCHAR, p_throws VARCHAR, stand VARCHAR,
            bat_speed DOUBLE, launch_speed DOUBLE, swing_length DOUBLE,
            attack_angle DOUBLE, attack_direction DOUBLE, swing_path_tilt DOUBLE{miss_column}
        )
    """)
    columns = "batter_id,pitch_type,pitch_name,description,pitcher_team,batter_team,p_throws,stand,bat_speed,launch_speed,swing_length,attack_angle,attack_direction,swing_path_tilt"
    values = [
        (1, "FF", "4-Seam Fastball", "hit_into_play", "NYY", "BOS", "R", "R", 80, 100, 7.0, 12, 2, 30),
        (1, "FF", "4-Seam Fastball", "swinging_strike", "NYY", "BOS", "R", "R", 70, None, 7.2, 10, 3, 31),
        (1, "SL", "Slider", "swinging_strike", "TOR", "BOS", "R", "R", 76, None, 7.1, 8, -1, 32),
        (1, "FF", "4-Seam Fastball", "foul_bunt", "NYY", "BOS", "R", "R", 60, None, 5.0, 0, 0, 0),
    ]
    if include_miss:
        columns += ",miss_distance"
        values = [(*row, 5.0 if row[3] == "swinging_strike" else None) for row in values]
    placeholders = ",".join("?" for _ in values[0])
    conn.executemany(f"INSERT INTO pitches_enriched ({columns}) VALUES ({placeholders})", values)
    conn.close()


def test_pitcher_team_filter_is_exact_and_excludes_bunts(tmp_path, monkeypatch):
    path = tmp_path / "2026.duckdb"
    _database(path)
    monkeypatch.setattr(service, "get_season_duckdb_path", lambda year, root: path)
    monkeypatch.setattr(service, "list_batter_leaderboard", lambda year: [{"player_id": 1, "name": "Test Batter", "team": "BOS", "plate_appearances": 200}])
    service._season_bat_speed_baselines.cache_clear()

    rows, league, matched, warnings = service.build_matchup_rows(2026, pitcher_team="NYY", data_dir=tmp_path)

    assert matched == 2
    assert not warnings
    assert rows[0].name == "Test Batter"
    assert rows[0].whiff_pct == 50.0
    assert rows[0].miss_distance == 5.0
    assert league is not None and league.n_swings == 2


def test_missing_historical_miss_distance_is_reported(tmp_path, monkeypatch):
    path = tmp_path / "2025.duckdb"
    _database(path, include_miss=False)
    monkeypatch.setattr(service, "get_season_duckdb_path", lambda year, root: path)
    monkeypatch.setattr(service, "list_batter_leaderboard", lambda year: [{"player_id": 1, "name": "Test Batter", "team": "BOS", "plate_appearances": 200}])
    service._season_bat_speed_baselines.cache_clear()

    rows, _, _, warnings = service.build_matchup_rows(2025, pitcher_team="NYY", data_dir=tmp_path)

    assert rows[0].miss_distance is None
    assert any("Miss Distance" in warning for warning in warnings)


def test_filtered_batting_metrics_keep_untracked_pa_and_exact_context(tmp_path, monkeypatch):
    path = tmp_path / "metrics.duckdb"
    with duckdb.connect(str(path)) as conn:
        conn.execute("""CREATE TABLE pitches (
            game_type VARCHAR, game_pk BIGINT, at_bat_number BIGINT, pitch_number BIGINT,
            batter BIGINT, pitch_type VARCHAR, description VARCHAR, events VARCHAR,
            bat_speed DOUBLE, attack_angle DOUBLE, launch_speed DOUBLE,
            p_throws VARCHAR, stand VARCHAR, batter_team VARCHAR, pitcher_team VARCHAR
        )""")
        rows = [
            ('R', 1, 1, 1, 10, 'FF', 'swinging_strike', '', 80, 5, None, 'R', 'L', 'DET', 'NYY'),
            ('R', 1, 1, 2, 10, 'FF', 'swinging_strike', 'strikeout', 80, 20, None, 'R', 'L', 'DET', 'NYY'),
            ('R', 1, 2, 1, 10, 'FF', 'ball', 'walk', None, None, None, 'R', 'L', 'DET', 'NYY'),
            ('R', 1, 3, 1, 10, 'FF', 'hit_into_play', 'single', 80, 25, 100, 'R', 'L', 'DET', 'NYY'),
            ('R', 1, 4, 1, 10, 'FF', 'hit_by_pitch', 'hit_by_pitch', None, None, None, 'R', 'L', 'DET', 'NYY'),
            # A bunt with tracking is not a regular swing; its PA still belongs in K/BB's denominator.
            ('R', 1, 5, 1, 10, 'FF', 'foul_bunt', 'strikeout', 80, 10, None, 'R', 'L', 'DET', 'NYY'),
            ('R', 2, 1, 1, 10, 'SL', 'called_strike', 'strikeout', None, None, None, 'L', 'L', 'DET', 'BOS'),
            ('R', 3, 1, 1, 10, 'FF', 'ball', 'intent_walk', None, None, None, 'R', 'L', 'LAD', 'NYY'),
            ('S', 4, 1, 1, 10, 'FF', 'called_strike', 'strikeout', None, None, None, 'R', 'L', 'DET', 'NYY'),
            ('R', 5, 1, 1, 20, 'FF', 'ball', 'walk', None, None, None, 'R', 'R', 'DET', 'NYY'),
        ]
        # Exact duplicate terminal rows must not double-count a PA or tracked swing.
        rows.append(rows[1])
        conn.executemany('INSERT INTO pitches VALUES (' + ','.join('?' for _ in range(15)) + ')', rows)
    monkeypatch.setattr(service, 'get_season_duckdb_path', lambda *args: path)
    service._cached_filtered_batting_metrics.cache_clear()
    selected = service.filtered_batting_metrics(2026, {'FF'}, 'R', 'L', 'DET', 'NYY', tmp_path)[10]
    assert selected['context_pa'] == 5
    assert selected['k_pct'] == 40
    assert selected['bb_pct'] == 20
    assert selected['k_bb_pct'] == 20
    assert selected['avg_bat_speed'] == 80
    assert selected['bat_speed_swings'] == 3
    assert selected['attack_angle_swings'] == 3
    assert selected['ideal_attack_angle_pct'] == pytest.approx(66.667)
    assert 20 not in service.filtered_batting_metrics(2026, {'FF'}, 'R', 'L', 'DET', 'NYY', tmp_path)
    # Untracked PA metrics remain available while tracking metrics are null, not zero.
    slider = service.filtered_batting_metrics(2026, {'SL'}, 'L', data_dir=tmp_path)[10]
    assert slider['context_pa'] == 1 and slider['k_pct'] == 100 and slider['bb_pct'] == 0
    assert slider['avg_bat_speed'] is None and slider['ideal_attack_angle_pct'] is None
    assert slider['attack_angle_swings'] == 0
    # The same player with a different batting team has a different result, not a season fallback.
    traded = service.filtered_batting_metrics(2026, {'FF'}, 'R', 'L', 'LAD', 'NYY', tmp_path)[10]
    assert traded['context_pa'] == 1 and traded['bb_pct'] == 100 and traded['k_bb_pct'] == -100


def test_filtered_batting_metrics_leave_unavailable_sources_empty(tmp_path, monkeypatch):
    path = tmp_path / 'missing.duckdb'
    monkeypatch.setattr(service, 'get_season_duckdb_path', lambda *args: path)
    assert service.filtered_batting_metrics(2026, data_dir=tmp_path) == {}
