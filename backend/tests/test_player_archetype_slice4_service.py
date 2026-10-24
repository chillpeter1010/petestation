from __future__ import annotations

import duckdb

from app.services.player_archetype_slice4_service import (
    CONTRACT_VERSION,
    get_player_archetype_slice4,
    slice4_report_path,
    slice4_warehouse_path,
)


def test_real_slice4_artifact_has_complete_integrity_contract() -> None:
    artifact = get_player_archetype_slice4()

    assert artifact["contract_version"] == CONTRACT_VERSION
    assert artifact["status"] == "ready"
    assert artifact["integrity_passed"] is True
    assert [row["year"] for row in artifact["audits"]] == list(range(2021, 2027))
    assert all(row["source_row_match"] for row in artifact["audits"])
    assert all(row["duplicate_decision_ids"] == 0 for row in artifact["audits"])
    assert all(row["pa_boundary_errors"] == 0 for row in artifact["audits"])
    assert all(row["prior_map_mismatch_rows"] == 0 for row in artifact["audits"])
    assert artifact["feature_policy"]["current_season_full_year_tags_allowed"] is False


def test_yamamoto_mccann_replay_uses_only_prior_information() -> None:
    path = slice4_warehouse_path(2026)
    with duckdb.connect() as connection:
        rows = connection.execute(
            """
            SELECT pitch_number, target_pitch_type, observed_description,
                   prior_pitch_type, prior_pitch_result,
                   prior_pitcher_count_side_pitches, prior_catcher_context_pitches,
                   prior_pair_context_pitches, prior_h2h_pitches,
                   pitcher_prior_tag_1, batter_prior_tag_1, prior_tag_year
            FROM read_parquet(?)
            WHERE game_pk = 823926 AND pitcher_id = 808967 AND batter_id = 543510
              AND at_bat_number = 44
            ORDER BY pitch_number
            """,
            [str(path)],
        ).fetchall()

    assert len(rows) == 2
    first, second = rows
    assert first[0:3] == (1, "FF", "ball")
    assert first[3] is None and first[4] is None
    assert first[5:9] == (212, 23, 0, 5)
    assert second[0:3] == (2, "SI", "hit_into_play")
    assert second[3:5] == ("FF", "ball")
    assert second[5:9] == (82, 11, 0, 6)
    assert first[9] == "Multi-Pitch SP"
    assert first[10] == "Balanced Decision"
    assert first[11] == 2025


def test_slice4_report_is_utf8_and_documents_target_boundary() -> None:
    report = slice4_report_path().read_text(encoding="utf-8")
    assert "A–D deliverables" in report
    assert "`target_*` is the action to predict" in report
    assert "Same-season full-year tags are forbidden" in report
