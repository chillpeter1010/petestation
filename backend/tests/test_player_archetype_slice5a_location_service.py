from __future__ import annotations

import duckdb

from app.services.player_archetype_slice5_service import slice5_prediction_path
from app.services.player_archetype_slice5a_location_service import (
    CONTRACT_VERSION,
    get_player_archetype_slice5a,
    slice5a_pitch_path,
    slice5a_report_path,
)


def test_slice5a_contract_keeps_meatball_as_post_pitch_proxy() -> None:
    artifact = get_player_archetype_slice5a()

    assert artifact["contract_version"] == CONTRACT_VERSION
    assert artifact["meatball_contract"]["primary_rule"] == "Statcast zone == 5 (middle-middle)."
    assert artifact["release_gate"]["true_missed_target_supported"] is False
    assert artifact["release_gate"]["slice5_model_retrained"] is False


def test_slice5a_rows_match_frozen_predictions_and_are_unique() -> None:
    with duckdb.connect() as connection:
        row = connection.execute(
            """
            SELECT count(*) AS row_count,
                   count(*) - count(DISTINCT decision_id) duplicates,
                   count(*) FILTER (WHERE is_meatball_proxy AND statcast_zone <> 5) bad_primary_meatballs,
                   count(*) FILTER (WHERE feature_time_scope <> 'observed_post_pitch_explanation_only') bad_scope
            FROM read_parquet(?)
            """,
            [str(slice5a_pitch_path())],
        ).fetchone()
        prediction_rows = connection.execute(
            "SELECT count(*) FROM read_parquet(?)", [str(slice5_prediction_path())]
        ).fetchone()[0]

    assert row == (prediction_rows, 0, 0, 0)


def test_slice5a_meatball_rate_is_savant_scale_and_case_does_not_use_result_as_label() -> None:
    artifact = get_player_archetype_slice5a()
    example = artifact["case_823926_yamamoto_mccann"]

    assert 5.0 < artifact["audit"]["meatball_pct"] < 10.0
    assert len(example) == 2
    home_run_pitch = next(row for row in example if row["observed_pa_event"] == "home_run")
    assert home_run_pitch["is_meatball_proxy"] is False


def test_slice5a_report_is_utf8_and_states_interpretation_limit() -> None:
    report = slice5a_report_path().read_text(encoding="utf-8")

    assert "middle third horizontally and vertically" in report
    assert "not a verified command miss" in report
    assert "post-pitch explanation only" in report
