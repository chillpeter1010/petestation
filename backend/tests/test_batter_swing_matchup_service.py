from pathlib import Path

import duckdb

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
