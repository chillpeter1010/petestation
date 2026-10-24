from __future__ import annotations

import duckdb

from app.services.player_archetype_slice6c_service import DEFAULT_PROPENSITY
from app.services.player_archetype_slice6d_service import (
    CONTRACT_VERSION,
    get_player_archetype_slice6d,
    slice6d_decision_diagnostic_path,
    slice6d_report_path,
    slice6d_subgroup_path,
)


def test_slice6d_contract_freezes_inputs_and_exploitability_boundary() -> None:
    artifact = get_player_archetype_slice6d()

    assert artifact["contract_version"] == CONTRACT_VERSION
    assert artifact["status"] == "ready"
    assert artifact["scope"]["model_refit"] is False
    assert artifact["scope"]["post_pitch_features_allowed"] is False
    assert artifact["release_gate"]["aggregate_entropy_diagnostic_ready"] is True
    assert artifact["release_gate"]["true_exploitability_ready"] is False
    assert artifact["release_gate"]["individual_strategy_advice_ready"] is False
    assert artifact["release_gate"]["research_only"] is True


def test_slice6d_decision_diagnostics_are_unique_bounded_and_noncausal() -> None:
    with duckdb.connect() as connection:
        row = connection.execute(
            """
            SELECT count(*) AS row_count,
                   count(*) - count(DISTINCT propensity_threshold || ':' || decision_id)
                     AS duplicates,
                   count(*) FILTER (WHERE supported_candidates < 2) AS bad_support,
                   count(*) FILTER (WHERE normalized_entropy < -1e-10
                                      OR normalized_entropy > 1.0000001) AS bad_entropy,
                   count(*) FILTER (WHERE effective_supported_choices < 1
                                      OR effective_supported_choices > supported_candidates + 1e-8)
                     AS bad_effective_choices,
                   count(*) FILTER (WHERE supported_deviation_gain < -1e-10)
                     AS negative_deviation,
                   count(*) FILTER (WHERE interpretation_scope <>
                     'one_sided_supported_deviation_not_true_exploitability') AS bad_scope
            FROM read_parquet(?)
            """,
            [str(slice6d_decision_diagnostic_path())],
        ).fetchone()

    artifact = get_player_archetype_slice6d()
    assert row[0] == artifact["audit"]["diagnostic_rows"]
    assert row[1:] == (0, 0, 0, 0, 0, 0)


def test_slice6d_subgroup_intervals_and_threshold_sensitivity_are_auditable() -> None:
    with duckdb.connect() as connection:
        row = connection.execute(
            """
            SELECT count(*) FILTER (WHERE entropy_lower_90 > mean_normalized_entropy
                                      OR entropy_upper_90 < mean_normalized_entropy),
                   count(*) FILTER (WHERE deviation_lower_90 > mean_supported_deviation_gain
                                      OR deviation_upper_90 < mean_supported_deviation_gain),
                   count(*) FILTER (WHERE decisions < 500 AND
                                      abs(propensity_threshold - ?) < 1e-12)
            FROM read_parquet(?)
            """,
            [DEFAULT_PROPENSITY, str(slice6d_subgroup_path())],
        ).fetchone()

    artifact = get_player_archetype_slice6d()
    assert row == (0, 0, 0)
    assert len(artifact["threshold_sensitivity"]) == 4
    assert artifact["release_gate"]["entropy_threshold_stability_ready"] is False
    assert artifact["release_gate"]["entropy_leaderboard_ready"] is False


def test_slice6d_yamamoto_case_and_utf8_report_preserve_uncertainty() -> None:
    artifact = get_player_archetype_slice6d()
    case = artifact["case_823926_yamamoto_mccann"][0]

    assert case["chosen_pitch_type"] == "SI"
    assert case["best_supported_pitch_type"] == "FS"
    assert case["chosen_gap_vs_best_supported"] < case["single_pitch_residual_half_width_90"]
    assert case["deviation_exceeds_noise_floor"] is False
    report = slice6d_report_path().read_text(encoding="utf-8")
    assert "not true exploitability" in report
    assert "cannot support a factual-best-pitch" in report
