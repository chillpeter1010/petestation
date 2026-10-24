from __future__ import annotations

from app.services.catcher_pitch_calling_prework_service import (
    CONTRACT_VERSION,
    catcher_prework_report_path,
    get_catcher_pitch_calling_prework,
)


def test_real_catcher_prework_artifact_has_complete_coverage_contract() -> None:
    audit = get_catcher_pitch_calling_prework()

    assert audit["contract_version"] == CONTRACT_VERSION
    assert audit["status"] == "ready"
    assert [row["year"] for row in audit["coverage"]] == list(range(2021, 2027))
    assert all(row["catcher_id_coverage_pct"] >= 99 for row in audit["coverage"])
    assert audit["decision"] == "proceed_with_hierarchical_features_not_sparse_cross_tabs"
    assert audit["slice4_contract"]["minimum_rules"]["all_rolling_features_use_strictly_earlier_pitches"] is True


def test_catcher_prework_preserves_sparse_state_and_causal_limits() -> None:
    audit = get_catcher_pitch_calling_prework()
    support = audit["chronological_support"]

    assert support["pitcher_count_stand_20"] > support["pair_context_20"]
    assert audit["slice4_contract"]["minimum_rules"]["unseen_or_low_support_states_back_off"] is True
    assert "not who selected the pitch" in audit["interpretation_policy"]["reason"]
    report = catcher_prework_report_path().read_text(encoding="utf-8")
    assert "Coverage and sparsity" in report
    assert "Strictly prior support" in report
