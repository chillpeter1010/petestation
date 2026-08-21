from fastapi import APIRouter, HTTPException

from app.api.schemas.common import AnalysisResponse
from app.api.schemas.location import LocationComparisonResponse, LocationHeatmapResponse, LocationLeaderboardResponse, LocationPitcherResponse
from app.services.location_export_service import get_location_comparison, get_location_leaderboard, get_location_pitcher
from app.services.location_heatmap_service import build_location_heatmap
from app.services.location_service import get_location_features, get_location_score

router = APIRouter()


@router.get("/leaderboard", response_model=LocationLeaderboardResponse)
def read_location_leaderboard(year: int = 2026, minimum_pitches: int = 300) -> LocationLeaderboardResponse:
    try:
        return get_location_leaderboard(year=year, minimum_pitches=max(0, minimum_pitches))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/pitcher", response_model=LocationPitcherResponse)
def read_location_pitcher(year: int, pitcher_id: int, game_pk: int | None = None) -> LocationPitcherResponse:
    try:
        return get_location_pitcher(year=year, pitcher_id=pitcher_id, game_pk=game_pk)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/comparison", response_model=LocationComparisonResponse)
def read_location_comparison(year: int = 2026, minimum_pitches: int = 100) -> LocationComparisonResponse:
    try:
        return get_location_comparison(year=year, minimum_pitches=max(0, minimum_pitches))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/heatmap", response_model=LocationHeatmapResponse)
def read_location_heatmap(
    sample: str = "training",
    pitcher_hand: str = "R",
    batter_side: str = "R",
    pitch_type: str = "4-Seam Fastball",
    count: str = "All",
) -> LocationHeatmapResponse:
    try:
        return build_location_heatmap(
            sample=sample,
            pitcher_hand=pitcher_hand,
            batter_side=batter_side,
            pitch_type=pitch_type,
            count=count,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/features", response_model=AnalysisResponse)
def read_location_features(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> AnalysisResponse:
    return get_location_features(
        year=year,
        pitcher_id=pitcher_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/score", response_model=AnalysisResponse)
def read_location_score(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> AnalysisResponse:
    return get_location_score(
        year=year,
        pitcher_id=pitcher_id,
        start_date=start_date,
        end_date=end_date,
    )
