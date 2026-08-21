from fastapi import APIRouter, HTTPException

from app.api.schemas.pitching import PitchingOverviewResponse, PitchingPitcherResponse
from app.services.pitching_export_service import get_pitching_overview, get_pitching_pitcher

router = APIRouter()


@router.get("/overview", response_model=PitchingOverviewResponse)
def read_pitching_overview(year: int = 2026, minimum_pitches: int = 0, minimum_innings: float = 0) -> PitchingOverviewResponse:
    try:
        return get_pitching_overview(year, max(0, minimum_pitches), max(0, minimum_innings))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/pitcher", response_model=PitchingPitcherResponse)
def read_pitching_pitcher(year: int, pitcher_id: int) -> PitchingPitcherResponse:
    try:
        return get_pitching_pitcher(year, pitcher_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
