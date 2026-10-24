from typing import Literal

from fastapi import APIRouter, Query

from app.api.schemas.common import AnalysisResponse
from app.services.derived_service import get_derived_model_scores, get_derived_outing_report, get_derived_status
from app.services.player_archetype_slice3_service import get_player_archetype_slice3_view

router = APIRouter()


@router.get("/player-archetypes/slice3")
def read_player_archetype_slice3(
    year: int = Query(default=2026, ge=2021, le=2026),
    population: Literal["pitcher", "batter"] = "pitcher",
    role: str | None = None,
) -> dict[str, object]:
    return get_player_archetype_slice3_view(year=year, population=population, role=role)


@router.get("/status")
def read_derived_status(year: int = 2026) -> dict[str, object]:
    return get_derived_status(year=year)


@router.get("/outing-report", response_model=AnalysisResponse)
def read_derived_outing_report(year: int, pitcher_id: int, game_pk: int) -> AnalysisResponse:
    return get_derived_outing_report(year=year, pitcher_id=pitcher_id, game_pk=game_pk)


@router.get("/model-scores", response_model=AnalysisResponse)
def read_derived_model_scores(year: int = 2026, scope: str = "pitcher") -> AnalysisResponse:
    return get_derived_model_scores(year=year, scope=scope)
