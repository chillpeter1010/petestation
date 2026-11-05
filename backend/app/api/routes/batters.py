from typing import Literal

from fastapi import APIRouter, Query
from app.api.schemas.batter_zone_rates import BatterZoneRatesResponse
from app.services.batter_zone_rates_service import get_batter_zone_rates

from app.api.schemas.batter_swing_timing import SwingTimingPlayerDetailResponse, SwingTimingResponse
from app.api.schemas.batter_stuff_attack import StuffAttackResponse
from app.api.schemas.common import AnalysisResponse, BatterLeaderboardRow, BatterOption
from app.services.batter_swing_timing_service import get_batter_swing_timing, get_batter_swing_timing_player
from app.services.batter_stuff_attack_service import get_batter_stuff_attack
from app.services.batter_service import (
    get_batter_personal_discipline,
    get_batter_personal_overview,
    list_batter_leaderboard,
    list_batter_options,
)

router = APIRouter()


@router.get("/personal/zone-rates", response_model=BatterZoneRatesResponse)
def read_batter_zone_rates(year: int = Query(2026), batter_id: int = Query(..., gt=0), pitcher_hand: Literal["All", "L", "R"] = Query("All")) -> BatterZoneRatesResponse:
    return get_batter_zone_rates(year, batter_id, pitcher_hand)


@router.get("", response_model=list[BatterOption])
def get_batters(year: int = Query(2026), team: str = Query("All")) -> list[dict]:
    return list_batter_options(year, team)


@router.get("/leaderboard", response_model=list[BatterLeaderboardRow])
def get_batter_leaderboard(year: int = Query(2026), team: str = Query("All")) -> list[dict]:
    return list_batter_leaderboard(year, team)


@router.get("/lab/stuff-attack", response_model=StuffAttackResponse)
def read_batter_stuff_attack(
    year: int = Query(2026),
    pitch_group: str = Query("fastballs"),
    pitch_types: str | None = Query(None),
    pitcher_hand: str = Query("All"),
    stuff_bin: str = Query("115_plus"),
    minimum_pitches: int = Query(50, ge=0),
    batter_id: int | None = Query(None),
) -> StuffAttackResponse:
    return get_batter_stuff_attack(
        year=year,
        pitch_group=pitch_group,
        pitch_types=tuple(value.strip().upper() for value in pitch_types.split(",") if value.strip()) if pitch_types else None,
        pitcher_hand=pitcher_hand,
        stuff_bin=stuff_bin,
        minimum_pitches=minimum_pitches,
        batter_id=batter_id,
    )


@router.get("/lab/swing-timing", response_model=SwingTimingResponse)
def read_batter_swing_timing(
    year: int = Query(2026),
    pitch_group: str = Query("all"),
    pitch_type: str = Query("All"),
    pitcher_hand: str = Query("All"),
    batter_side: str = Query("All"),
    batter_team: str = Query("All"),
    pitcher_team: str = Query("All"),
    minimum_swings: int = Query(50, ge=0),
    minimum_plate_appearances: int = Query(100, ge=5, le=700),
) -> SwingTimingResponse:
    return get_batter_swing_timing(
        year=year,
        pitch_group=pitch_group,
        pitch_type=pitch_type,
        pitcher_hand=pitcher_hand,
        batter_side=batter_side,
        batter_team=batter_team,
        pitcher_team=pitcher_team,
        minimum_swings=minimum_swings,
        minimum_plate_appearances=minimum_plate_appearances,
    )


@router.get("/lab/swing-timing/player", response_model=SwingTimingPlayerDetailResponse)
def read_batter_swing_timing_player(
    year: int = Query(2026),
    batter_id: int = Query(...),
    pitch_group: str = Query("all"),
    pitch_type: str = Query("All"),
    pitcher_hand: str = Query("All"),
    batter_side: str = Query("All"),
    pitcher_team: str = Query("All"),
) -> SwingTimingPlayerDetailResponse:
    return get_batter_swing_timing_player(
        year=year, batter_id=batter_id, pitch_group=pitch_group, pitch_type=pitch_type,
        pitcher_hand=pitcher_hand, batter_side=batter_side, pitcher_team=pitcher_team,
    )


@router.get("/personal/overview", response_model=AnalysisResponse)
def get_batter_overview(year: int = Query(2026), batter_id: int = Query(...)) -> AnalysisResponse:
    return get_batter_personal_overview(year, batter_id)


@router.get("/personal/discipline", response_model=AnalysisResponse)
def get_batter_discipline(
    year: int = Query(2026),
    batter_id: int = Query(...),
    stand: str = Query("All"),
    count: str = Query("All"),
    pitch: str = Query("All"),
    pitch_result: str = Query("All"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> AnalysisResponse:
    return get_batter_personal_discipline(
        year=year,
        batter_id=batter_id,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        start_date=start_date,
        end_date=end_date,
    )
