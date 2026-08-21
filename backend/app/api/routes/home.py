from fastapi import APIRouter, Query

from app.api.schemas.home import HomeRecommendationsResponse
from app.services.home_service import get_home_video_recommendations, search_home_videos

router = APIRouter()


@router.get("/recommendations", response_model=HomeRecommendationsResponse)
def read_home_recommendations(year: int = 2026) -> HomeRecommendationsResponse:
    return get_home_video_recommendations(year=year)


@router.get("/videos/search", response_model=HomeRecommendationsResponse)
def read_home_video_search(
    q: str = Query(min_length=2, max_length=120),
    year: int = 2026,
    limit: int = Query(default=12, ge=1, le=24),
) -> HomeRecommendationsResponse:
    return search_home_videos(query=q, year=year, limit=limit)
