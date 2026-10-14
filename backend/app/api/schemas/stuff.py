from pydantic import BaseModel, Field


class StuffCalculatorRequest(BaseModel):
    pitch_type: str = Field(default="FF", min_length=2, max_length=3)
    pitcher_hand: str = Field(default="R", pattern="^[RL]$")
    pitches: int = Field(default=50, ge=1, le=1000)
    release_speed: float = Field(default=94.0, ge=55.0, le=110.0)
    ivb: float = Field(default=15.0, ge=-35.0, le=35.0)
    hb: float = Field(default=7.0, ge=-35.0, le=35.0)
    spin_rate: float = Field(default=2300.0, ge=500.0, le=4000.0)
    spin_axis: float = Field(default=190.0, ge=0.0, le=360.0)
    extension: float = Field(default=6.3, ge=3.0, le=9.0)
    release_pos_x: float = Field(default=-1.8, ge=-5.0, le=5.0)
    release_pos_z: float = Field(default=5.8, ge=2.0, le=9.0)
    arm_angle: float = Field(default=45.0, ge=-20.0, le=90.0)
    primary_fastball_speed: float = Field(default=94.0, ge=55.0, le=110.0)
    primary_fastball_ivb: float = Field(default=15.0, ge=-35.0, le=35.0)
    primary_fastball_hb: float = Field(default=7.0, ge=-35.0, le=35.0)


class StuffCalculatorResponse(BaseModel):
    stuff_plus: float
    raw_stuff_plus: float
    reliability: float
    grade: str
    pitch_type: str
    pitch_family: str
    scale_source: str
    model_version: str
    contexts_evaluated: int
    derived_features: dict[str, float]


class PitchQualityLeaderboardRow(BaseModel):
    rank: int
    player_id: int
    name: str
    team: str
    role: str
    ip: float | None = None
    pitches: int
    pitch_type_scores: dict[str, float | None] = Field(default_factory=dict)
    location_pitch_type_scores: dict[str, float | None] = Field(default_factory=dict)
    pitching_pitch_type_scores: dict[str, float | None] = Field(default_factory=dict)
    stuff_plus: float | None = None
    location_plus: float | None = None
    pitching_plus: float | None = None
    location_pitches: int = 0
    location_status: str = "unavailable"


class PitchQualityLeaderboardResponse(BaseModel):
    year: int
    data_as_of: str | None = None
    generated_at: str | None = None
    model_version: str
    location_generated_at: str | None = None
    pitching_generated_at: str | None = None
    pitching_model_version: str | None = None
    pitching_data_as_of: str | None = None
    source_status: dict[str, str] = Field(default_factory=dict)
    cache_status: str
    pitch_types: list[str] = Field(default_factory=list)
    total_pitchers: int
    warnings: list[str] = Field(default_factory=list)
    rows: list[PitchQualityLeaderboardRow] = Field(default_factory=list)
