from fastapi import APIRouter

from app.api.schemas.common import AnalysisResponse, OptionItem
from app.services.catcher_service import get_catcher_options, get_catcher_pitcher_options, get_catcher_sequence

router = APIRouter()


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
