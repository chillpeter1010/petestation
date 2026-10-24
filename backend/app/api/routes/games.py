from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services.games_service import get_game_pitching, list_games

router = APIRouter()


@router.get("")
def read_games(
    year: int = 2026,
    date: str | None = None,
    team: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    return list_games(year=year, date=date, team=team, limit=limit)


@router.get("/{game_pk}")
def read_game_pitching(game_pk: int, year: int = 2026) -> dict[str, Any]:
    return get_game_pitching(year=year, game_pk=game_pk)
