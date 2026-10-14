from fastapi import APIRouter, HTTPException

from app.api.schemas.common import AnalysisResponse
from app.api.schemas.stuff import PitchQualityLeaderboardResponse, StuffCalculatorRequest, StuffCalculatorResponse
from app.services.stuff_leaderboard_service import get_stuff_leaderboard
from app.services.stuff_service import calculate_stuff_pitch, get_stuff_features, get_stuff_score

router = APIRouter()


@router.post("/calculator", response_model=StuffCalculatorResponse)
def calculate_stuff(request: StuffCalculatorRequest) -> StuffCalculatorResponse:
    try:
        return calculate_stuff_pitch(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/leaderboard", response_model=PitchQualityLeaderboardResponse)
def read_stuff_leaderboard(
    year: int = 2026,
    role: str = "All",
    team: str = "All",
    minimum_ip: float = 0,
) -> PitchQualityLeaderboardResponse:
    try:
        return PitchQualityLeaderboardResponse(**get_stuff_leaderboard(year, role, team, minimum_ip))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/features", response_model=AnalysisResponse)
def read_stuff_features(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> AnalysisResponse:
    return get_stuff_features(
        year=year,
        pitcher_id=pitcher_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/score", response_model=AnalysisResponse)
def read_stuff_score(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    game_pk: int | None = None,
    model_mode: str = "pete",
) -> AnalysisResponse:
    return get_stuff_score(
        year=year,
        pitcher_id=pitcher_id,
        start_date=start_date,
        end_date=end_date,
        game_pk=game_pk,
        scoring_mode=model_mode,
    )
