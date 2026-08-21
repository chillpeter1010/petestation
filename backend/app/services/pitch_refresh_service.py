from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import duckdb

from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.video_service import fetch_json


def fetch_completed_regular_season_games(year: int, through: date | None = None) -> list[dict[str, object]]:
    end_date = min(through or date.today(), date(int(year), 11, 30))
    query = urlencode(
        {
            "sportId": 1,
            "gameTypes": "R",
            "startDate": f"03/01/{int(year)}",
            "endDate": end_date.strftime("%m/%d/%Y"),
        }
    )
    payload = fetch_json(f"https://statsapi.mlb.com/api/v1/schedule?{query}", timeout=45)
    games: list[dict[str, object]] = []
    for date_block in payload.get("dates", []) or []:
        for game in date_block.get("games", []) or []:
            status = game.get("status") or {}
            if status.get("detailedState") not in {"Final", "Completed Early", "Game Over"}:
                continue
            game_pk = game.get("gamePk")
            game_date = game.get("officialDate") or date_block.get("date")
            if game_pk and game_date and str(game_date)[:10] <= end_date.isoformat():
                games.append({"game_pk": int(game_pk), "game_date": str(game_date)[:10]})
    return games


def audit_pitch_coverage(year: int, data_dir: Path, through: date | None = None) -> dict[str, object]:
    official_games = fetch_completed_regular_season_games(year=int(year), through=through)
    official_by_pk = {int(game["game_pk"]): str(game["game_date"]) for game in official_games}
    local_game_pks: set[int] = set()
    latest_local_date: str | None = None
    db_path = get_season_duckdb_path(int(year), data_dir)
    if db_path.exists():
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            source_table = resolve_pitch_table(tables)
            if source_table:
                rows = conn.execute(
                    f"""
                    SELECT DISTINCT CAST(game_pk AS BIGINT), CAST(game_date AS DATE)
                    FROM {source_table}
                    WHERE game_type = 'R' AND game_pk IS NOT NULL
                    """
                ).fetchall()
                local_game_pks = {int(row[0]) for row in rows}
                dates = [str(row[1])[:10] for row in rows if row[1] is not None]
                latest_local_date = max(dates) if dates else None

    missing_game_pks = sorted(set(official_by_pk) - local_game_pks)
    missing_by_date: dict[str, list[int]] = defaultdict(list)
    for game_pk in missing_game_pks:
        missing_by_date[official_by_pk[game_pk]].append(game_pk)
    latest_official_date = max(official_by_pk.values()) if official_by_pk else None
    return {
        "year": int(year),
        "official_completed_games": len(official_by_pk),
        "local_games": len(local_game_pks),
        "latest_official_date": latest_official_date,
        "latest_local_date": latest_local_date,
        "missing_games": len(missing_game_pks),
        "missing_game_pks": missing_game_pks,
        "missing_dates": sorted(missing_by_date),
        "missing_by_date": dict(sorted(missing_by_date.items())),
        "complete": not missing_game_pks,
    }


def summarize_missing_coverage(audit: dict[str, Any]) -> str:
    dates = list(audit.get("missing_dates") or [])
    preview = ", ".join(dates[:8])
    if len(dates) > 8:
        preview += f" and {len(dates) - 8} more date(s)"
    return f"{int(audit.get('missing_games') or 0)} completed MLB game(s) missing from pitch data: {preview}"


def classify_source_pending(
    audit: dict[str, Any],
    *,
    today: date | None = None,
    grace_days: int = 2,
) -> dict[str, object]:
    """Separate normal recent Statcast publication lag from older coverage gaps."""

    reference_day = today or date.today()
    cutoff = reference_day - timedelta(days=max(0, int(grace_days)))
    recent_dates: list[str] = []
    stale_dates: list[str] = []
    for value in audit.get("missing_dates") or []:
        try:
            missing_day = date.fromisoformat(str(value))
        except ValueError:
            stale_dates.append(str(value))
            continue
        (recent_dates if missing_day >= cutoff else stale_dates).append(missing_day.isoformat())
    return {
        "source_pending": bool(recent_dates) and not stale_dates,
        "pending_dates": recent_dates,
        "stale_dates": stale_dates,
        "grace_days": max(0, int(grace_days)),
    }
