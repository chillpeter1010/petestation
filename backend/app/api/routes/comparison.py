from fastapi import APIRouter

from app.api.schemas.common import AnalysisResponse
from app.api.schemas.comparison import ComparisonOptionsResponse, ComparisonOverviewResponse
from app.services.comparison_service import (
    get_comparison_options,
    get_comparison_overview,
    get_period_comparison_overview,
    get_period_date_range,
)
from app.services.personal_service import get_personal_sequence
from app.services.video_service import build_playbyplay_pitch_map, fetch_sporty_video_metadata

router = APIRouter()


@router.get("/video-direct")
def read_direct_video(play_id: str) -> dict[str, object]:
    return fetch_sporty_video_metadata(play_id)


@router.get("/video-pitch")
def read_pitch_video(
    game_pk: int,
    at_bat_number: int,
    pitch_number: int,
) -> dict[str, object]:
    video_map = build_playbyplay_pitch_map(game_pk)
    matched = video_map[
        video_map["at_bat_number"].eq(int(at_bat_number))
        & video_map["pitch_number"].eq(int(pitch_number))
    ]
    if matched.empty:
        return {
            "game_pk": game_pk,
            "at_bat_number": at_bat_number,
            "pitch_number": pitch_number,
            "play_id": None,
            "video_url": None,
            "direct_video_url": None,
            "title": None,
        }
    row = matched.iloc[0].to_dict()
    play_id = row.get("play_id")
    direct_video_url = None
    title = None
    if play_id:
        meta = fetch_sporty_video_metadata(str(play_id))
        direct_video_url = meta.get("direct_video_url")
        title = meta.get("title")
    return {
        "game_pk": game_pk,
        "at_bat_number": at_bat_number,
        "pitch_number": pitch_number,
        "play_id": play_id,
        "video_url": row.get("video_url"),
        "direct_video_url": direct_video_url,
        "title": title,
    }


@router.get("/personal/options", response_model=ComparisonOptionsResponse)
def read_personal_comparison_options(year: int = 2026) -> ComparisonOptionsResponse:
    return get_comparison_options(year=year)


@router.get("/personal/overview", response_model=ComparisonOverviewResponse)
def read_personal_comparison_overview(
    year: int = 2026,
    left_year: int | None = None,
    right_year: int | None = None,
    left_pitcher_id: int | None = None,
    right_pitcher_id: int | None = None,
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    in_play_result: str | None = None,
    pa_result: str | None = None,
) -> ComparisonOverviewResponse:
    left_year = left_year or year
    right_year = right_year or year
    if left_pitcher_id is None or right_pitcher_id is None:
        options = get_comparison_options(year=left_year).pitchers
        left_pitcher_id = left_pitcher_id or (options[0].player_id if options else 0)
        right_options = get_comparison_options(year=right_year).pitchers
        right_pitcher_id = right_pitcher_id or (right_options[1].player_id if len(right_options) > 1 else left_pitcher_id)
    return get_comparison_overview(
        left_year=left_year,
        right_year=right_year,
        left_pitcher_id=left_pitcher_id,
        right_pitcher_id=right_pitcher_id,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        in_play_result=in_play_result,
        pa_result=pa_result,
    )


@router.get("/period/options", response_model=ComparisonOptionsResponse)
def read_period_comparison_options(year: int = 2026) -> ComparisonOptionsResponse:
    return get_comparison_options(year=year)


@router.get("/period/date-range")
def read_period_date_range(year: int, pitcher_id: int) -> dict[str, object]:
    return get_period_date_range(year=year, pitcher_id=pitcher_id)


@router.get("/period/overview", response_model=ComparisonOverviewResponse)
def read_period_comparison_overview(
    pitcher_id: int,
    left_year: int = 2026,
    right_year: int = 2026,
    left_start: str = "2026-03-01",
    left_end: str = "2026-05-31",
    right_start: str = "2026-06-01",
    right_end: str = "2026-07-31",
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    in_play_result: str | None = None,
    pa_result: str | None = None,
    include_pitch_stuff: bool = False,
) -> ComparisonOverviewResponse:
    return get_period_comparison_overview(
        pitcher_id=pitcher_id,
        left_year=left_year,
        right_year=right_year,
        left_start=left_start,
        left_end=left_end,
        right_start=right_start,
        right_end=right_end,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        in_play_result=in_play_result,
        pa_result=pa_result,
        include_pitch_stuff=include_pitch_stuff,
    )


@router.get("/period/sequence")
def read_period_comparison_sequence(
    pitcher_id: int,
    left_year: int = 2026,
    right_year: int = 2026,
    left_start: str = "2026-03-01",
    left_end: str = "2026-05-31",
    right_start: str = "2026-06-01",
    right_end: str = "2026-07-31",
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
) -> dict[str, AnalysisResponse]:
    common_filters = {
        "current_pitch": "All",
        "stand": stand,
        "count": count,
        "pitch": pitch,
        "pitch_result": pitch_result,
    }
    return {
        "left": get_personal_sequence(
            year=left_year,
            pitcher_id=pitcher_id,
            start_date=left_start,
            end_date=left_end,
            **common_filters,
        ),
        "right": get_personal_sequence(
            year=right_year,
            pitcher_id=pitcher_id,
            start_date=right_start,
            end_date=right_end,
            **common_filters,
        ),
    }
