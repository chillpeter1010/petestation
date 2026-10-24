from __future__ import annotations

import duckdb

from app.services.player_archetype_slice2a_service import (
    CONTRACT_VERSION,
    get_player_archetype_slice2a,
    slice2a_tags_path,
)


def test_slice2a_contract_and_unique_dimensions() -> None:
    contract = get_player_archetype_slice2a()
    assert contract["contract_version"] == CONTRACT_VERSION
    assert contract["status"] == "ready"
    assert contract["audit"]["duplicate_entity_dimensions"] == 0
    assert contract["audit"]["rows"] == contract["audit"]["entities"] * 4


def test_slice2a_named_examples_are_interpretable() -> None:
    with duckdb.connect() as connection:
        rows = connection.execute(
            """SELECT display_name, dimension, tag FROM read_parquet(?)
               WHERE year = 2026 AND display_name IN ('Paul Sewald', 'Seth Lugo', 'Trey Yesavage', 'Chris Sale')""",
            [str(slice2a_tags_path())],
        ).fetchall()
    tags = {(name, dimension): tag for name, dimension, tag in rows}
    assert tags[("Paul Sewald", "arsenal_depth")] == "Two-Pitch RP"
    assert tags[("Paul Sewald", "primary_pair")] == "FF-ST Primary Pair"
    assert tags[("Seth Lugo", "arsenal_depth")] == "Versatile SP"
    assert tags[("Trey Yesavage", "arm_slot")] == "RHP Overhand"
    assert tags[("Chris Sale", "arm_slot")] == "LHP Sidearm"


def test_slice2a_arm_angle_uses_supported_official_values() -> None:
    with duckdb.connect() as connection:
        bad = connection.execute(
            """SELECT count(*) FROM read_parquet(?)
               WHERE dimension = 'arm_slot' AND tag IS NOT NULL
                 AND arm_angle_coverage_pct < 70""",
            [str(slice2a_tags_path())],
        ).fetchone()[0]
        yesavage = connection.execute(
            """SELECT arm_angle_median FROM read_parquet(?)
               WHERE year = 2026 AND display_name = 'Trey Yesavage'
                 AND role = 'SP' AND dimension = 'arm_slot'""",
            [str(slice2a_tags_path())],
        ).fetchone()[0]
    assert bad == 0
    assert 60 <= yesavage <= 70
