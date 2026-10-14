from fastapi import APIRouter

from app.api.schemas.common import PitcherLeaderboardRow, PitcherOption
from app.api.schemas.pitcher_metric_explorer import PitcherMetricExplorerResponse
from app.services.pitcher_metric_explorer_service import get_pitcher_metric_explorer
from app.services.pitcher_service import list_pitcher_leaderboard, list_pitcher_options

router = APIRouter()


@router.get("/metric-explorer", response_model=PitcherMetricExplorerResponse)
def pitcher_metric_explorer(year: int = 2026) -> PitcherMetricExplorerResponse:
    return PitcherMetricExplorerResponse(**get_pitcher_metric_explorer(year=year))


@router.get("/leaderboard", response_model=list[PitcherLeaderboardRow])
def pitcher_leaderboard(year: int = 2026, role: str = "All", team: str = "All") -> list[PitcherLeaderboardRow]:
    return list_pitcher_leaderboard(year=year, role=role, team=team)


@router.get("", response_model=list[PitcherOption])
def list_pitchers(year: int = 2026, role: str = "SP") -> list[PitcherOption]:
    return list_pitcher_options(year=year, role=role)
