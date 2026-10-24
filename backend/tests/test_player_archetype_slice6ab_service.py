from __future__ import annotations

import duckdb

from app.services.player_archetype_slice4_service import slice4_warehouse_path
from app.services.player_archetype_slice6ab_service import (
    CONTRACT_VERSION,
    get_player_archetype_slice6ab,
    slice6a_candidate_path,
    slice6a_chosen_path,
    slice6ab_report_path,
    slice6b_surface_path,
)


def test_slice6ab_contract_preserves_time_and_causal_boundaries() -> None:
    artifact = get_player_archetype_slice6ab()

    assert artifact["contract_version"] == CONTRACT_VERSION
    assert artifact["status"] == "ready"
    assert artifact["scope"]["slice5_retrained"] is False
    assert artifact["scope"]["threat_history_years"] == [2021, 2022, 2023, 2024, 2025]
    assert artifact["release_gate"]["counterfactual_best_pitch_supported"] is False
    assert artifact["release_gate"]["causal_claim_supported"] is False


def test_slice6a_has_one_chosen_weapon_row_per_decision_without_future_counts() -> None:
    with duckdb.connect() as connection:
        candidate = connection.execute(
            """
            SELECT count(DISTINCT decision_id) decisions,
                   count(*) FILTER (WHERE is_chosen) chosen,
                   count(*) FILTER (WHERE outing_prior_type_pitches < 0
                                      OR outing_prior_type_pitches > appearance_pitch_number - 1) bad_prior,
                   count(*) FILTER (WHERE NOT is_chosen AND
                                      (observed_chosen_stuff_plus IS NOT NULL
                                       OR observed_chosen_location_plus IS NOT NULL)) observed_on_alternative
            FROM read_parquet(?)
            """,
            [str(slice6a_candidate_path())],
        ).fetchone()
        chosen = connection.execute(
            """
            SELECT count(*) AS row_count, count(*) - count(DISTINCT decision_id) AS duplicates,
                   count(*) FILTER (WHERE target_pitch_type <> candidate_pitch_type) mismatches
            FROM read_parquet(?)
            """,
            [str(slice6a_chosen_path())],
        ).fetchone()
        warehouse_rows = connection.execute(
            "SELECT count(*) FROM read_parquet(?)", [str(slice4_warehouse_path(2026))]
        ).fetchone()[0]

    assert candidate == (warehouse_rows, warehouse_rows, 0, 0)
    assert chosen == (warehouse_rows, 0, 0)


def test_slice6b_uses_only_pre_2026_history_and_has_complete_metrics() -> None:
    with duckdb.connect() as connection:
        row = connection.execute(
            """
            SELECT count(*) FILTER (WHERE hunt_plus IS NULL OR contact_plus IS NULL OR damage_plus IS NULL),
                   count(*) FILTER (WHERE feature_time_scope NOT LIKE '2021-2025%'),
                   count(*) FILTER (WHERE surface_level = 'league' AND
                                      (hunt_plus <> 100 OR contact_plus <> 100 OR damage_plus <> 100))
            FROM read_parquet(?)
            """,
            [str(slice6b_surface_path())],
        ).fetchone()

    assert row == (0, 0, 0)


def test_slice6ab_yamamoto_case_and_utf8_report_are_auditable() -> None:
    artifact = get_player_archetype_slice6ab()
    example = artifact["case_823926_yamamoto_mccann_before_home_run"]
    fastball = next(row for row in example if row["candidate_pitch_type"] == "FF")
    sinker = next(row for row in example if row["candidate_pitch_type"] == "SI")

    assert fastball["weapon_stuff_delta"] < 0
    assert sinker["is_chosen"] is True
    report = slice6ab_report_path().read_text(encoding="utf-8")
    assert "earlier pitches in the same game" in report
    assert "do not yet identify a factual best unthrown pitch" in report
