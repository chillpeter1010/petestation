from fastapi import APIRouter

from app.api.schemas.common import AnalysisResponse
from app.services.derived_service import get_derived_model_scores, get_derived_outing_report, get_derived_status

router = APIRouter()


@router.get("/status")
def read_derived_status(year: int = 2026) -> dict[str, object]:
    return get_derived_status(year=year)


@router.get("/outing-report", response_model=AnalysisResponse)
def read_derived_outing_report(year: int, pitcher_id: int, game_pk: int) -> AnalysisResponse:
    return get_derived_outing_report(year=year, pitcher_id=pitcher_id, game_pk=game_pk)


@router.get("/model-scores", response_model=AnalysisResponse)
def read_derived_model_scores(year: int = 2026, scope: str = "pitcher") -> AnalysisResponse:
    return get_derived_model_scores(year=year, scope=scope)
