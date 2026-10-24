from fastapi import APIRouter, HTTPException, Query

from app.api.schemas.common import AnalysisResponse, OptionItem
from app.services.catcher_service import get_catcher_options, get_catcher_pitcher_options, get_catcher_sequence
from app.services.catcher_descriptive_metrics_service import (
    get_catcher_descriptive_detail,
    get_catcher_descriptive_leaderboard,
    get_catcher_descriptive_paired_duo_leaderboard,
)
from app.services.catcher_descriptive_strategy_service import get_catcher_descriptive_strategy_bridge

router = APIRouter()


@router.get("/descriptive/leaderboard")
def read_catcher_descriptive_leaderboard(
    year: int = Query(default=2021, ge=2021, le=2026),
    minimum_outs: int = Query(default=0, ge=0),
) -> dict:
    try:
        return get_catcher_descriptive_leaderboard(year=year, minimum_outs=minimum_outs)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/descriptive/pairs/leaderboard")
def read_catcher_descriptive_paired_duo_leaderboard(
    year: int = Query(default=2021, ge=2021, le=2026),
    minimum_outs: int = Query(default=120, ge=0),
) -> dict:
    try:
        return get_catcher_descriptive_paired_duo_leaderboard(year=year, minimum_outs=minimum_outs)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/descriptive/{catcher_id}")
def read_catcher_descriptive_detail(
    catcher_id: int,
    year: int = Query(default=2021, ge=2021, le=2026),
) -> dict:
    try:
        return get_catcher_descriptive_detail(year=year, catcher_id=catcher_id)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/descriptive/{catcher_id}/strategy-bridge")
def read_catcher_descriptive_strategy_bridge(
    catcher_id: int,
    year: int = Query(default=2026, ge=2021, le=2026),
) -> dict:
    try:
        return get_catcher_descriptive_strategy_bridge(year=year, catcher_id=catcher_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/options", response_model=list[OptionItem])
def read_catcher_options(year: int) -> list[OptionItem]:
    return get_catcher_options(year=year)


@router.get("/pitchers", response_model=list[OptionItem])
def read_catcher_pitchers(year: int, catcher_id: str) -> list[OptionItem]:
    return get_catcher_pitcher_options(year=year, catcher_id=catcher_id)


@router.get("/sequence", response_model=AnalysisResponse)
def read_catcher_sequence(
    year: int,
    catcher_id: str,
    pitcher_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    current_pitch: str = "All",
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    condition_count: str | None = None,
    condition_pitch: str | None = None,
    detail_count: str | None = "0-0",
    followup_pitch: str | None = None,
) -> AnalysisResponse:
    return get_catcher_sequence(
        year=year,
        catcher_id=catcher_id,
        pitcher_id=pitcher_id,
        start_date=start_date,
        end_date=end_date,
        current_pitch=current_pitch,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        condition_count=condition_count,
        condition_pitch=condition_pitch,
        detail_count=detail_count,
        followup_pitch=followup_pitch,
    )
