from fastapi import APIRouter, Query

from app.api.schemas.batter_period_comparison import BatterPeriodComparisonResponse, BatterPeriodOptionsResponse
from app.api.schemas.batter_team_research import BatterLineupScenarioResponse, BatterTeamResearchResponse
from app.services.batter_period_comparison_service import (
    get_batter_period_comparison,
    get_batter_period_date_range,
    get_batter_period_options,
)
from app.services.batter_team_research_service import get_batter_team_research, get_cached_batter_lineup_scenarios

router = APIRouter()


@router.get("/team-research", response_model=BatterTeamResearchResponse)
def read_batter_team_research(year: int = Query(2026), team: str = Query(...), opponent_hand: str = Query("All")) -> BatterTeamResearchResponse:
    return get_batter_team_research(year, team, opponent_hand)


@router.get("/team-research/lineup-scenarios", response_model=BatterLineupScenarioResponse)
def read_cached_batter_lineup_scenarios(
    year: int = Query(2026),
    team: str = Query(...),
    opponent_hand: str = Query(..., pattern="^[LR]$"),
) -> BatterLineupScenarioResponse:
    return get_cached_batter_lineup_scenarios(year, team, opponent_hand)


@router.get("/period/options", response_model=BatterPeriodOptionsResponse)
def read_batter_period_options(year: int = Query(2026)) -> BatterPeriodOptionsResponse:
    return get_batter_period_options(year)


@router.get("/period/date-range")
def read_batter_period_date_range(year: int, batter_id: int) -> dict[str, object]:
    return get_batter_period_date_range(year, batter_id)


@router.get("/period/overview", response_model=BatterPeriodComparisonResponse)
def read_batter_period_comparison(
    batter_id: int,
    left_year: int = 2026,
    right_year: int = 2026,
    left_start: str = "2026-03-01",
    left_end: str = "2026-05-31",
    right_start: str = "2026-06-01",
    right_end: str = "2026-07-31",
    batter_side: str | None = None,
    pitcher_hand: str | None = None,
    pitch_family: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
) -> BatterPeriodComparisonResponse:
    return get_batter_period_comparison(
        batter_id=batter_id,
        left_year=left_year,
        right_year=right_year,
        left_start=left_start,
        left_end=left_end,
        right_start=right_start,
        right_end=right_end,
        batter_side=batter_side,
        pitcher_hand=pitcher_hand,
        pitch_family=pitch_family,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
    )
