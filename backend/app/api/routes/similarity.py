from fastapi import APIRouter

from app.api.schemas.common import AnalysisResponse, ResponseMeta

router = APIRouter()


@router.get("/search", response_model=AnalysisResponse)
def search_similar_pitchers(year: int = 2026, pitcher_id: int | None = None) -> AnalysisResponse:
    # TODO: extract from pages/27_pitcher_similarity.py.
    return AnalysisResponse(meta=ResponseMeta(year=year))
