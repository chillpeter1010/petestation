from pydantic import BaseModel, Field


class PitchingLeaderboardRow(BaseModel):
    rank: int
    pitcher_id: int
    pitcher_name: str
    team: str
    pitches: int
    innings_pitched: float = 0.0
    pitch_type_scores: dict[str, float] = Field(default_factory=dict)
    pitching_plus: float
    xrv_per_100: float


class PitchingDistributionBin(BaseModel):
    low: float
    high: float
    count: int


class PitchingOverviewResponse(BaseModel):
    year: int
    available_years: list[int] = Field(default_factory=list)
    generated_at: str | None = None
    model_version: str
    public_candidate: str
    minimum_pitches: int
    minimum_innings: float = 0.0
    total_pitchers: int
    total_pitches: int
    league_average: float = 100.0
    median: float
    p10: float
    p90: float
    rows: list[PitchingLeaderboardRow]
    distribution: list[PitchingDistributionBin]
    candidates: dict[str, dict] = Field(default_factory=dict)


class PitchingPitchTypeRow(BaseModel):
    pitch_type: str
    pitches: int
    pitching_plus: float
    xrv_per_100: float


class PitchingOutingRow(BaseModel):
    game_pk: int
    game_date: str
    pitches: int
    pitching_plus: float
    xrv_per_100: float


class PitchingPitcherResponse(BaseModel):
    year: int
    pitcher: PitchingLeaderboardRow
    pitch_types: list[PitchingPitchTypeRow]
    outings: list[PitchingOutingRow]
