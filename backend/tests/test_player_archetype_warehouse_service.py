from __future__ import annotations

import duckdb

from app.services.player_archetype_warehouse_service import (
    BATTER_NORMALIZED_FEATURES,
    CONTRACT_VERSION,
    PITCHER_NORMALIZED_FEATURES,
    batter_warehouse_path,
    get_player_archetype_warehouse_contract,
    pitcher_warehouse_path,
)


def test_slice1_contract_and_unique_keys() -> None:
    contract = get_player_archetype_warehouse_contract()
    assert contract["contract_version"] == CONTRACT_VERSION
    assert contract["status"] == "ready"
    assert contract["audit"]["pitcher_duplicate_keys"] == 0
    assert contract["audit"]["batter_duplicate_keys"] == 0
    assert contract["audit"]["pitcher_rows"] > 0
    assert contract["audit"]["batter_rows"] > 0
    assert len(contract["artifact_fingerprints"]["pitcher_sha256"]) == 64
    assert len(contract["artifact_fingerprints"]["batter_sha256"]) == 64


def test_slice1_keeps_plus_sources_and_missingness_separate() -> None:
    with duckdb.connect() as connection:
        pitcher_columns = {row[0] for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(pitcher_warehouse_path())]).fetchall()}
        batter_columns = {row[0] for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(batter_warehouse_path())]).fetchall()}
        pitcher_2022 = connection.execute(
            "SELECT count(per_pitch_stuff_plus), count(season_stuff_plus) FROM read_parquet(?) WHERE year = 2022",
            [str(pitcher_warehouse_path())],
        ).fetchone()
        batter_swing_shape = connection.execute(
            "SELECT year, count(*) FILTER (WHERE swing_shape_available) FROM read_parquet(?) GROUP BY year ORDER BY year",
            [str(batter_warehouse_path())],
        ).fetchall()
        cease_name = connection.execute(
            "SELECT display_name FROM read_parquet(?) WHERE player_id = 656302 LIMIT 1",
            [str(pitcher_warehouse_path())],
        ).fetchone()[0]
    assert {f"z_{feature}" for feature in PITCHER_NORMALIZED_FEATURES}.issubset(pitcher_columns)
    assert {f"z_{feature}" for feature in BATTER_NORMALIZED_FEATURES}.issubset(batter_columns)
    assert pitcher_2022[0] == 0
    assert pitcher_2022[1] > 0
    assert dict(batter_swing_shape)[2021] == 0
    assert dict(batter_swing_shape)[2024] > 0
    assert cease_name == "Dylan Cease"


def test_slice1_preserves_role_and_denominator_contracts() -> None:
    with duckdb.connect() as connection:
        pitcher_bad = connection.execute(
            """SELECT count(*) FROM read_parquet(?)
               WHERE whiffs > swings OR chase_swings > outside_pitches
                  OR first_pitch_strikes > first_pitches OR dominant_pitch_pitches > pitches""",
            [str(pitcher_warehouse_path())],
        ).fetchone()[0]
        batter_bad = connection.execute(
            """SELECT count(*) FROM read_parquet(?)
               WHERE whiffs > swings OR chase_swings > outside_pitches
                  OR zone_swings > zone_pitches OR hard_hit_balls > tracked_batted_balls""",
            [str(batter_warehouse_path())],
        ).fetchone()[0]
    assert pitcher_bad == 0
    assert batter_bad == 0
