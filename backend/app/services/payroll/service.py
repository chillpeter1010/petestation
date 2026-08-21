from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.api.schemas.common import ResponseMeta
from app.api.schemas.teams import TeamPayrollLineItem, TeamPayrollPlayer, TeamPayrollResponse
from app.core.config import settings
from app.services.payroll.importer import derive_salary_statuses


WEEKLY_REFRESH_DAYS = 7


def get_team_payroll(year: int, team_code: str, data_dir: Path | None = None) -> TeamPayrollResponse:
    path = Path(data_dir or settings.data_dir) / f"MLB{year}" / "payroll" / f"{team_code.casefold()}.json"
    if not path.exists():
        return TeamPayrollResponse(
            meta=ResponseMeta(year=year, warnings=["Payroll snapshot has not been imported for this team."]),
            team_id=team_code,
            team_name=team_code,
            source="Manual snapshot",
            season=year,
            refresh_mode="manual_weekly_snapshot",
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    source_updated = _parse_datetime(payload.get("source_updated_at"))
    next_refresh = source_updated + timedelta(days=WEEKLY_REFRESH_DAYS) if source_updated else None
    return TeamPayrollResponse(
        meta=ResponseMeta(year=year),
        team_id=team_code,
        team_name=str(payload.get("team_name") or team_code),
        source=str(payload.get("source") or "Manual snapshot"),
        source_url=payload.get("source_url"),
        season=year,
        estimated_payroll=payload.get("estimated_payroll"),
        prior_year_payroll=payload.get("prior_year_payroll"),
        source_updated_at=payload.get("source_updated_at"),
        next_refresh_due=next_refresh.isoformat() if next_refresh else None,
        refresh_due=bool(next_refresh and datetime.now(timezone.utc) >= next_refresh),
        refresh_mode=str(payload.get("refresh_mode") or "manual_weekly_snapshot"),
        guaranteed_players=[_payroll_player(row) for row in payload.get("guaranteed_players", [])],
        arbitration_players=[_payroll_player(row) for row in payload.get("arbitration_players", [])],
        pre_arbitration_players=[_payroll_player(row) for row in payload.get("pre_arbitration_players", [])],
        pre_arbitration_other_estimate=payload.get("pre_arbitration_other_estimate"),
        off_roster_players=[_payroll_player(row) for row in payload.get("off_roster_players", [])],
        incentives=[TeamPayrollLineItem(**row) for row in payload.get("incentives", [])],
        other_payments=[TeamPayrollLineItem(**row) for row in payload.get("other_payments", [])],
        estimated_payroll_by_year=payload.get("estimated_payroll_by_year", {}),
        luxury_tax_items=[TeamPayrollLineItem(**row) for row in payload.get("luxury_tax_items", [])],
        estimated_luxury_tax_payroll=payload.get("estimated_luxury_tax_payroll", {}),
    )


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _payroll_player(row: dict[str, object]) -> TeamPayrollPlayer:
    payload = dict(row)
    salaries = payload.get("salaries") or {}
    payload["salary_statuses"] = derive_salary_statuses(
        str(payload.get("contract") or ""),
        {str(year): str(value) for year, value in dict(salaries).items()},
    )
    return TeamPayrollPlayer(**payload)
