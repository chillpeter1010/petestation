from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    year: int
    data_updated_at: datetime | None = None
    warnings: list[str] = Field(default_factory=list)


class MetricItem(BaseModel):
    key: str
    label: str
    value: int | float | str | None
    unit: str | None = None


class OptionItem(BaseModel):
    value: str | int
    label: str
    meta: dict[str, Any] = Field(default_factory=dict)


class PitcherOption(BaseModel):
    value: int
    label: str
    name: str
    team: str
    role: str
    games: int = 0
    starts: int = 0
    relief_games: int = 0
    innings_pitched: float | None = None
    start_rate: float | None = None


class PitcherLeaderboardRow(BaseModel):
    player_id: int
    name: str
    team: str
    role: str
    games: int = 0
    starts: int = 0
    relief_games: int = 0
    ip: float | None = None
    era: float | None = None
    hits: int | None = None
    runs: int | None = None
    earned_runs: int | None = None
    walks: int | None = None
    strikeouts: int | None = None
    home_runs: int | None = None
    pitches: int | None = None
    batters_faced: int | None = None
    avg_game_score: float | None = None
    avg_pitches: float | None = None
    whip: float | None = None
    strikeout_rate: float | None = None
    walk_rate: float | None = None


class BatterOption(BaseModel):
    value: int
    label: str
    name: str
    team: str
    games: int = 0
    plate_appearances: int = 0


class BatterLeaderboardRow(BaseModel):
    player_id: int
    name: str
    team: str
    games: int = 0
    plate_appearances: int | None = None
    pitches: int | None = None
    at_bats: int | None = None
    hits: int | None = None
    home_runs: int | None = None
    walks: int | None = None
    strikeouts: int | None = None
    avg: float | None = None
    obp: float | None = None
    slg: float | None = None
    ops: float | None = None
    woba: float | None = None
    xba: float | None = None
    xslg: float | None = None
    xwoba: float | None = None
    avg_ev: float | None = None
    max_ev: float | None = None
    hard_hit_rate: float | None = None
    barrel_rate: float | None = None
    whiff_rate: float | None = None
    strikeout_rate: float | None = None
    walk_rate: float | None = None


class TablePayload(BaseModel):
    columns: list[dict[str, Any]] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    meta: ResponseMeta
    summary: list[MetricItem] = Field(default_factory=list)
    charts: dict[str, Any] = Field(default_factory=dict)
    tables: dict[str, TablePayload] = Field(default_factory=dict)
