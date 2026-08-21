from pydantic import BaseModel, Field


class LocationHeatmapCell(BaseModel):
    x: float
    z: float
    location_plus: float
    xrv: float
    called_strike_pct: float
    whiff_pct: float
    barrel_pct: float
    ball_pct: float
    density_count: int
    density_pct: float


class LocationHeatmapFilters(BaseModel):
    sample: str
    pitcher_hand: str
    batter_side: str
    pitch_type: str
    count: str


class LocationHeatmapResponse(BaseModel):
    model_version: str
    filters: LocationHeatmapFilters
    pitch_types: list[str]
    counts: list[str]
    sample_pitches: int
    context_rows: int
    grid_size: int
    x_domain: list[float] = Field(min_length=2, max_length=2)
    z_domain: list[float] = Field(min_length=2, max_length=2)
    strike_zone: list[float] = Field(min_length=4, max_length=4)
    cells: list[LocationHeatmapCell]
    warnings: list[str] = Field(default_factory=list)


class LocationLeaderboardRow(BaseModel):
    rank: int
    pitcher_id: int
    pitcher_name: str
    team: str
    pitches: int
    location_plus: float
    xrv_per_100: float
    location_plus_vs_l: float | None = None
    location_plus_vs_r: float | None = None
    location_plus_se: float
    reliability: float
    sample_status: str
    loc_fa: float | None = None
    loc_si: float | None = None
    loc_fc: float | None = None
    loc_fs: float | None = None
    loc_sl: float | None = None
    loc_cu: float | None = None
    loc_ch: float | None = None
    loc_kc: float | None = None
    loc_fo: float | None = None


class LocationLeaderboardResponse(BaseModel):
    year: int
    generated_at: str | None = None
    model_version: str
    minimum_pitches: int
    total_pitchers: int
    rows: list[LocationLeaderboardRow]


class LocationPitchTypeRow(BaseModel):
    pitch_name: str
    pitches: int
    location_plus: float
    xrv_per_100: float
    called_strike_pct: float
    whiff_pct: float
    barrel_pct: float
    ball_pct: float
    location_plus_se: float
    sample_status: str


class LocationOutingRow(BaseModel):
    game_pk: int
    game_date: str
    team: str
    pitches: int
    location_plus: float
    xrv_per_100: float
    called_strike_pct: float
    whiff_pct: float
    barrel_pct: float
    location_plus_se: float


class LocationPitcherResponse(BaseModel):
    year: int
    pitcher: LocationLeaderboardRow
    pitch_types: list[LocationPitchTypeRow]
    outing_pitch_types: list[LocationPitchTypeRow] = Field(default_factory=list)
    outings: list[LocationOutingRow]


class LocationComparisonPoint(BaseModel):
    pitcher_id: int
    pitcher_name: str
    pitches: int
    ours: float
    fangraphs: float


class LocationComparisonSlice(BaseModel):
    minimum_pitches: int
    matched_pitchers: int
    pearson_r: float
    spearman_rho: float
    r_squared: float
    mae: float
    rmse: float
    slope: float
    intercept: float


class LocationComparisonSeries(BaseModel):
    key: str
    label: str
    statistics: LocationComparisonSlice
    points: list[LocationComparisonPoint]


class LocationComparisonResponse(BaseModel):
    year: int
    fangraphs_rows: int
    model_rows: int
    matched_pitchers: int
    recommended_minimum_pitches: int
    active: LocationComparisonSlice
    sensitivity: list[LocationComparisonSlice]
    points: list[LocationComparisonPoint]
    series: list[LocationComparisonSeries]
