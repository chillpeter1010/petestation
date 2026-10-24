from __future__ import annotations

import pytest

from app.services.catcher_descriptive_audit_service import (
    CONTRACT_VERSION,
    baseball_ip_to_outs,
    get_catcher_descriptive_slice0_audit,
)


def test_baseball_ip_to_outs_uses_baseball_not_decimal_arithmetic() -> None:
    assert baseball_ip_to_outs("6.1") == 19
    assert baseball_ip_to_outs("6.2") == 20
    assert baseball_ip_to_outs("7") == 21
    with pytest.raises(ValueError):
        baseball_ip_to_outs("324.3")


def test_real_slice0_audit_freezes_ledger_and_source_gates() -> None:
    audit = get_catcher_descriptive_slice0_audit()

    assert audit["contract_version"] == CONTRACT_VERSION
    assert [row["year"] for row in audit["local_coverage"]] == list(range(2021, 2027))
    assert all(row["catcher_terminal_rows"] == row["terminal_rows"] for row in audit["local_coverage"])
    assert all(row["duplicate_pitch_keys"] == 0 for row in audit["local_coverage"])
    assert audit["legacy_workbook"]["formula_cells"] == 0
    assert len(audit["legacy_workbook"]["invalid_display_innings_rows"]) == 2
    assert "earned_runs" in audit["slice1_contract"]["required_raw_fields"]
    assert audit["scope"]["leaderboards_allowed"] is False
    assert any("DRS" in item for item in audit["missing_sources"])
    assert any("park-factor" in item for item in audit["missing_sources"])
