from __future__ import annotations

from pydantic import BaseModel, Field


class StuffAttackMetricSet(BaseModel):
    pitches_seen: int = 0
    swings: int = 0
    batted_balls: int = 0
    swing_pct: float | None = None
    zone_swing_pct: float | None = None
    chase_pct: float | None = None
    contact_pct: float | None = None
    whiff_pct: float | None = None
    hard_hit_pct: float | None = None
    barrel_pct: float | None = None
    xwoba_contact: float | None = None
    rv_per_100_seen: float | None = None
    rv_per_100_swings: float | None = None


class StuffAttackAxisOption(BaseModel):
    key: str
    label: str
    unit: str
    population: str
    description: str


class StuffAttackLeaderboardRow(StuffAttackMetricSet):
    batter_id: int
    name: str
    team: str
    adjusted_swing_pct: float | None = None
    adjusted_contact_pct: float | None = None
    adjusted_rv_per_100_seen: float | None = None
    adjusted_rv_per_100_swings: float | None = None
    axis_metrics: dict[str, float | None] = Field(default_factory=dict)
    axis_samples: dict[str, int] = Field(default_factory=dict)
    sample_status: str


class StuffAttackCurvePoint(StuffAttackMetricSet):
    key: str
    label: str
    league_swing_pct: float | None = None
    league_contact_pct: float | None = None
    league_rv_per_100_seen: float | None = None


class StuffAttackFilters(BaseModel):
    available_years: list[int] = Field(default_factory=list)
    pitch_groups: list[dict[str, str]] = Field(default_factory=list)
    pitch_type_groups: list[dict] = Field(default_factory=list)
    stuff_bins: list[dict[str, str]] = Field(default_factory=list)
    axis_options: list[StuffAttackAxisOption] = Field(default_factory=list)


class StuffAttackResponse(BaseModel):
    year: int
    data_updated_at: str | None = None
    pitch_group: str
    selected_pitch_types: list[str] = Field(default_factory=list)
    pitcher_hand: str = "All"
    stuff_bin: str
    minimum_pitches: int
    matched_pitches: int = 0
    matched_batters: int = 0
    qualifying_batters: int = 0
    join_coverage_pct: float | None = None
    league: StuffAttackMetricSet = Field(default_factory=StuffAttackMetricSet)
    league_axis_metrics: dict[str, float | None] = Field(default_factory=dict)
    leaderboard: list[StuffAttackLeaderboardRow] = Field(default_factory=list)
    selected_batter: StuffAttackLeaderboardRow | None = None
    response_curve: list[StuffAttackCurvePoint] = Field(default_factory=list)
    filters: StuffAttackFilters = Field(default_factory=StuffAttackFilters)
    warnings: list[str] = Field(default_factory=list)
