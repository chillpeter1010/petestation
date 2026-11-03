from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from app.api.schemas.common import ResponseMeta
from app.api.schemas.teams import ActiveRosterPlayer, ActiveRosterResponse
from app.core.config import settings
from app.core.mlb_teams import MLB_TEAM_CODE_TO_ID
from app.services.video_service import fetch_json


ACTIVE_ROSTER_CONTRACT_VERSION = "official_active_roster_v1"
ACTIVE_ROSTER_STALE_AFTER_SECONDS = 30 * 60


def get_team_active_roster(
    year: int,
    team_code: str,
    *,
    data_dir: Path | None = None,
    force_refresh: bool = False,
    fetcher: Callable[..., dict[str, Any]] = fetch_json,
    now: datetime | None = None,
) -> ActiveRosterResponse:
    code = team_code.strip().upper()
    if code not in MLB_TEAM_CODE_TO_ID:
        raise ValueError(f"Unsupported MLB team: {team_code}")
    current_time = _utc(now or datetime.now(timezone.utc))
    team_id = MLB_TEAM_CODE_TO_ID[code]
    source_url = _source_url(team_id, year)
    cache_path = _cache_path(Path(data_dir or settings.data_dir), year, code)
    cached = _read_cache(cache_path, year, code, team_id)
    cache_age = _cache_age_seconds(cached, current_time)

    if not force_refresh and cached is not None and cache_age is not None and cache_age <= ACTIVE_ROSTER_STALE_AFTER_SECONDS:
        return _response(cached, freshness="fresh", cache_age_seconds=cache_age)

    try:
        payload = fetcher(source_url, timeout=12)
        normalized = _normalize_payload(payload, year, code, team_id, source_url, current_time)
        _write_cache(cache_path, normalized)
        return _response(normalized, freshness="fresh", cache_age_seconds=0)
    except Exception as exc:
        warning = f"Official active-roster refresh failed: {exc}"
        if cached is not None:
            return _response(cached, freshness="stale", cache_age_seconds=cache_age, warning=warning)
        return ActiveRosterResponse(
            meta=ResponseMeta(year=year, warnings=[warning]),
            team_id=team_id,
            team_code=code,
            season=year,
            source_url=source_url,
            freshness="unavailable",
            stale_after_seconds=ACTIVE_ROSTER_STALE_AFTER_SECONDS,
            players=[],
        )


def _source_url(team_id: int, year: int) -> str:
    query = urlencode({"rosterType": "active", "season": int(year), "hydrate": "person"})
    return f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?{query}"


def _cache_path(data_dir: Path, year: int, team_code: str) -> Path:
    return data_dir / f"MLB{int(year)}" / "official_active_rosters" / f"{team_code}.json"


def _normalize_payload(
    payload: dict[str, Any],
    year: int,
    team_code: str,
    team_id: int,
    source_url: str,
    retrieved_at: datetime,
) -> dict[str, Any]:
    roster = payload.get("roster")
    if not isinstance(roster, list):
        raise ValueError("MLB StatsAPI response does not contain a roster list.")
    players: list[dict[str, Any]] = []
    for item in roster:
        person = item.get("person") or {}
        player_id = person.get("id")
        if player_id is None:
            continue
        position = item.get("position") or {}
        status = item.get("status") or {}
        players.append(ActiveRosterPlayer(
            player_id=int(player_id),
            name=str(person.get("fullName") or "Unknown player"),
            jersey_number=str(item["jerseyNumber"]) if item.get("jerseyNumber") is not None else None,
            position_code=str(position["code"]) if position.get("code") is not None else None,
            position_name=str(position["name"]) if position.get("name") is not None else None,
            position_type=str(position["type"]) if position.get("type") is not None else None,
            status_code=str(status["code"]) if status.get("code") is not None else None,
            status_description=str(status["description"]) if status.get("description") is not None else None,
        ).model_dump())
    return {
        "contract_version": ACTIVE_ROSTER_CONTRACT_VERSION,
        "team_id": team_id,
        "team_code": team_code,
        "season": int(year),
        "roster_type": "active",
        "source": "MLB StatsAPI",
        "source_url": source_url,
        "retrieved_at": retrieved_at.isoformat(),
        "source_as_of": None,
        "stale_after_seconds": ACTIVE_ROSTER_STALE_AFTER_SECONDS,
        "players": players,
    }


def _read_cache(path: Path, year: int, team_code: str, team_id: int) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("contract_version") == ACTIVE_ROSTER_CONTRACT_VERSION
            and payload.get("season") == int(year)
            and payload.get("team_code") == team_code
            and payload.get("team_id") == team_id
            and payload.get("roster_type") == "active"
            and isinstance(payload.get("players"), list)
        ):
            return payload
    except (OSError, ValueError, TypeError):
        pass
    return None


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _cache_age_seconds(payload: dict[str, Any] | None, now: datetime) -> int | None:
    if payload is None or not payload.get("retrieved_at"):
        return None
    try:
        retrieved_at = _utc(datetime.fromisoformat(str(payload["retrieved_at"])))
    except ValueError:
        return None
    return max(0, int((now - retrieved_at).total_seconds()))


def _response(
    payload: dict[str, Any],
    *,
    freshness: str,
    cache_age_seconds: int | None,
    warning: str | None = None,
) -> ActiveRosterResponse:
    warnings = [warning] if warning else []
    return ActiveRosterResponse(
        meta=ResponseMeta(year=int(payload["season"]), data_updated_at=payload.get("retrieved_at"), warnings=warnings),
        **payload,
        freshness=freshness,
        cache_age_seconds=cache_age_seconds,
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
