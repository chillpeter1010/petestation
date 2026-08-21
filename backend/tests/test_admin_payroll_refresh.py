from app.services import admin_service
from app.services.payroll.importer import PayrollSourceBlockedError


def test_payroll_refresh_preserves_snapshots_when_source_is_blocked(tmp_path, monkeypatch):
    payroll_dir = tmp_path / "MLB2026" / "payroll"
    payroll_dir.mkdir(parents=True)
    for team in admin_service.TEAM_PAYROLL_SLUGS:
        (payroll_dir / f"{team.casefold()}.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(admin_service.settings, "data_dir", tmp_path)

    def blocked(*_args, **_kwargs):
        raise PayrollSourceBlockedError("verification required")

    monkeypatch.setattr(admin_service, "_refresh_payroll_team", blocked)

    result = admin_service.run_payroll_refresh(year=2026)

    assert result["source_status"] == "temporarily_blocked"
    assert result["updated_count"] == 0
    assert result["failed_count"] == 0
    assert result["preserved_count"] == 30
