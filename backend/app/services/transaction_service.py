from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any
from urllib.parse import urlencode

from app.api.schemas.common import ResponseMeta
from app.api.schemas.teams import TeamTransactionRow, TeamTransactionsResponse
from app.core.config import settings
from app.services.video_service import fetch_json


_CACHE_TTL_SECONDS = 1800
_memory_cache: dict[tuple[int, int, str], tuple[float, dict[str, Any]]] = {}
_cache_lock = Lock()


def get_team_transactions(
    year: int,
    team_code: str,
    mlb_team_id: int,
    days: int = 60,
    limit: int = 40,
    data_dir: Path | None = None,
    force_refresh: bool = False,
) -> TeamTransactionsResponse:
    base_dir = Path(data_dir or settings.data_dir)
    period_end = min(date.today(), date(year, 12, 31))
    period_start = max(date(year, 1, 1), period_end - timedelta(days=days - 1))
    cache_key = (year, days, str(base_dir.resolve()))

    payload: dict[str, Any] | None = None
    warning: str | None = None
    if not force_refresh:
        with _cache_lock:
            cached = _memory_cache.get(cache_key)
            if cached and monotonic() - cached[0] < _CACHE_TTL_SECONDS:
                payload = cached[1]

    cache_path = base_dir / f"MLB{year}" / f"mlb_{year}_transactions.json"
    if payload is None and not force_refresh:
        payload = _read_disk_cache(cache_path, period_start, period_end)

    if payload is None:
        query = urlencode({
            "startDate": period_start.strftime("%m/%d/%Y"),
            "endDate": period_end.strftime("%m/%d/%Y"),
            "sportId": 1,
        })
        try:
            payload = fetch_json(f"https://statsapi.mlb.com/api/v1/transactions?{query}", timeout=30)
            payload["petehubFetchedAt"] = datetime.now(timezone.utc).isoformat()
            payload["petehubPeriodStart"] = period_start.isoformat()
            payload["petehubPeriodEnd"] = period_end.isoformat()
            _write_disk_cache(cache_path, payload)
        except Exception as exc:
            payload = _read_disk_cache(cache_path, period_start, period_end, allow_stale=True) or {"transactions": []}
            warning = f"Live transaction refresh failed; using available cache: {exc}"

    with _cache_lock:
        _memory_cache[cache_key] = (monotonic(), payload)

    rows = [
        _to_transaction_row(item, mlb_team_id)
        for item in payload.get("transactions", []) or []
        if _belongs_to_team(item, mlb_team_id)
    ]
    rows.sort(key=lambda row: (row.date, row.transaction_id), reverse=True)
    warnings = [warning] if warning else []
    return TeamTransactionsResponse(
        meta=ResponseMeta(year=year, warnings=warnings),
        team_id=team_code,
        fetched_at=payload.get("petehubFetchedAt"),
        period_start=payload.get("petehubPeriodStart", period_start.isoformat()),
        period_end=payload.get("petehubPeriodEnd", period_end.isoformat()),
        transactions=rows[:limit],
    )


def _read_disk_cache(
    path: Path,
    period_start: date,
    period_end: date,
    allow_stale: bool = False,
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        same_period = (
            payload.get("petehubPeriodStart") == period_start.isoformat()
            and payload.get("petehubPeriodEnd") == period_end.isoformat()
        )
        age_seconds = datetime.now().timestamp() - path.stat().st_mtime
        if same_period and (allow_stale or age_seconds < _CACHE_TTL_SECONDS):
            return payload
    except (OSError, ValueError, TypeError):
        return None
    return None


def _write_disk_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def _belongs_to_team(item: dict[str, Any], team_id: int) -> bool:
    return any(
        int((item.get(key) or {}).get("id") or 0) == team_id
        for key in ("fromTeam", "toTeam")
    )


def _to_transaction_row(item: dict[str, Any], team_id: int) -> TeamTransactionRow:
    person = item.get("person") or {}
    from_team = item.get("fromTeam") or {}
    to_team = item.get("toTeam") or {}
    description = str(item.get("description") or item.get("typeDesc") or "Roster transaction")
    return TeamTransactionRow(
        transaction_id=int(item.get("id") or 0),
        date=str(item.get("date") or item.get("effectiveDate") or ""),
        effective_date=str(item.get("effectiveDate")) if item.get("effectiveDate") else None,
        player_id=int(person["id"]) if person.get("id") else None,
        player_name=str(person.get("fullName") or "Unknown player"),
        from_team=str(from_team.get("name")) if from_team.get("name") else None,
        to_team=str(to_team.get("name")) if to_team.get("name") else None,
        type_code=str(item.get("typeCode")) if item.get("typeCode") else None,
        type_description=str(item.get("typeDesc") or "Roster move"),
        category=_transaction_category(description, from_team.get("id"), to_team.get("id"), team_id),
        description=description,
    )


def _transaction_category(description: str, from_team_id: Any, to_team_id: Any, team_id: int) -> str:
    text = description.casefold()
    if "injured list" in text:
        return "Activated" if "activated" in text or "reinstated" in text else "Injury"
    if "recalled" in text or "selected the contract" in text or "contract of" in text and "selected" in text:
        return "Called up"
    if "optioned" in text or "reassigned" in text:
        return "Optioned"
    if "designated for assignment" in text:
        return "DFA"
    if "released" in text or "free agent" in text:
        return "Departed"
    if "claimed" in text or "acquired" in text or "traded" in text:
        return "Acquired" if int(to_team_id or 0) == team_id else "Departed"
    if int(from_team_id or 0) == team_id and int(to_team_id or 0) != team_id:
        return "Departed"
    return "Roster move"
