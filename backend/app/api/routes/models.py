from fastapi import APIRouter

from app.api.schemas.common import AnalysisResponse, ResponseMeta

router = APIRouter()


@router.get("/spin-breakdown", response_model=AnalysisResponse)
def get_spin_breakdown(year: int = 2026) -> AnalysisResponse:
    # TODO: extract from pages/28_pitch_spin_breakdown.py.
    return AnalysisResponse(meta=ResponseMeta(year=year))
