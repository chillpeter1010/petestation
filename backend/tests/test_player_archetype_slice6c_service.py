from __future__ import annotations

import duckdb

from app.services.player_archetype_slice6ab_service import slice6a_candidate_path
from app.services.player_archetype_slice6c_service import (
    CONTRACT_VERSION,
    DEFAULT_PROPENSITY,
    MIN_THREAT_PITCHES,
    MIN_WEAPON_PITCHES,
    get_player_archetype_slice6c,
    slice6c_candidate_value_path,
    slice6c_decision_value_path,
    slice6c_report_path,
)


def test_slice6c_contract_preserves_time_support_and_claim_boundaries() -> None:
    artifact = get_player_archetype_slice6c()

    assert artifact["contract_version"] == CONTRACT_VERSION
    assert artifact["status"] == "ready"
    assert artifact["scope"]["development"] == "2025 first half"
    assert artifact["scope"]["validation"] == "2025 second half"
    assert artifact["scope"]["test"].startswith("2026")
    assert artifact["scope"]["slice5_retrained"] is False
    assert artifact["support_contract"]["minimum_pitcher_type_history"] == MIN_WEAPON_PITCHES
    assert artifact["support_contract"]["minimum_batter_context_history"] == MIN_THREAT_PITCHES
    assert artifact["support_contract"]["default_exact_type_propensity"] == DEFAULT_PROPENSITY
    assert artifact["release_gate"]["individual_best_pitch_ready"] is False
    assert artifact["release_gate"]["causal_claim_supported"] is False


def test_slice6c_candidate_values_are_complete_unique_by_decision_and_choice() -> None:
    with duckdb.connect() as connection:
        candidate = connection.execute(
            """
            SELECT count(*) AS row_count,
                   count(DISTINCT decision_id) AS decisions,
                   count(*) FILTER (WHERE is_chosen) AS chosen_rows,
                   count(*) FILTER (WHERE candidate_propensity IS NULL
                                      OR candidate_propensity < 0
                                      OR candidate_propensity > 1) AS bad_propensity,
                   count(*) FILTER (WHERE predicted_batter_run_value IS NULL) AS null_prediction
            FROM read_parquet(?)
            """,
            [str(slice6c_candidate_value_path())],
        ).fetchone()
        source = connection.execute(
            "SELECT count(*), count(DISTINCT decision_id) FROM read_parquet(?)",
            [str(slice6a_candidate_path())],
        ).fetchone()

    assert candidate[:2] == source
    assert candidate[2] == source[1]
    assert candidate[3:] == (0, 0)


def test_slice6c_decision_values_are_unique_and_remain_observational() -> None:
    with duckdb.connect() as connection:
        row = connection.execute(
            """
            SELECT count(*) AS row_count,
                   count(*) - count(DISTINCT decision_id) AS duplicates,
                   count(*) FILTER (WHERE supported_candidates >= 2) AS comparable,
                   count(*) FILTER (WHERE interpretation_scope <>
                       'supported_observational_comparison_not_causal') AS bad_scope,
                   count(*) FILTER (WHERE intervals_separate_in_alternative_favor) AS separated
            FROM read_parquet(?)
            """,
            [str(slice6c_decision_value_path())],
        ).fetchone()

    artifact = get_player_archetype_slice6c()
    assert row[0] == artifact["audit"]["decision_rows"]
    assert row[1] == 0
    assert row[2] == artifact["audit"]["default_multi_candidate_decisions"]
    assert row[3] == 0
    assert row[4] == artifact["audit"]["interval_separated_decisions"]


def test_slice6c_yamamoto_case_and_utf8_report_are_auditable() -> None:
    artifact = get_player_archetype_slice6c()
    candidates = artifact["case_823926_yamamoto_mccann_candidates"]
    decision = artifact["case_823926_yamamoto_mccann_decision"][0]

    assert next(row for row in candidates if row["candidate_pitch_type"] == "SI")["is_chosen"] is True
    assert decision["chosen_pitch_type"] == "SI"
    assert decision["interpretation_scope"] == "supported_observational_comparison_not_causal"
    report = slice6c_report_path().read_text(encoding="utf-8")
    assert "Individual best-pitch labels remain disabled" in report
    assert "single-pitch run value is noisy" in report
