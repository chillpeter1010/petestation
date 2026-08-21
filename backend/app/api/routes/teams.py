from fastapi import APIRouter, HTTPException, Query

from app.api.schemas.common import AnalysisResponse
from app.api.schemas.teams import TeamDashboardResponse, TeamPayrollResponse, TeamPitchVideoResponse, TeamTransactionsResponse
from app.services.team_dashboard_service import (
    MLB_TEAM_IDS,
    TEAM_CONFIG,
    get_team_dashboard,
    get_team_starter_pitch_videos,
    get_team_starter_workload,
)
from app.services.video_service import fetch_sporty_video_metadata
from app.services.transaction_service import get_team_transactions
from app.services.payroll import get_team_payroll

router = APIRouter()


@router.get("/media/video-direct")
def read_team_direct_video(play_id: str) -> dict[str, object]:
    try:
        return fetch_sporty_video_metadata(play_id, timeout=12)
    except Exception:
        return {
            "play_id": play_id,
            "video_url": f"https://baseballsavant.mlb.com/sporty-videos?playId={play_id}",
            "direct_video_url": None,
            "title": None,
        }


@router.get("/{team_id}/dashboard", response_model=TeamDashboardResponse)
def read_team_dashboard(team_id: str, year: int = Query(2026)) -> TeamDashboardResponse:
    try:
        return get_team_dashboard(year=year, team_id=team_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{team_id}/transactions", response_model=TeamTransactionsResponse)
def read_team_transactions(
    team_id: str,
    year: int = Query(2026),
    days: int = Query(60, ge=7, le=180),
    limit: int = Query(40, ge=1, le=100),
    refresh: bool = Query(False),
) -> TeamTransactionsResponse:
    team_code = team_id.strip().upper()
    if team_code not in MLB_TEAM_IDS:
        raise HTTPException(status_code=404, detail=f"Unsupported MLB team: {team_id}")
    return get_team_transactions(
        year,
        team_code,
        MLB_TEAM_IDS[team_code],
        days=days,
        limit=limit,
        force_refresh=refresh,
    )


@router.get("/{team_id}/payroll", response_model=TeamPayrollResponse)
def read_team_payroll(team_id: str, year: int = Query(2026)) -> TeamPayrollResponse:
    team_code = team_id.strip().upper()
    if team_code not in TEAM_CONFIG:
        raise HTTPException(status_code=404, detail=f"Unsupported MLB team: {team_id}")
    return get_team_payroll(year, team_code)


@router.get("/{team_id}/starter-workload", response_model=AnalysisResponse)
def read_team_starter_workload(
    team_id: str,
    year: int = Query(2026),
    pitcher_id: int = Query(...),
    game_pk: int | None = Query(None),
) -> AnalysisResponse:
    try:
        return get_team_starter_workload(
            year=year,
            team_code=team_id.strip().upper(),
            pitcher_id=pitcher_id,
            game_pk=game_pk,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{team_id}/starter-pitch-videos", response_model=TeamPitchVideoResponse)
def read_team_starter_pitch_videos(
    team_id: str,
    year: int = Query(2026),
    pitcher_id: int = Query(...),
    game_pk: int = Query(...),
) -> TeamPitchVideoResponse:
    if team_id.strip().upper() not in TEAM_CONFIG:
        raise HTTPException(status_code=404, detail=f"Unsupported MLB team: {team_id}")
    return get_team_starter_pitch_videos(year=year, pitcher_id=pitcher_id, game_pk=game_pk)
