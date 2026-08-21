from fastapi import APIRouter

from app.api.schemas.common import AnalysisResponse, ResponseMeta

router = APIRouter()


@router.get("/leaderboard", response_model=AnalysisResponse)
def get_discipline_leaderboard(year: int = 2026) -> AnalysisResponse:
    # TODO: extract from pages/23_starter_discipline.py.
    return AnalysisResponse(meta=ResponseMeta(year=year))
