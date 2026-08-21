from fastapi import APIRouter

from app.api.schemas.common import AnalysisResponse
from app.api.schemas.personal import PersonalOverviewResponse
from app.services.personal_service import (
    get_personal_discipline,
    get_personal_movement,
    get_personal_overview,
    get_personal_outing_report,
    get_personal_outings,
    get_personal_pitch_data,
    get_personal_rotation,
    get_personal_sequence,
    get_personal_timing,
    get_personal_videos,
)

router = APIRouter()


@router.get("/overview", response_model=PersonalOverviewResponse)
def read_personal_overview(year: int, pitcher_id: int, role: str = "SP") -> PersonalOverviewResponse:
    return get_personal_overview(year=year, pitcher_id=pitcher_id, role=role)


@router.get("/outings", response_model=AnalysisResponse)
def read_personal_outings(year: int, pitcher_id: int) -> AnalysisResponse:
    return get_personal_outings(year=year, pitcher_id=pitcher_id)


@router.get("/outing-report", response_model=AnalysisResponse)
def read_personal_outing_report(year: int, pitcher_id: int, game_pk: int) -> AnalysisResponse:
    return get_personal_outing_report(year=year, pitcher_id=pitcher_id, game_pk=game_pk)


@router.get("/pitches", response_model=AnalysisResponse)
def read_personal_pitches(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 250,
) -> AnalysisResponse:
    return get_personal_pitch_data(
        year=year,
        pitcher_id=pitcher_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


@router.get("/movement", response_model=AnalysisResponse)
def read_personal_movement(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    in_play_result: str | None = None,
    pa_result: str | None = None,
    catcher: str | None = None,
    include_pitch_stuff: bool = False,
) -> AnalysisResponse:
    return get_personal_movement(
        year=year,
        pitcher_id=pitcher_id,
        start_date=start_date,
        end_date=end_date,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        in_play_result=in_play_result,
        pa_result=pa_result,
        catcher=catcher,
        include_pitch_stuff=include_pitch_stuff,
    )


@router.get("/discipline", response_model=AnalysisResponse)
def read_personal_discipline(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    catcher: str | None = None,
) -> AnalysisResponse:
    return get_personal_discipline(
        year=year,
        pitcher_id=pitcher_id,
        start_date=start_date,
        end_date=end_date,
        stand=stand,
        count=count,
        pitch=pitch,
        catcher=catcher,
    )


@router.get("/sequence", response_model=AnalysisResponse)
def read_personal_sequence(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    current_pitch: str = "All",
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    catcher: str | None = None,
    condition_count: str | None = None,
    condition_pitch: str | None = None,
    detail_count: str | None = "0-0",
    followup_pitch: str | None = None,
) -> AnalysisResponse:
    return get_personal_sequence(
        year=year,
        pitcher_id=pitcher_id,
        start_date=start_date,
        end_date=end_date,
        current_pitch=current_pitch,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        catcher=catcher,
        condition_count=condition_count,
        condition_pitch=condition_pitch,
        detail_count=detail_count,
        followup_pitch=followup_pitch,
    )


@router.get("/rotation", response_model=AnalysisResponse)
def read_personal_rotation(
    year: int,
    pitcher_id: int,
    game_pk: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> AnalysisResponse:
    return get_personal_rotation(year=year, pitcher_id=pitcher_id, game_pk=game_pk, start_date=start_date, end_date=end_date)


@router.get("/videos", response_model=AnalysisResponse)
def read_personal_videos(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> AnalysisResponse:
    return get_personal_videos(year=year, pitcher_id=pitcher_id, start_date=start_date, end_date=end_date, limit=limit)


@router.get("/timing", response_model=AnalysisResponse)
def read_personal_timing(year: int, pitcher_id: int) -> AnalysisResponse:
    return get_personal_timing(year=year, pitcher_id=pitcher_id)
