from __future__ import annotations

from pydantic import BaseModel, Field

from app.api.schemas.common import BatterLeaderboardRow, PitcherLeaderboardRow, ResponseMeta


class TeamIdentity(BaseModel):
    team_id: str
    name: str
    year: int
    primary_color: str
    secondary_color: str
    data_as_of: str | None = None
    logo_url: str | None = None


class TeamDashboardSummary(BaseModel):
    pitchers: int = 0
    batters: int = 0
    starters: int = 0
    relievers: int = 0


class TeamRotationRow(BaseModel):
    player_id: int
    name: str
    starts: int = 0
    innings: float | None = None
    qs_rate: str | None = None
    game_score_avg: float | None = None
    pitches_per_start: float | None = None
    max_pitches: int | None = None


class TeamBullpenRow(BaseModel):
    player_id: int
    name: str
    throws: str | None = None
    pitches_last_3: int = 0
    pitches_yesterday: int = 0
    last_game: str | None = None
    availability: int = 0
    status: str


class TeamOutingRow(BaseModel):
    game_pk: int
    game_date: str
    pitcher_id: int
    pitcher_name: str
    opponent: str | None = None
    home_away: str | None = None
    ip: str | None = None
    hits: int = 0
    runs: int = 0
    earned_runs: int = 0
    walks: int = 0
    strikeouts: int = 0
    pitches: int = 0
    game_score: float | None = None


class TeamRosterPlayer(BaseModel):
    player_id: int
    name: str
    team: str
    group: str
    role: str
    games: int = 0
    starts: int = 0


class TeamImpactPlay(BaseModel):
    game_pk: int
    game_date: str
    play_id: str
    video_url: str
    opponent: str
    home_away: str
    inning: int
    inning_half: str
    pitcher_name: str
    batter_name: str
    pitch_name: str | None = None
    event: str | None = None
    description: str
    team_wpa: float
    team_unit: str


class TeamSeasonRecord(BaseModel):
    wins: int
    losses: int
    winning_percentage: str
    division_name: str | None = None
    division_rank: str | None = None
    games_back: str | None = None
    streak: str | None = None


class TeamNextGame(BaseModel):
    game_pk: int
    game_datetime: str
    status: str
    opponent_name: str
    opponent_code: str | None = None
    home_away: str
    venue: str | None = None
    team_probable_pitcher: str | None = None
    team_probable_pitcher_id: int | None = None
    opponent_probable_pitcher: str | None = None
    opponent_probable_pitcher_id: int | None = None


class TeamStarterOption(BaseModel):
    team_code: str
    pitcher_id: int
    pitcher_name: str
    role_label: str


class TeamStarterGame(BaseModel):
    game_date: str
    game_pk: int | None = None
    opponent: str
    home_away: str
    status: str = "Final"
    is_upcoming: bool = False
    has_pitch_data: bool = False
    starters: list[TeamStarterOption] = Field(default_factory=list)


class TeamPitchVideoRow(BaseModel):
    pitch_name: str
    pitch_count: int
    usage_pct: float
    release_speed: float | None = None
    description: str | None = None
    play_id: str
    video_url: str


class TeamPitchVideoResponse(BaseModel):
    meta: ResponseMeta
    pitcher_id: int
    pitcher_name: str
    game_pk: int
    game_date: str | None = None
    pitches: list[TeamPitchVideoRow] = Field(default_factory=list)


class TeamTransactionRow(BaseModel):
    transaction_id: int
    date: str
    effective_date: str | None = None
    player_id: int | None = None
    player_name: str
    from_team: str | None = None
    to_team: str | None = None
    type_code: str | None = None
    type_description: str
    category: str
    description: str


class TeamTransactionsResponse(BaseModel):
    meta: ResponseMeta
    team_id: str
    source: str = "MLB Stats API"
    fetched_at: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    transactions: list[TeamTransactionRow] = Field(default_factory=list)


class TeamPayrollPlayer(BaseModel):
    name: str
    age: float | None = None
    service_time: str | None = None
    contract: str
    aav: str | None = None
    salaries: dict[str, str] = Field(default_factory=dict)
    salary_statuses: dict[str, str] = Field(default_factory=dict)


class TeamPayrollLineItem(BaseModel):
    description: str
    amounts: dict[str, str] = Field(default_factory=dict)


class TeamPayrollResponse(BaseModel):
    meta: ResponseMeta
    team_id: str
    team_name: str
    source: str
    source_url: str | None = None
    season: int
    estimated_payroll: str | None = None
    prior_year_payroll: str | None = None
    source_updated_at: str | None = None
    next_refresh_due: str | None = None
    refresh_due: bool = False
    refresh_mode: str
    guaranteed_players: list[TeamPayrollPlayer] = Field(default_factory=list)
    arbitration_players: list[TeamPayrollPlayer] = Field(default_factory=list)
    pre_arbitration_players: list[TeamPayrollPlayer] = Field(default_factory=list)
    pre_arbitration_other_estimate: str | None = None
    off_roster_players: list[TeamPayrollPlayer] = Field(default_factory=list)
    incentives: list[TeamPayrollLineItem] = Field(default_factory=list)
    other_payments: list[TeamPayrollLineItem] = Field(default_factory=list)
    estimated_payroll_by_year: dict[str, str] = Field(default_factory=dict)
    luxury_tax_items: list[TeamPayrollLineItem] = Field(default_factory=list)
    estimated_luxury_tax_payroll: dict[str, str] = Field(default_factory=dict)


class TeamDashboardResponse(BaseModel):
    meta: ResponseMeta
    team: TeamIdentity
    summary: TeamDashboardSummary
    rotation: list[TeamRotationRow] = Field(default_factory=list)
    bullpen: list[TeamBullpenRow] = Field(default_factory=list)
    latest_outings: list[TeamOutingRow] = Field(default_factory=list)
    pitching_leaders: list[PitcherLeaderboardRow] = Field(default_factory=list)
    batting_leaders: list[BatterLeaderboardRow] = Field(default_factory=list)
    roster: list[TeamRosterPlayer] = Field(default_factory=list)
    impact_plays: list[TeamImpactPlay] = Field(default_factory=list)
    season_record: TeamSeasonRecord | None = None
    next_game: TeamNextGame | None = None
    starter_games: list[TeamStarterGame] = Field(default_factory=list)
