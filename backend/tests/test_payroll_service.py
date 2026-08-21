import json
from datetime import datetime, timedelta, timezone

from app.services.payroll import TEAM_PAYROLL_SLUGS, get_team_payroll, payroll_source_url
from app.services.team_dashboard_service import TEAM_CONFIG


def test_get_team_payroll_reads_weekly_snapshot(tmp_path):
    updated_at = datetime.now(timezone.utc) - timedelta(days=2)
    payroll_dir = tmp_path / "MLB2026" / "payroll"
    payroll_dir.mkdir(parents=True)
    (payroll_dir / "sd.json").write_text(
        json.dumps({
            "team_name": "San Diego Padres",
            "source": "Fixture",
            "source_url": "https://example.com/payroll",
            "source_updated_at": updated_at.isoformat(),
            "estimated_payroll": "$209M",
            "prior_year_payroll": "$211M",
            "guaranteed_players": [{
                "name": "Example Player",
                "age": 29.5,
                "service_time": "5.000",
                "contract": "2 yr, $20M",
                "aav": "$10M",
                "salaries": {"2026": "$10M", "2027": "$10M"},
            }],
        }),
        encoding="utf-8",
    )

    result = get_team_payroll(2026, "SD", data_dir=tmp_path)

    assert result.team_name == "San Diego Padres"
    assert result.estimated_payroll == "$209M"
    assert result.refresh_due is False
    assert result.next_refresh_due is not None
    assert result.guaranteed_players[0].name == "Example Player"


def test_get_team_payroll_returns_staged_response_when_snapshot_missing(tmp_path):
    result = get_team_payroll(2026, "AZ", data_dir=tmp_path)

    assert result.team_id == "AZ"
    assert result.guaranteed_players == []
    assert result.meta.warnings


def test_payroll_slug_registry_covers_all_team_pages():
    assert set(TEAM_PAYROLL_SLUGS) == set(TEAM_CONFIG)
    assert payroll_source_url("ATH") == "https://www.fangraphs.com/roster-resource/payroll/athletics"
