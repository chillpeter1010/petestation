from __future__ import annotations

from app.services.player_archetype_audit_service import (
    CONTRACT_VERSION,
    archetype_slice0_report_path,
    get_player_archetype_slice0_audit,
)


def test_real_slice0_artifact_has_complete_contract() -> None:
    audit = get_player_archetype_slice0_audit()

    assert audit["contract_version"] == CONTRACT_VERSION
    assert audit["status"] == "ready"
    assert [row["year"] for row in audit["year_coverage"]] == list(range(2021, 2027))
    assert all(row["role_integrity"]["duplicate_player_role_keys"] == 0 for row in audit["year_coverage"])
    assert all({item["role"] for item in row["pitcher_roles"]} == {"SP", "RP"} for row in audit["year_coverage"])
    assert audit["prior_work"]["identity_decision"] == "retire_as_player_identity_keep_as_prior_work"
    assert audit["prior_work"]["duplicate_appearance_keys"] == 0
    assert audit["slice1_decision"]["proceed"] is True
    report = archetype_slice0_report_path().read_text(encoding="utf-8")
    assert "## 年度與玩家覆蓋" in report
    assert "2021" in report and "2026" in report


def test_slice0_contract_separates_denominators_and_time_availability() -> None:
    audit = get_player_archetype_slice0_audit()
    pitcher_contracts = audit["feature_contracts"]["pitcher"]
    batter_contracts = audit["feature_contracts"]["batter"]

    assert all(item["denominator"] for item in pitcher_contracts + batter_contracts)
    assert all(item["availability"] for item in pitcher_contracts + batter_contracts)
    assert any(item["slice1_decision"] == "ready_2023_2026_only" for item in pitcher_contracts)
    assert any(item["slice1_decision"] == "ready_2024_2026_2023_partial" for item in batter_contracts)
