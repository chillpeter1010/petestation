from __future__ import annotations

import duckdb
import numpy as np

from app.services.player_archetype_challenger_service import (
    BATTER_SPECS,
    CONTRACT_VERSION,
    PITCHER_SPECS,
    _component_labels,
    _nearest_prototype,
    batter_tags_path,
    get_player_archetype_challenger,
    pitcher_tags_path,
)


def test_named_prototypes_are_shared_by_rules_and_components() -> None:
    for spec in PITCHER_SPECS + BATTER_SPECS:
        values = np.asarray(list(spec.prototypes.values()), dtype=float)
        expected = list(spec.prototypes)
        assert _nearest_prototype(values, spec).tolist() == expected
        assert list(_component_labels(values, spec).values()) == expected


def test_slice2_contract_and_assignment_gates() -> None:
    contract = get_player_archetype_challenger()
    assert contract["contract_version"] == CONTRACT_VERSION
    assert contract["status"] == "ready"
    assert contract["audit"]["pitcher"]["duplicate_entity_dimensions"] == 0
    assert contract["audit"]["batter"]["duplicate_entity_dimensions"] == 0
    assert all(model["selected_components"] in range(2, 6) for model in contract["model_diagnostics"])
    assert all(model["bootstrap_iterations_completed"] > 0 for model in contract["model_diagnostics"])
    sp_arsenal = next(
        model
        for model in contract["model_diagnostics"]
        if model["population"] == "pitcher" and model["cohort"] == "SP" and model["dimension"] == "arsenal"
    )
    assert sp_arsenal["publication_gate_passed"] is False
    assert sp_arsenal["supported_rows"] == 0

    with duckdb.connect() as connection:
        for path in (pitcher_tags_path(), batter_tags_path()):
            invalid = connection.execute(
                """SELECT count(*) FROM read_parquet(?)
                   WHERE published_tag IS NOT NULL
                     AND assignment_status NOT IN ('supported', 'supported_context')""",
                [str(path)],
            ).fetchone()[0]
            unsupported = connection.execute(
                """SELECT count(*) FROM read_parquet(?)
                   WHERE assignment_status = 'supported'
                     AND (membership_probability < 0.50 OR bootstrap_stability < 0.65)""",
                [str(path)],
            ).fetchone()[0]
            assert invalid == 0
            assert unsupported == 0


def test_slice2_retains_nulls_and_full_season_scope() -> None:
    with duckdb.connect() as connection:
        batter_missing_shape = connection.execute(
            """SELECT count(*) FROM read_parquet(?)
               WHERE dimension = 'swing_shape' AND assignment_status = 'unavailable'
                 AND published_tag IS NULL""",
            [str(batter_tags_path())],
        ).fetchone()[0]
        bad_scope = connection.execute(
            """SELECT count(*) FROM read_parquet(?)
               WHERE feature_time_scope <> 'full_season_descriptive'""",
            [str(pitcher_tags_path())],
        ).fetchone()[0]
        pitcher_tag_counts = connection.execute(
            """SELECT min(tag_count), max(tag_count) FROM (
                   SELECT year, player_id, role, count(published_tag) AS tag_count
                   FROM read_parquet(?) GROUP BY year, player_id, role
               )""",
            [str(pitcher_tags_path())],
        ).fetchone()
    assert batter_missing_shape > 0
    assert bad_scope == 0
    assert 0 <= pitcher_tag_counts[0] <= pitcher_tag_counts[1] <= 4
