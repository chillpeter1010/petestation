from __future__ import annotations

from pydantic import BaseModel, Field


class SwingTimingLeaderboardRow(BaseModel):
    batter_id: int
    name: str
    team: str = "-"
    teams: list[str] = Field(default_factory=list)
    age: int | None = None
    plate_appearances: int | None = None
    batter_side: str = "-"
    pitch_types: list[str] = Field(default_factory=list)
    n_swings: int = 0
    miss_distance: float | None = None
    flawed_pct: float | None = None
    perfect_pct: float | None = None
    whiff_pct: float | None = None
    competitive_pct: float | None = None
    tied_up_pct: float | None = None
    avg_tied_up_distance: float | None = None
    centered_pct: float | None = None
    flail_pct: float | None = None
    avg_flail_distance: float | None = None
    late_pct: float | None = None
    avg_late_ms: float | None = None
    on_time_pct: float | None = None
    early_pct: float | None = None
    avg_early_ms: float | None = None
    over_pct: float | None = None
    avg_over_distance: float | None = None
    lined_up_pct: float | None = None
    under_pct: float | None = None
    avg_under_distance: float | None = None
    sample_status: str = "Developing"
    avg_bat_speed: float | None = None
    season_bat_speed: float | None = None
    bat_speed_delta: float | None = None
    fast_swing_pct: float | None = None
    avg_swing_length: float | None = None
    avg_attack_angle: float | None = None
    avg_attack_direction: float | None = None
    avg_swing_path_tilt: float | None = None


class SwingTimingFilters(BaseModel):
    available_years: list[int] = Field(default_factory=list)
    pitch_groups: list[dict[str, str]] = Field(default_factory=list)
    pitch_type_groups: list[dict] = Field(default_factory=list)
    pitcher_hands: list[dict[str, str]] = Field(default_factory=list)
    batter_sides: list[dict[str, str]] = Field(default_factory=list)
    batter_teams: list[dict[str, str]] = Field(default_factory=list)
    pitcher_teams: list[dict[str, str]] = Field(default_factory=list)


class SwingTimingResponse(BaseModel):
    year: int
    data_updated_at: str | None = None
    source_url: str | None = None
    pitch_group: str = "all"
    pitch_type: str = "All"
    pitcher_hand: str = "All"
    batter_side: str = "All"
    batter_team: str = "All"
    pitcher_team: str = "All"
    minimum_swings: int = 50
    minimum_plate_appearances: int = 100
    matched_swings: int = 0
    matched_hitters: int = 0
    qualified_hitters: int = 0
    league: SwingTimingLeaderboardRow | None = None
    leaderboard: list[SwingTimingLeaderboardRow] = Field(default_factory=list)
    filters: SwingTimingFilters = Field(default_factory=SwingTimingFilters)
    warnings: list[str] = Field(default_factory=list)
    data_mode: str = "summary"


class SwingTimingPitchProfile(BaseModel):
    pitch_type: str
    pitch_label: str
    n_swings: int = 0
    miss_distance: float | None = None
    whiff_pct: float | None = None
    competitive_pct: float | None = None
    flawed_pct: float | None = None
    perfect_pct: float | None = None
    centered_pct: float | None = None
    on_time_pct: float | None = None
    lined_up_pct: float | None = None
    avg_bat_speed: float | None = None
    season_bat_speed: float | None = None
    bat_speed_delta: float | None = None
    fast_swing_pct: float | None = None
    avg_swing_length: float | None = None
    avg_attack_angle: float | None = None
    avg_attack_direction: float | None = None
    avg_swing_path_tilt: float | None = None


class SwingTimingPlayerDetailResponse(BaseModel):
    year: int
    batter_id: int
    name: str
    team: str = "-"
    pitcher_team: str = "All"
    data_mode: str = "summary"
    tracking_start: str = "2023 All-Star break"
    player: SwingTimingLeaderboardRow | None = None
    league: SwingTimingLeaderboardRow | None = None
    pitch_matrix: list[SwingTimingPitchProfile] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
