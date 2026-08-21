from fastapi import APIRouter

from app.api.schemas.common import AnalysisResponse
from app.services.rotation_service import (
    get_bullpen_role_response,
    get_reliever_fatigue_lab_response,
    get_starter_fatigue_lab_response,
    get_starter_rotation_response,
)

router = APIRouter()


@router.get("/starter", response_model=AnalysisResponse)
def read_starter_rotation(
    year: int = 2025,
    team: str | None = None,
    min_gs: int = 3,
    min_ip_per_gs: float = 3.0,
    player_id: int | None = None,
    fatigue_game_pk: int | None = None,
) -> AnalysisResponse:
    return get_starter_rotation_response(
        year=year,
        team=team,
        min_gs=min_gs,
        min_ip_per_gs=min_ip_per_gs,
        player_id=player_id,
        fatigue_game_pk=fatigue_game_pk,
    )


@router.get("/starter/fatigue-lab", response_model=AnalysisResponse)
def read_starter_fatigue_lab(
    year: int = 2025,
    team: str | None = None,
    min_gs: int = 3,
    min_ip_per_gs: float = 3.0,
    player_id: int | None = None,
    game_pk: int | None = None,
) -> AnalysisResponse:
    return get_starter_fatigue_lab_response(
        year=year,
        team=team,
        min_gs=min_gs,
        min_ip_per_gs=min_ip_per_gs,
        player_id=player_id,
        game_pk=game_pk,
    )


@router.get("/reliever", response_model=AnalysisResponse)
def read_bullpen_role(
    year: int = 2025,
    team: str | None = None,
    min_games: int = 5,
    player_id: int | None = None,
    availability_date: str | None = None,
) -> AnalysisResponse:
    return get_bullpen_role_response(
        year=year,
        team=team,
        min_games=min_games,
        player_id=player_id,
        availability_date=availability_date,
    )


@router.get("/reliever/fatigue-lab", response_model=AnalysisResponse)
def read_reliever_fatigue_lab(
    year: int = 2025,
    team: str | None = None,
    min_games: int = 5,
    player_id: int | None = None,
    availability_date: str | None = None,
) -> AnalysisResponse:
    return get_reliever_fatigue_lab_response(
        year=year,
        team=team,
        min_games=min_games,
        player_id=player_id,
        availability_date=availability_date,
    )
