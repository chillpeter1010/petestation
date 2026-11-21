from pydantic import BaseModel, Field


class LeverageStateInput(BaseModel):
    inning: int = Field(ge=1, le=20)
    half: str = Field(pattern="^(Top|Bottom)$")
    outs: int = Field(ge=0, le=2)
    runner_first: bool = False
    runner_second: bool = False
    runner_third: bool = False
    fielding_score: int = Field(ge=0, le=99)
    opponent_score: int = Field(ge=0, le=99)


class LeverageScenarioRequest(BaseModel):
    year: int = Field(default=2026, ge=2025, le=2026)
    entry: LeverageStateInput
    exit: LeverageStateInput


class LeverageMetric(BaseModel):
    key: str
    label: str
    value: float | int | str | None = None
    status: str = "estimated"
    note: str | None = None


class LeverageScenarioResponse(BaseModel):
    year: int
    data_as_of: str | None = None
    model_version: str
    entry: dict[str, float | int | str | None]
    exit: dict[str, float | int | str | None]
    metrics: list[LeverageMetric]
    warnings: list[str] = Field(default_factory=list)


class LeverageLeaderboardRow(BaseModel):
    rank: int
    player_id: int
    name: str
    team: str
    appearances: int | None = None
    wpa: float | None = None
    negative_wpa: float | None = None
    positive_wpa: float | None = None
    re24: float | None = None
    rew: float | None = None
    pli: float | None = None
    inli: float | None = None
    gmli: float | None = None
    exli: float | None = None
    entry_wpa_low: float | None = None
    entry_wpa_mid: float | None = None
    entry_wpa_high: float | None = None
    pulls: int | None = None
    wpa_li: float | None = None
    clutch: float | None = None
    shutdowns: int | None = None
    meltdowns: int | None = None


class LeverageValidationRow(BaseModel):
    metric: str
    samples: int
    correlation: float | None = None
    r_squared: float | None = None
    mae: float | None = None
    rmse: float | None = None
    bias: float | None = None
    slope: float | None = None
    intercept: float | None = None


class TeamSubstitutionRow(BaseModel):
    team: str
    moves: int
    announced_moves: int | None = None
    wpa_n: int
    re24_n: int
    wpa: float | None = None
    re24: float | None = None
    wpa_per_move: float | None = None
    re24_per_move: float | None = None
    mean_entry_li: float | None = None
    entry_wpa_low: float | None = None
    entry_wpa_mid: float | None = None
    entry_wpa_high: float | None = None
    entry_wpa_low_moves: int | None = None
    entry_wpa_mid_moves: int | None = None
    entry_wpa_high_moves: int | None = None


class LeverageOverviewResponse(BaseModel):
    year: int
    data_as_of: str | None = None
    reference_updated_at: str | None = None
    model_version: str
    runs_per_win: float
    warnings: list[str] = Field(default_factory=list)
    estimated_rows: list[LeverageLeaderboardRow] = Field(default_factory=list)
    reference_rows: list[LeverageLeaderboardRow] = Field(default_factory=list)
    validation: list[LeverageValidationRow] = Field(default_factory=list)
    team_pitching_rows: list[TeamSubstitutionRow] = Field(default_factory=list)
    team_pinch_hit_rows: list[TeamSubstitutionRow] = Field(default_factory=list)
    pinch_hit_data_as_of: str | None = None
