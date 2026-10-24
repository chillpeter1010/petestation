from __future__ import annotations

import duckdb

from app.services.player_archetype_slice5_service import (
    CONTRACT_VERSION,
    FAMILY_CLASSES,
    TEST_YEAR,
    TRAIN_YEARS,
    TYPE_CLASSES,
    get_player_archetype_slice5,
    slice5_prediction_path,
    slice5_report_path,
)


def test_slice5_contract_freezes_chronological_split_and_feature_boundary() -> None:
    artifact = get_player_archetype_slice5()

    assert artifact["contract_version"] == CONTRACT_VERSION
    assert artifact["status"] == "ready"
    assert artifact["scope"]["train_years"] == list(TRAIN_YEARS)
    assert artifact["scope"]["calibration_year"] == 2025
    assert artifact["scope"]["test_year"] == TEST_YEAR
    assert artifact["scope"]["test_used_for_selection"] is False
    assert artifact["feature_contract"]["post_decision_features_allowed"] is False
    assert artifact["feature_contract"]["player_ids_in_regularized_model"] is False
    assert artifact["selection"]["selected_base"] in {"regularized_context", "regularized_tags"}
    assert artifact["selection"]["selected_family_model"] in {
        "regularized_context",
        "regularized_tags",
        "player_only_update",
        "hierarchical_update",
    }


def test_slice5_2026_predictions_are_unique_complete_and_normalized() -> None:
    path = slice5_prediction_path()
    family_sum = " + ".join(f"prob_family_{label.lower()}" for label in FAMILY_CLASSES)
    type_sum = " + ".join(f"prob_type_{label.lower()}" for label in TYPE_CLASSES)
    with duckdb.connect() as connection:
        row = connection.execute(
            f"""
            SELECT
                count(*) AS rows,
                count(*) - count(DISTINCT decision_id) AS duplicates,
                count(*) FILTER (WHERE abs(({family_sum}) - 1.0) > 1e-7) AS bad_family_sum,
                count(*) FILTER (WHERE abs(({type_sum}) - 1.0) > 1e-8) AS bad_type_sum,
                count(*) FILTER (WHERE predicted_family IS NULL OR predicted_pitch_type IS NULL) AS null_predictions
            FROM read_parquet(?)
            """,
            [str(path)],
        ).fetchone()

    artifact = get_player_archetype_slice5()
    assert row[0] == artifact["rows"]["test_2026"] == 713_853
    assert row[1:] == (0, 0, 0, 0)


def test_slice5_hierarchical_result_and_cold_start_reporting_are_auditable() -> None:
    artifact = get_player_archetype_slice5()
    validation = artifact["validation_2025_second_half"]["family_models"]
    test = artifact["test_2026"]["family_models"]
    subgroups = artifact["test_2026"]["selected_model_subgroups"]

    assert validation["regularized_tags"]["log_loss"] < validation["regularized_context"]["log_loss"]
    assert validation["hierarchical_update"]["log_loss"] < validation["regularized_tags"]["log_loss"]
    assert test["hierarchical_update"]["log_loss"] < test["regularized_tags"]["log_loss"]
    assert subgroups["all_three_hard_cold"] == {"rows": 5, "status": "insufficient_for_metric"}
    assert artifact["selection"]["hierarchical_release_supported"] is True


def test_slice5_report_is_utf8_and_preserves_interpretation_limits() -> None:
    report = slice5_report_path().read_text(encoding="utf-8")
    assert "2021–2024 train" in report
    assert "never assigned an Average tag" in report
    assert "not proof of who called the pitch" in report
