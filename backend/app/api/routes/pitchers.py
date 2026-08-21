from fastapi import APIRouter

from app.api.schemas.common import PitcherLeaderboardRow, PitcherOption
from app.services.pitcher_service import list_pitcher_leaderboard, list_pitcher_options

router = APIRouter()


@router.get("/leaderboard", response_model=list[PitcherLeaderboardRow])
def pitcher_leaderboard(year: int = 2026, role: str = "All", team: str = "All") -> list[PitcherLeaderboardRow]:
    return list_pitcher_leaderboard(year=year, role=role, team=team)


@router.get("", response_model=list[PitcherOption])
def list_pitchers(year: int = 2026, role: str = "SP") -> list[PitcherOption]:
    return list_pitcher_options(year=year, role=role)
