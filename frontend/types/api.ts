export interface ResponseMeta {
  year: number
  data_updated_at: string | null
  warnings: string[]
}

export interface MetricItem {
  key: string
  label: string
  value: number | string | null
  unit?: string | null
}

export interface TablePayload {
  columns: Record<string, unknown>[]
  rows: Record<string, unknown>[]
}

export interface OptionItem {
  value: string | number
  label: string
  meta: Record<string, unknown>
}

export interface AnalysisResponse {
  meta: ResponseMeta
  summary: MetricItem[]
  charts: Record<string, unknown>
  tables: Record<string, TablePayload>
}

export interface StuffCalculatorInput {
  pitch_type: string
  pitcher_hand: 'R' | 'L'
  pitches: number
  release_speed: number
  ivb: number
  hb: number
  spin_rate: number
  spin_axis: number
  extension: number
  release_pos_x: number
  release_pos_z: number
  arm_angle: number
  primary_fastball_speed: number
  primary_fastball_ivb: number
  primary_fastball_hb: number
}

export interface StuffCalculatorResponse {
  stuff_plus: number
  raw_stuff_plus: number
  reliability: number
  grade: string
  pitch_type: string
  pitch_family: string
  scale_source: string
  model_version: string
  contexts_evaluated: number
  derived_features: Record<string, number>
}

export interface PersonalOverviewResponse extends AnalysisResponse {
  pitcher_id: number
  selected_pitcher: Record<string, unknown>
  filters: Record<string, string[]>
}

export interface PitcherOption {
  value: number
  label: string
  name: string
  team: string
  role: string
  games: number
  starts: number
  relief_games: number
  innings_pitched: number | null
  start_rate: number | null
}

export interface PitcherLeaderboardRow {
  player_id: number
  name: string
  team: string
  role: string
  games: number
  starts: number
  relief_games: number
  ip: number | null
  era: number | null
  hits: number | null
  runs: number | null
  earned_runs: number | null
  walks: number | null
  strikeouts: number | null
  home_runs: number | null
  pitches: number | null
  batters_faced: number | null
  avg_game_score: number | null
  avg_pitches: number | null
  whip: number | null
  strikeout_rate: number | null
  walk_rate: number | null
}

export interface BatterOption {
  value: number
  label: string
  name: string
  team: string
  games: number
  plate_appearances: number
}

export interface BatterLeaderboardRow {
  player_id: number
  name: string
  team: string
  games: number
  plate_appearances: number | null
  pitches: number | null
  at_bats: number | null
  hits: number | null
  home_runs: number | null
  walks: number | null
  strikeouts: number | null
  avg: number | null
  obp: number | null
  slg: number | null
  ops: number | null
  woba: number | null
  xba: number | null
  xslg: number | null
  xwoba: number | null
  avg_ev: number | null
  max_ev: number | null
  hard_hit_rate: number | null
  barrel_rate: number | null
  whiff_rate: number | null
  strikeout_rate: number | null
  walk_rate: number | null
}

export interface StuffAttackMetricSet {
  pitches_seen: number
  swings: number
  batted_balls: number
  swing_pct: number | null
  zone_swing_pct: number | null
  chase_pct: number | null
  contact_pct: number | null
  whiff_pct: number | null
  hard_hit_pct: number | null
  barrel_pct: number | null
  xwoba_contact: number | null
  rv_per_100_seen: number | null
  rv_per_100_swings: number | null
}

export interface StuffAttackLeaderboardRow extends StuffAttackMetricSet {
  batter_id: number
  name: string
  team: string
  adjusted_swing_pct: number | null
  adjusted_contact_pct: number | null
  adjusted_rv_per_100_seen: number | null
  adjusted_rv_per_100_swings: number | null
  axis_metrics: Record<string, number | null>
  axis_samples: Record<string, number>
  sample_status: string
  avg_bat_speed: number | null
  season_bat_speed: number | null
  bat_speed_delta: number | null
  fast_swing_pct: number | null
  avg_swing_length: number | null
  avg_attack_angle: number | null
  avg_attack_direction: number | null
  avg_swing_path_tilt: number | null
}

export interface SwingTimingPitchProfile {
  pitch_type: string
  pitch_label: string
  n_swings: number
  miss_distance: number | null
  whiff_pct: number | null
  competitive_pct: number | null
  flawed_pct: number | null
  perfect_pct: number | null
  centered_pct: number | null
  on_time_pct: number | null
  lined_up_pct: number | null
  avg_bat_speed: number | null
  season_bat_speed: number | null
  bat_speed_delta: number | null
  fast_swing_pct: number | null
  avg_swing_length: number | null
  avg_attack_angle: number | null
  avg_attack_direction: number | null
  avg_swing_path_tilt: number | null
}

export interface SwingTimingPlayerDetailResponse {
  year: number
  batter_id: number
  name: string
  team: string
  pitcher_team: string
  data_mode: 'summary' | 'matchup_event'
  tracking_start: string
  player: SwingTimingLeaderboardRow | null
  league: SwingTimingLeaderboardRow | null
  pitch_matrix: SwingTimingPitchProfile[]
  warnings: string[]
}

export interface StuffAttackAxisOption {
  key: string
  label: string
  unit: string
  population: string
  description: string
}

export interface StuffAttackCurvePoint extends StuffAttackMetricSet {
  key: string
  label: string
  league_swing_pct: number | null
  league_contact_pct: number | null
  league_rv_per_100_seen: number | null
}

export interface StuffAttackResponse {
  year: number
  data_updated_at: string | null
  pitch_group: string
  selected_pitch_types: string[]
  pitcher_hand: 'All' | 'L' | 'R'
  stuff_bin: string
  minimum_pitches: number
  matched_pitches: number
  matched_batters: number
  qualifying_batters: number
  join_coverage_pct: number | null
  league: StuffAttackMetricSet
  league_axis_metrics: Record<string, number | null>
  leaderboard: StuffAttackLeaderboardRow[]
  selected_batter: StuffAttackLeaderboardRow | null
  response_curve: StuffAttackCurvePoint[]
  filters: {
    available_years: number[]
    pitch_groups: Array<{ value: string; label: string }>
    pitch_type_groups: Array<{ key: string; label: string; options: Array<{ value: string; label: string }> }>
    stuff_bins: Array<{ value: string; label: string }>
    axis_options: StuffAttackAxisOption[]
  }
  warnings: string[]
}

export interface SwingTimingLeaderboardRow {
  batter_id: number
  name: string
  team: string
  teams: string[]
  age: number | null
  plate_appearances: number | null
  batter_side: string
  pitch_types: string[]
  n_swings: number
  miss_distance: number | null
  flawed_pct: number | null
  perfect_pct: number | null
  whiff_pct: number | null
  competitive_pct: number | null
  tied_up_pct: number | null
  avg_tied_up_distance: number | null
  centered_pct: number | null
  flail_pct: number | null
  avg_flail_distance: number | null
  late_pct: number | null
  avg_late_ms: number | null
  on_time_pct: number | null
  early_pct: number | null
  avg_early_ms: number | null
  over_pct: number | null
  avg_over_distance: number | null
  lined_up_pct: number | null
  under_pct: number | null
  avg_under_distance: number | null
  sample_status: string
  avg_bat_speed: number | null
  season_bat_speed: number | null
  bat_speed_delta: number | null
  fast_swing_pct: number | null
  avg_swing_length: number | null
  avg_attack_angle: number | null
  avg_attack_direction: number | null
  avg_swing_path_tilt: number | null
}

export interface SwingTimingResponse {
  year: number
  data_updated_at: string | null
  source_url: string | null
  pitch_group: string
  pitch_type: string
  pitcher_hand: 'All' | 'L' | 'R'
  batter_side: 'All' | 'L' | 'R'
  batter_team: string
  pitcher_team: string
  minimum_swings: number
  minimum_plate_appearances: number
  matched_swings: number
  matched_hitters: number
  qualified_hitters: number
  league: SwingTimingLeaderboardRow | null
  leaderboard: SwingTimingLeaderboardRow[]
  filters: {
    available_years: number[]
    pitch_groups: Array<{ value: string; label: string }>
    pitch_type_groups: Array<{ key: string; label: string; options: Array<{ value: string; label: string }> }>
    pitcher_hands: Array<{ value: string; label: string }>
    batter_sides: Array<{ value: string; label: string }>
    batter_teams: Array<{ value: string; label: string }>
    pitcher_teams: Array<{ value: string; label: string }>
  }
  warnings: string[]
  data_mode: 'summary' | 'matchup_event'
}

export interface TeamIdentity {
  team_id: string
  name: string
  year: number
  primary_color: string
  secondary_color: string
  data_as_of: string | null
  logo_url: string | null
}

export interface TeamDashboardSummary {
  pitchers: number
  batters: number
  starters: number
  relievers: number
}

export interface TeamRotationRow {
  player_id: number
  name: string
  starts: number
  innings: number | null
  qs_rate: string | null
  game_score_avg: number | null
  pitches_per_start: number | null
  max_pitches: number | null
}

export interface TeamBullpenRow {
  player_id: number
  name: string
  throws: string | null
  pitches_last_3: number
  pitches_yesterday: number
  last_game: string | null
  availability: number
  status: 'Ready' | 'Monitor' | 'Rest' | string
}

export interface TeamOutingRow {
  game_pk: number
  game_date: string
  pitcher_id: number
  pitcher_name: string
  opponent: string | null
  home_away: string | null
  ip: string | null
  hits: number
  runs: number
  earned_runs: number
  walks: number
  strikeouts: number
  pitches: number
  game_score: number | null
}

export interface TeamRosterPlayer {
  player_id: number
  name: string
  team: string
  group: 'Pitcher' | 'Batter' | string
  role: string
  games: number
  starts: number
}

export interface TeamImpactPlay {
  game_pk: number
  game_date: string
  play_id: string
  video_url: string
  opponent: string
  home_away: 'Home' | 'Away' | string
  inning: number
  inning_half: string
  pitcher_name: string
  batter_name: string
  pitch_name: string | null
  event: string | null
  description: string
  team_wpa: number
  team_unit: 'Pitcher' | 'Batter' | string
}

export interface TeamSeasonRecord {
  wins: number
  losses: number
  winning_percentage: string
  division_name: string | null
  division_rank: string | null
  games_back: string | null
  streak: string | null
}

export interface TeamNextGame {
  game_pk: number
  game_datetime: string
  status: string
  opponent_name: string
  opponent_code: string | null
  home_away: 'Home' | 'Away' | string
  venue: string | null
  team_probable_pitcher: string | null
  team_probable_pitcher_id: number | null
  opponent_probable_pitcher: string | null
  opponent_probable_pitcher_id: number | null
}

export interface TeamStarterOption {
  team_code: string
  pitcher_id: number
  pitcher_name: string
  role_label: string
}

export interface TeamStarterGame {
  game_date: string
  game_pk: number | null
  opponent: string
  home_away: 'Home' | 'Away' | string
  status: string
  is_upcoming: boolean
  has_pitch_data: boolean
  starters: TeamStarterOption[]
}

export interface TeamPitchVideoRow {
  pitch_name: string
  pitch_count: number
  usage_pct: number
  release_speed: number | null
  description: string | null
  play_id: string
  video_url: string
}

export interface TeamPitchVideoResponse {
  meta: ResponseMeta
  pitcher_id: number
  pitcher_name: string
  game_pk: number
  game_date: string | null
  pitches: TeamPitchVideoRow[]
}

export interface TeamTransactionRow {
  transaction_id: number
  date: string
  effective_date: string | null
  player_id: number | null
  player_name: string
  from_team: string | null
  to_team: string | null
  type_code: string | null
  type_description: string
  category: string
  description: string
}

export interface TeamTransactionsResponse {
  meta: ResponseMeta
  team_id: string
  source: string
  fetched_at: string | null
  period_start: string | null
  period_end: string | null
  transactions: TeamTransactionRow[]
}

export interface TeamPayrollPlayer {
  name: string
  age: number | null
  service_time: string | null
  contract: string
  aav: string | null
  salaries: Record<string, string>
  salary_statuses: Record<string, string>
}

export interface TeamPayrollLineItem {
  description: string
  amounts: Record<string, string>
}

export interface TeamPayrollResponse {
  meta: ResponseMeta
  team_id: string
  team_name: string
  source: string
  source_url: string | null
  season: number
  estimated_payroll: string | null
  prior_year_payroll: string | null
  source_updated_at: string | null
  next_refresh_due: string | null
  refresh_due: boolean
  refresh_mode: string
  guaranteed_players: TeamPayrollPlayer[]
  arbitration_players: TeamPayrollPlayer[]
  pre_arbitration_players: TeamPayrollPlayer[]
  pre_arbitration_other_estimate: string | null
  off_roster_players: TeamPayrollPlayer[]
  incentives: TeamPayrollLineItem[]
  other_payments: TeamPayrollLineItem[]
  estimated_payroll_by_year: Record<string, string>
  luxury_tax_items: TeamPayrollLineItem[]
  estimated_luxury_tax_payroll: Record<string, string>
}

export interface TeamDashboardResponse {
  meta: ResponseMeta
  team: TeamIdentity
  summary: TeamDashboardSummary
  rotation: TeamRotationRow[]
  bullpen: TeamBullpenRow[]
  latest_outings: TeamOutingRow[]
  pitching_leaders: PitcherLeaderboardRow[]
  batting_leaders: BatterLeaderboardRow[]
  roster: TeamRosterPlayer[]
  impact_plays: TeamImpactPlay[]
  season_record: TeamSeasonRecord | null
  next_game: TeamNextGame | null
  starter_games: TeamStarterGame[]
}

export interface TeamHittingProfile {
  swings: number
  miss_distance: number | null
  flawed_pct: number | null
  perfect_pct: number | null
  whiff_pct: number | null
  contact_pct: number | null
  competitive_pct: number | null
  tied_up_pct: number | null
  centered_pct: number | null
  flail_pct: number | null
  late_pct: number | null
  on_time_pct: number | null
  early_pct: number | null
  over_pct: number | null
  lined_up_pct: number | null
  under_pct: number | null
  run_value_per_100_swings: number | null
}

export interface TeamHitterIntelligenceRow extends TeamHittingProfile {
  batter_id: number
  name: string
  hand: string
  age: number | null
  plate_appearances: number | null
  avg_bat_speed: number | null
  platoon_edge: number | null
  sample_status: string
}

export interface TeamPitchFamilyHitter {
  batter_id: number
  name: string
  swings: number
  miss_distance: number | null
  perfect_pct: number | null
  on_time_pct: number | null
  whiff_pct: number | null
  run_value_per_100_swings: number | null
}

export interface TeamPitchFamilyProfile {
  family: string
  label: string
  team: TeamHittingProfile
  league: TeamHittingProfile
  hitters: TeamPitchFamilyHitter[]
}

export interface TeamHittingIntelligenceResponse {
  meta: ResponseMeta
  team_id: string
  tracking_start: string
  lineup_basis: string
  hitters: TeamHitterIntelligenceRow[]
  lineup: TeamHitterIntelligenceRow[]
  team_profile: TeamHittingProfile
  league_profile: TeamHittingProfile
  pitch_families: TeamPitchFamilyProfile[]
  warnings: string[]
}

export interface HomeVideoRecommendation {
  game_pk: number
  game_date: string
  play_id: string
  video_url: string
  home_team: string
  away_team: string
  inning: number | null
  inning_half: string | null
  pitcher_name: string
  batter_name: string
  pitch_name: string | null
  event: string | null
  description: string
  wpa: number | null
  recommendation_source: string
}

export interface HomeRecommendationsResponse {
  meta: ResponseMeta
  latest_data_date: string | null
  videos: HomeVideoRecommendation[]
}

export interface LocationHeatmapCell {
  x: number
  z: number
  location_plus: number
  xrv: number
  called_strike_pct: number
  whiff_pct: number
  barrel_pct: number
  ball_pct: number
  density_count: number
  density_pct: number
}

export interface LocationHeatmapResponse {
  model_version: string
  filters: {
    sample: string
    pitcher_hand: string
    batter_side: string
    pitch_type: string
    count: string
  }
  pitch_types: string[]
  counts: string[]
  sample_pitches: number
  context_rows: number
  grid_size: number
  x_domain: [number, number]
  z_domain: [number, number]
  strike_zone: [number, number, number, number]
  cells: LocationHeatmapCell[]
  warnings: string[]
}

export interface LocationLeaderboardRow {
  rank: number
  pitcher_id: number
  pitcher_name: string
  team: string
  pitches: number
  location_plus: number
  xrv_per_100: number
  location_plus_vs_l: number | null
  location_plus_vs_r: number | null
  location_plus_se: number
  reliability: number
  sample_status: string
  loc_fa: number | null
  loc_si: number | null
  loc_fc: number | null
  loc_fs: number | null
  loc_sl: number | null
  loc_cu: number | null
  loc_ch: number | null
  loc_kc: number | null
  loc_fo: number | null
}

export interface LocationLeaderboardResponse {
  year: number
  generated_at: string | null
  model_version: string
  minimum_pitches: number
  total_pitchers: number
  rows: LocationLeaderboardRow[]
}

export interface LocationPitchTypeRow {
  pitch_name: string
  pitches: number
  location_plus: number
  xrv_per_100: number
  called_strike_pct: number
  whiff_pct: number
  barrel_pct: number
  ball_pct: number
  location_plus_se: number
  sample_status: string
}

export interface LocationOutingRow {
  game_pk: number
  game_date: string
  team: string
  pitches: number
  location_plus: number
  xrv_per_100: number
  called_strike_pct: number
  whiff_pct: number
  barrel_pct: number
  location_plus_se: number
}

export interface LocationPitcherResponse {
  year: number
  pitcher: LocationLeaderboardRow
  pitch_types: LocationPitchTypeRow[]
  outing_pitch_types: LocationPitchTypeRow[]
  outings: LocationOutingRow[]
}

export interface LocationComparisonSlice {
  minimum_pitches: number
  matched_pitchers: number
  pearson_r: number
  spearman_rho: number
  r_squared: number
  mae: number
  rmse: number
  slope: number
  intercept: number
}

export interface LocationComparisonPoint {
  pitcher_id: number
  pitcher_name: string
  pitches: number
  ours: number
  fangraphs: number
}

export interface LocationComparisonSeries {
  key: string
  label: string
  statistics: LocationComparisonSlice
  points: LocationComparisonPoint[]
}

export interface LocationComparisonResponse {
  year: number
  fangraphs_rows: number
  model_rows: number
  matched_pitchers: number
  recommended_minimum_pitches: number
  active: LocationComparisonSlice
  sensitivity: LocationComparisonSlice[]
  points: LocationComparisonPoint[]
  series: LocationComparisonSeries[]
}

export interface ComparisonMetric {
  key: string
  label: string
  value: number | string | null
  formatted_value: string
  percentile: number | null
  higher_is_better: boolean
}

export interface ComparisonPlayer {
  player_id: number
  display_name: string
  team: string
  role: string
  display_label: string
  meta: Record<string, unknown>
}

export interface ComparisonOptionsResponse {
  meta: ResponseMeta
  years: number[]
  pitchers: ComparisonPlayer[]
}

export interface ComparisonOverviewResponse {
  meta: ResponseMeta
  players: {
    left: ComparisonPlayer | null
    right: ComparisonPlayer | null
  }
  percentile_cards: {
    left: ComparisonMetric[]
    right: ComparisonMetric[]
  }
  charts: Record<string, unknown>
  tables: Record<string, TablePayload>
  notes: string[]
}

export interface PitchingLeaderboardRow {
  rank: number; pitcher_id: number; pitcher_name: string; team: string; pitches: number; innings_pitched: number
  pitch_type_scores: Record<string, number>; pitching_plus: number; xrv_per_100: number
}
export interface PitchingDistributionBin { low: number; high: number; count: number }
export interface PitchingOverviewResponse {
  year: number; available_years: number[]; generated_at: string | null; model_version: string; public_candidate: string
  minimum_pitches: number; minimum_innings: number
  total_pitchers: number; total_pitches: number; league_average: number; median: number; p10: number; p90: number
  rows: PitchingLeaderboardRow[]; distribution: PitchingDistributionBin[]
  candidates: Record<string, { validation_metrics: Record<string, number>; test_metrics: Record<string, number> }>
}
export interface PitchingPitcherResponse {
  year: number; pitcher: PitchingLeaderboardRow
  pitch_types: Array<{ pitch_type: string; pitches: number; pitching_plus: number; xrv_per_100: number }>
  outings: Array<{ game_pk: number; game_date: string; pitches: number; pitching_plus: number; xrv_per_100: number }>
}
