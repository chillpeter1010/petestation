from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from typing import Literal
from app.services.pitch_matchup_service import get_pitch_matchup

from app.api.schemas.common import AnalysisResponse
from app.services.game_pitcher_analysis_service import get_game_pitch_replay, get_game_pitch_shape, get_game_pitcher_tags
from app.services.games_service import get_game_pitching, list_games
from app.services.personal_service import get_personal_movement, get_personal_sequence

router = APIRouter()


@router.get("/matchup-context")
def read_matchup_context(year: int = Query(2026, ge=2021, le=2100), pitcher_id: int = Query(..., gt=0), batter_id: int = Query(..., gt=0), batter_side: Literal["L", "R", "unknown"] = "unknown", pitcher_hand: Literal["L", "R", "unknown"] = "unknown", balls: int = Query(..., ge=0, le=3), strikes: int = Query(..., ge=0, le=2)) -> dict[str, Any]:
    return get_pitch_matchup(year, pitcher_id, batter_id, batter_side, pitcher_hand, balls, strikes)


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


@router.get("/{game_pk}/pitchers/{pitcher_id}/location", response_model=AnalysisResponse)
def read_game_pitcher_location(
    game_pk: int,
    pitcher_id: int,
    year: int = 2026,
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    in_play_result: str | None = None,
    pa_result: str | None = None,
    catcher: str | None = None,
) -> AnalysisResponse:
    return get_personal_movement(
        year=year,
        pitcher_id=pitcher_id,
        game_pk=game_pk,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        in_play_result=in_play_result,
        pa_result=pa_result,
        catcher=catcher,
        include_pitch_stuff=True,
        game_view=True,
    )


@router.get("/{game_pk}/pitchers/{pitcher_id}/sequence", response_model=AnalysisResponse)
def read_game_pitcher_sequence(
    game_pk: int,
    pitcher_id: int,
    year: int = 2026,
    current_pitch: str = "All",
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    catcher: str | None = None,
    condition_count: str | None = None,
    condition_pitch: str | None = None,
    detail_count: str | None = "0-0",
    followup_pitch: str | None = None,
) -> AnalysisResponse:
    return get_personal_sequence(
        year=year,
        pitcher_id=pitcher_id,
        game_pk=game_pk,
        current_pitch=current_pitch,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        catcher=catcher,
        condition_count=condition_count,
        condition_pitch=condition_pitch,
        detail_count=detail_count,
        followup_pitch=followup_pitch,
    )


@router.get("/{game_pk}/pitchers/{pitcher_id}/shape", response_model=AnalysisResponse)
def read_game_pitch_shape(
    game_pk: int,
    pitcher_id: int,
    year: int = 2026,
) -> AnalysisResponse:
    return get_game_pitch_shape(year=year, game_pk=game_pk, pitcher_id=pitcher_id)


@router.get("/{game_pk}/pitchers/{pitcher_id}/replay", response_model=AnalysisResponse)
def read_game_pitch_replay(
    game_pk: int,
    pitcher_id: int,
    year: int = 2026,
) -> AnalysisResponse:
    return get_game_pitch_replay(year=year, game_pk=game_pk, pitcher_id=pitcher_id)


@router.get("/{game_pk}/pitchers/{pitcher_id}/tags")
def read_game_pitcher_tags(
    game_pk: int,
    pitcher_id: int,
    year: int = 2026,
    role: str = "RP",
) -> dict[str, Any]:
    return get_game_pitcher_tags(
        year=year,
        game_pk=game_pk,
        pitcher_id=pitcher_id,
        role=role,
    )
