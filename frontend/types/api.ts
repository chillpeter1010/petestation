export interface BatterZoneRate {
  numerator: number
  denominator: number
  value: number | null
  league_average?: number | null
  raw_pr?: number | null
  color_pr?: number | null
  peer_count?: number
  benchmark_status?: string
}
export interface BatterZoneRateCell {
  id: string
  label: string
  region: 'zone' | 'outside'
  bounds: [number, number, number, number]
  pitches: number
  rates: Record<string, BatterZoneRate>
}
export interface BatterZoneRatesResponse {
  contract_version: string
  year: number
  batter_id: number
  pitcher_hand: 'All' | 'L' | 'R'
  status: 'ready' | 'insufficient_pa' | 'no_data' | 'unavailable'
  season_pa: number
  eligible: boolean
  split_pitches: number
  located_pitches: number
  missing_location_pitches: number
  zone_height_fallback_pitches: number
  metrics: { key: string; label: string; denominator: string; format?: 'decimal' | 'percent'; direction?: 'higher' | 'lower' | 'frequency' }[]
  cells: BatterZoneRateCell[]
  benchmark_status?: string
  benchmark_version?: string | null
  benchmark_min_denominator?: number
  benchmark_min_peers?: number
  scope: string
}

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

export interface CatcherDescriptiveRow {
  rank?: number | null
  season: number
  catcher_id: number
  catcher_name: string
  team: string
  teams: string[]
  games?: number | null
  pitchers: number
  outs: number
  display_ip: string
  bf: number
  pitcher_charged_runs: number
  earned_runs: number
  home_runs: number
  walks_total: number
  hit_by_pitch: number
  strikeouts: number
  c_era?: number | null
  c_ra9?: number | null
  c_fip?: number | null
  baseline_supported_outs: number
  baseline_supported_ip: string
  baseline_coverage_pct: number
  baseline_status: 'available' | 'limited' | 'unavailable'
  t_era?: number | null
  t_ra9?: number | null
  t_fip?: number | null
  c_save_run?: number | null
  c_save_run_per_ip?: number | null
  cxera?: number | null
  txera?: number | null
  x_runs_vs_mix?: number | null
  x_runs_vs_mix_per_ip?: number | null
  xera_expected_runs?: number | null
  pitcher_mix_expected_runs?: number | null
  xera_source_coverage_pct?: number | null
  xera_status?: 'available' | 'limited' | 'unavailable'
  xera_model_version?: string | null
  drs?: number | null
  rsz?: number | null
  rcera?: number | null
  rsb?: number | null
  rgfp?: number | null
  frm?: number | null
  frv?: number | null
  throwing?: number | null
  blocking?: number | null
  framing?: number | null
  defense_value?: number | null
  drs_status?: 'available' | 'limited' | 'unavailable'
  frv_status?: 'available' | 'limited' | 'unavailable'
  source_innings_status?: 'exact' | 'different_official_accounting'
  source_display_ip?: string | null
  outs_difference?: number | null
  lco_supported_c_era?: number | null
  lco_supported_c_ra9?: number | null
  lco_t_era?: number | null
  lco_t_ra9?: number | null
  lco_t_fip?: number | null
  lco_c_save_run?: number | null
  max_pitcher_out_share_pct?: number | null
  dominant_pitcher_id?: number | null
  dominant_pitcher_name?: string | null
  dominant_pair_outs?: number | null
  dominant_pair_ip?: string | null
  dominant_pair_out_share_pct?: number | null
  non_dominant_outs?: number | null
  non_dominant_ip?: string | null
  without_dominant_c_ra9?: number | null
  without_dominant_t_ra9?: number | null
  without_dominant_c_save_run?: number | null
  without_dominant_c_save_run_per_ip?: number | null
  dominant_pair_delta_c_save_run_per_ip?: number | null
  dominant_pair_sensitivity_status?: 'stable' | 'sensitive' | 'unavailable'
  adjacent_eligible_seasons?: Array<{
    season: number
    c_save_run_per_ip: number
    absolute_delta: number
    same_sign: boolean
  }>
  adjacent_eligible_season_count?: number
  reliability_tier?: 'supported' | 'limited' | 'unavailable'
  reliability_reasons?: string[]
  sample_status: 'available' | 'limited'
  ranking_eligible: boolean
}

export interface CatcherDescriptiveLeaderboardResponse {
  contract_version: string
  source_contract_version: string
  publication_status: 'single_season_preview'
  year: number
  generated_at_utc: string
  fip_constant: number
  fip_constant_method: string
  pitcher_mix_method: string
  lco_diagnostic_method: string
  qualification: Record<string, number>
  summary: Record<string, number>
  reliability?: {
    contract_version: string
    generated_at_utc: string
    release_gate_passed: boolean
    pooled_cross_year: {
      adjacent_pairs: number
      pearson?: number | null
      spearman?: number | null
      same_sign_pct?: number | null
      mean_absolute_change_per_ip?: number | null
      pearson_cluster_bootstrap_95_ci?: {
        samples: number
        seed: number
        ci_level: number
        low?: number | null
        high?: number | null
      }
    }
    tier_counts: Record<string, number>
  }
  xera?: {
    contract_version: string
    model_version: string
    built_at_utc: string
    release_gate_passed: boolean
    selected_model: string
    evaluation: Record<string, {
      rows: number
      mae?: number | null
      rmse?: number | null
      bias?: number | null
      pearson?: number | null
      spearman?: number | null
    }>
    source_coverage: {
      rows: number
      statcast_joined_rows: number
      direct_expected_woba_rows: number
      deterministic_fallback_rows: number
      training_bip_mean_fallback_rows: number
      woba_denominator_excluded_rows: number
      fallback_bf: number
      source_supported_bf_pct: number
      fallback_policy: string
    }
    definitions: Record<string, string>
    warnings: string[]
  }
  defense?: {
    contract_version: string
    generated_at_utc: string
    release_gate_passed: boolean
    source_snapshot: {
      path: string
      sha256: string
      bytes: number
      last_modified_utc: string
      source_name: string
      source_url?: string | null
      provenance_status: string
      publication_rights_status: string
      grain: string
      unique_key: string[]
    }
    comparison_source_snapshot?: {
      path: string
      sha256: string
      bytes: number
      last_modified_utc: string
      source_name: string
      source_url?: string | null
      provenance_status: string
      publication_rights_status: string
    } | null
    source_field_coverage: Record<string, {
      non_null_rows: number
      null_rows: number
      status: 'available' | 'unavailable'
    }>
    row_counts: {
      source_team_catcher_rows: number
      canonical_team_catcher_rows: number
      catcher_seasons: number
      ranking_eligible_catcher_seasons: number
    }
    reconciliation: Record<string, unknown>
    cross_source_reconciliation: Record<string, unknown>
    cross_year_diagnostics: {
      population: string
      adjacent_pairs: number
      metrics: Record<string, { pearson?: number | null, spearman?: number | null }>
      interpretation: string
    }
    overlap_diagnostics: Record<string, unknown>
    definitions: Record<string, string>
    park_factor_status: 'deferred_by_user'
    paired_duo_status: 'unavailable_season_level_only'
    warnings: string[]
  }
  filters: Record<string, number>
  rows: CatcherDescriptiveRow[]
  warnings: string[]
}

export interface CatcherDescriptivePairedDuoRow {
  rank: number
  pair_key: string
  season: number
  catcher_id: number
  catcher_name: string
  pitcher_id: number
  pitcher_name: string
  team: string
  teams: string[]
  games: number
  outs: number
  display_ip: string
  bf: number
  pitcher_charged_runs: number
  earned_runs: number
  home_runs: number
  walks_total: number
  hit_by_pitch: number
  strikeouts: number
  c_era?: number | null
  c_ra9?: number | null
  c_fip?: number | null
  t_era?: number | null
  t_ra9?: number | null
  t_fip?: number | null
  c_save_run?: number | null
  c_save_run_per_ip?: number | null
  xera?: number | null
  pitcher_xera?: number | null
  x_runs_vs_mix?: number | null
  x_runs_vs_mix_per_ip?: number | null
  xera_expected_runs?: number | null
  xera_source_coverage_pct?: number | null
  xera_status?: 'available' | 'limited' | 'unavailable'
  lco_outs: number
  lco_display_ip: string
  lco_era?: number | null
  lco_ra9?: number | null
  lco_fip?: number | null
  lco_c_save_run?: number | null
  lco_status: 'available' | 'unavailable'
}

export interface CatcherDescriptivePairedDuoResponse {
  contract_version: string
  publication_status: 'single_season_preview'
  view: 'paired_duo'
  year: number
  generated_at_utc: string
  fip_constant: number
  qualification: Record<string, number>
  summary: { pairs: number }
  filters: Record<string, number>
  rows: CatcherDescriptivePairedDuoRow[]
  warnings: string[]
}

export interface CatcherDescriptivePairRow {
  pitcher_id: number
  pitcher_name: string
  teams: string
  outs: number
  display_ip: string
  bf: number
  pitcher_charged_runs: number
  earned_runs: number
  c_era?: number | null
  c_ra9?: number | null
  c_fip?: number | null
  pitcher_season_era?: number | null
  pitcher_season_ra9?: number | null
  pitcher_season_fip?: number | null
  lco_outs: number
  lco_display_ip: string
  lco_era?: number | null
  lco_ra9?: number | null
  lco_fip?: number | null
  c_save_run?: number | null
  c_save_run_per_ip?: number | null
  xera?: number | null
  pitcher_xera?: number | null
  x_runs_vs_mix?: number | null
  x_runs_vs_mix_per_ip?: number | null
  xera_expected_runs?: number | null
  xera_source_coverage_pct?: number | null
  xera_status?: 'available' | 'limited' | 'unavailable'
  lco_c_save_run?: number | null
  lco_status: 'available' | 'unavailable'
}

export interface CatcherDescriptiveDetailResponse {
  contract_version: string
  publication_status: 'single_season_preview'
  year: number
  catcher: CatcherDescriptiveRow
  pitcher_pairs: CatcherDescriptivePairRow[]
  fip_constant: number
  qualification: Record<string, number>
  warnings: string[]
}

export interface CatcherStrategyCountTierRow {
  count_tier: string
  decisions: number
  mean_normalized_entropy?: number | null
  mean_effective_supported_choices?: number | null
  mean_supported_deviation_gain?: number | null
  observed_choice_model_minimum_rate_pct?: number | null
}

export interface CatcherStrategyBridgeRow {
  season: number
  catcher_id: number
  total_decisions: number
  pitchers: number
  supported_set_decisions: number
  supported_set_coverage_pct?: number | null
  chosen_supported_decisions: number
  chosen_supported_coverage_pct?: number | null
  chosen_support_rate_pct?: number | null
  mean_normalized_entropy?: number | null
  mean_effective_supported_choices?: number | null
  mean_top_supported_probability_pct?: number | null
  mean_supported_deviation_gain?: number | null
  mean_chosen_gap_vs_best_supported?: number | null
  observed_choice_model_minimum_rate_pct?: number | null
  deviations_exceeding_noise_floor: number
  sample_status: 'available' | 'limited'
  count_tiers: CatcherStrategyCountTierRow[]
}

export interface CatcherStrategyBridgeResponse {
  contract_version: string
  publication_status: 'research_only_no_leaderboard'
  year: number
  catcher_id: number
  status: 'available' | 'limited' | 'unavailable'
  reason?: string | null
  method?: {
    propensity_threshold: number
    minimum_supported_decisions: number
    grain: string
    normalized_entropy: string
    supported_deviation_gain: string
  }
  release_gate?: Record<string, boolean | number>
  row?: CatcherStrategyBridgeRow | null
  warnings: string[]
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

export interface LeverageStateInput {
  inning: number
  half: 'Top' | 'Bottom'
  outs: number
  runner_first: boolean
  runner_second: boolean
  runner_third: boolean
  fielding_score: number
  opponent_score: number
}

export interface LeverageScenarioInput {
  year: 2025 | 2026
  entry: LeverageStateInput
  exit: LeverageStateInput
}

export interface LeverageMetric {
  key: string
  label: string
  value: number | string | null
  status: string
  note: string | null
}

export interface LeverageScenarioResponse {
  year: number
  data_as_of: string | null
  model_version: string
  entry: Record<string, number | string | null>
  exit: Record<string, number | string | null>
  metrics: LeverageMetric[]
  warnings: string[]
}

export interface LeverageLeaderboardRow {
  rank: number
  player_id: number
  name: string
  team: string
  appearances: number | null
  wpa: number | null
  negative_wpa: number | null
  positive_wpa: number | null
  re24: number | null
  rew: number | null
  pli: number | null
  inli: number | null
  gmli: number | null
  exli: number | null
  pulls: number | null
  wpa_li: number | null
  clutch: number | null
  shutdowns: number | null
  meltdowns: number | null
}

export interface LeverageValidationRow {
  metric: string
  samples: number
  correlation: number | null
  r_squared: number | null
  mae: number | null
  rmse: number | null
  bias: number | null
  slope: number | null
  intercept: number | null
}

export interface LeverageOverviewResponse {
  year: number
  data_as_of: string | null
  reference_updated_at: string | null
  model_version: string
  runs_per_win: number
  warnings: string[]
  estimated_rows: LeverageLeaderboardRow[]
  reference_rows: LeverageLeaderboardRow[]
  validation: LeverageValidationRow[]
}

export interface PitchQualityLeaderboardRow {
  rank: number
  player_id: number
  name: string
  team: string
  role: string
  ip: number | null
  pitches: number
  pitch_type_scores: Record<string, number | null>
  location_pitch_type_scores: Record<string, number | null>
  pitching_pitch_type_scores: Record<string, number | null>
  stuff_plus: number | null
  location_plus: number | null
  pitching_plus: number | null
  location_pitches: number
  location_status: string
}

export interface PitchQualityLeaderboardResponse {
  year: number
  data_as_of: string | null
  generated_at: string | null
  model_version: string
  location_generated_at: string | null
  pitching_generated_at: string | null
  pitching_model_version: string | null
  pitching_data_as_of: string | null
  source_status: Record<string, 'current' | 'stale' | 'unavailable'>
  cache_status: 'current' | 'stale' | 'unavailable'
  pitch_types: string[]
  total_pitchers: number
  warnings: string[]
  rows: PitchQualityLeaderboardRow[]
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

export interface PitcherMetricDefinition {
  key: string
  label: string
  category: string
  unit: string
  higher_is_better: boolean | null
  description: string
}

export interface PitcherMetricExplorerRow {
  player_id: number
  name: string
  team: string
  role: string
  metrics: Record<string, number | null>
}

export interface PitcherMetricExplorerResponse {
  year: number
  available_years: number[]
  data_as_of: string | null
  metrics: PitcherMetricDefinition[]
  rows: PitcherMetricExplorerRow[]
  teams: string[]
  source_status: Record<string, string>
  warnings: string[]
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
  avg_bat_speed: number | null
  batting_run_value: number | null
  sweet_spot_rate: number | null
  chase_rate: number | null
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

export interface ComparisonTeamStint {
  stint_index: number
  team: string
  start_date: string
  end_date: string
  pitches: number
  games: number
  label: string
}

export type PitcherTeamStint = ComparisonTeamStint

export interface BatterPeriodDateRange {
  year: number
  batter_id: number
  start_date: string | null
  end_date: string | null
  pitches: number
  current_team: string | null
  transfer_count: number
  team_stints: ComparisonTeamStint[]
}

export interface PitcherPeriodDateRange {
  year: number
  pitcher_id: number
  start_date: string | null
  end_date: string | null
  pitches: number
  current_team: string | null
  transfer_count: number
  team_stints: PitcherTeamStint[]
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

export interface BatterPeriodMetric {
  key: string
  label: string
  group: 'sample' | 'production' | 'contact' | 'discipline' | 'tracking' | 'timing'
  unit: 'count' | 'rate' | 'mph' | 'ft' | 'in' | 'pct'
  delta_unit: 'count' | 'rate' | 'mph' | 'ft' | 'in' | 'pp'
  period_a: number | null
  period_b: number | null
  delta: number | null
  denominator_label: string
  period_a_denominator: number
  period_b_denominator: number
}

export interface BatterPeriodOptionsResponse {
  meta: ResponseMeta
  years: number[]
  batters: BatterOption[]
}

export interface BatterPeriodComparisonResponse {
  meta: ResponseMeta
  batter: BatterOption | null
  periods: Record<'left' | 'right', { label: string; year: number; start_date: string; end_date: string; pitches: number; team: string | null }>
  filters: Record<string, string[]>
  metrics: BatterPeriodMetric[]
  percentile_cards: Record<'left' | 'right', ComparisonMetric[]>
  discipline: Record<'left' | 'right', { panel_groups?: Record<string, unknown>; total?: number }>
  heatmaps: Record<'left' | 'right', Record<string, unknown>[]>
  bat_speed_domain: [number, number] | null
}

export interface BatterTeamResearchResponse {
  meta: ResponseMeta
  team: string
  opponent_hand: string
  data_mode: string
  coverage: Record<string, unknown>
  order_splits: Array<Record<string, number | null>>
  hitters: BatterTeamResearchHitter[]
  position_coverage: Array<Record<string, unknown>>
  lineup_prediction: { basis?: string; players?: Array<Record<string, unknown>> }
  scenarios: Array<Record<string, unknown>>
  limitations: string[]
}

export interface BatterTeamResearchHitter {
  player_id: number
  name: string
  pa: number
  avg: number | null
  obp: number | null
  slg: number | null
  woba: number | null
  k_pct: number | null
  bb_pct: number | null
  reliability: number
  event_rates: Record<string, number>
}

export interface BatterLineupScenarioPlayer {
  slot: number
  player_id: number
  name: string
  position: string
}

export interface BatterLineupScenario {
  label: string
  lineup: BatterLineupScenarioPlayer[]
  projected_runs_per_game: number | null
  constraint_status: string
}

export interface BatterLineupScenarioResponse {
  meta: ResponseMeta
  team: string
  opponent_hand: 'L' | 'R'
  data_mode: 'precomputed_lineup_scenarios'
  cache_status: 'current' | 'stale' | 'unavailable'
  generated_at: string | null
  model_version: string
  lineup_prediction: { basis?: string; players?: Array<Record<string, unknown>> }
  scenarios: BatterLineupScenario[]
  limitations: string[]
}

export interface PitchingLeaderboardRow {
  rank: number; pitcher_id: number; pitcher_name: string; team: string; pitches: number; innings_pitched: number
  pitch_type_scores: Record<string, number>; pitching_plus: number; xrv_per_100: number
}
export interface PitchingDistributionBin { low: number; high: number; count: number }
export interface PitchingOverviewResponse {
  year: number; available_years: number[]; generated_at: string | null; model_version: string; public_candidate: string
  data_as_of: string | null; source_data_as_of: string | null; cache_status: string; warnings: string[]
  minimum_pitches: number; minimum_innings: number
  total_pitchers: number; total_pitches: number; league_average: number; median: number; p10: number; p90: number
  rows: PitchingLeaderboardRow[]; distribution: PitchingDistributionBin[]
  candidates: Record<string, { validation_metrics: Record<string, number>; test_metrics: Record<string, number> }>
}
export interface PitchingPitcherResponse {
  year: number; data_as_of: string | null; cache_status: string; warnings: string[]; pitcher: PitchingLeaderboardRow
  pitch_types: Array<{ pitch_type: string; pitches: number; pitching_plus: number; xrv_per_100: number }>
  outings: Array<{ game_pk: number; game_date: string; pitches: number; pitching_plus: number; xrv_per_100: number }>
}

export interface StaminaCleaningStep {
  key: string
  label: string
  input_rows: number
  output_rows: number
  removed_rows: number
  status: string
  note: string
}

export interface StaminaRoleSummary {
  role: 'SP' | 'RP'
  pitches: number
  appearances: number
  pitchers: number
  dual_role_pitchers: number
}

export interface StaminaCoverageRow {
  role: 'SP' | 'RP'
  pitches: number
  stuff_scored: number
  stuff_coverage_pct: number
  location_scored: number
  location_coverage_pct: number
  both_scored: number
  both_coverage_pct: number
}

export interface StaminaPitchBucket {
  role: 'SP' | 'RP'
  bucket: string
  pitches: number
  appearances: number
  pitchers: number
  stuff_coverage_pct: number
  location_coverage_pct: number
}

export interface StaminaFeatureAudit {
  group: string
  feature: string
  status: string
  coverage_pct: number
  note: string
}

export interface StaminaHypothesis {
  key: string
  title: string
  status: string
  question: string
  primary_outcomes: string[]
  required_controls: string[]
}

export interface StaminaArmAngleAudit {
  coverage_pct: number
  missing_pitches: number
  otherwise_trackable_missing: number
  dates: number
  zero_coverage_dates: string[]
  zero_coverage_date_count: number
  pattern: string
  note: string
}

export interface StaminaSlice1Point {
  role: 'SP' | 'RP'
  dimension: 'appearance_pitch_count' | 'season_workload'
  outcome: 'pitch_stuff_plus' | 'location_plus_pitch'
  outcome_label: string
  bucket: string
  order: number
  reference: boolean
  adjusted_delta: number
  ci_low: number
  ci_high: number
  standard_error: number
  raw_mean: number
  pitches: number
  appearances: number
  pitchers: number
}

export interface StaminaSlice1Summary {
  role: 'SP' | 'RP'
  dimension: 'appearance_pitch_count' | 'season_workload'
  outcome: 'pitch_stuff_plus' | 'location_plus_pitch'
  outcome_label: string
  reference_bucket: string
  terminal_bucket: string
  adjusted_delta: number
  ci_low: number
  ci_high: number
  direction: 'decline' | 'increase' | 'inconclusive'
}

export interface StaminaSlice1Diagnostic {
  role: 'SP' | 'RP'
  status: string
  pitches: number
  appearances: number | null
  pitchers: number | null
  clusters: number | null
  fixed_effects: string[]
  controls: string[]
  outcomes: Record<string, { within_r_squared: number }>
}

export interface StaminaSlice1Result {
  status: string
  method: string
  interpretation: string
  points: StaminaSlice1Point[]
  summaries: StaminaSlice1Summary[]
  diagnostics: StaminaSlice1Diagnostic[]
  warnings: string[]
}

export interface StaminaSlice2Appearance {
  role: 'SP' | 'RP'
  outcome: 'pitch_stuff_plus' | 'location_plus_pitch'
  outcome_label: string
  reference_bucket: string
  target_bucket: string
  order: number
  appearances: number
  pitchers: number
  unweighted_delta: number
  unweighted_ci_low: number
  unweighted_ci_high: number
  weighted_delta: number
  weighted_ci_low: number
  weighted_ci_high: number
}

export interface StaminaSlice2SelectionModel {
  role: 'SP' | 'RP'
  bucket: string
  auc: number
  features: string[]
  cross_fit: string
  at_risk_appearances: number
  reached_appearances: number
  marginal_reach_pct: number
  effective_sample_size: number
  max_weight: number
}

export interface StaminaSlice2TTO {
  role: 'SP' | 'RP'
  outcome: 'pitch_stuff_plus' | 'location_plus_pitch'
  outcome_label: string
  target_bucket: string
  tto: string
  appearances: number
  pitchers: number
  weighted_delta: number
  ci_low: number
  ci_high: number
}

export interface StaminaSlice2Season {
  role: 'SP' | 'RP'
  outcome: 'pitch_stuff_plus' | 'location_plus_pitch'
  outcome_label: string
  reference_bucket: string
  target_bucket: string
  order: number
  pitchers: number
  paired_delta: number
  ci_low: number
  ci_high: number
}

export interface StaminaSlice2Extreme {
  role: 'SP' | 'RP'
  outcome: 'pitch_stuff_plus' | 'location_plus_pitch'
  outcome_label: string
  slice1_adjusted_delta: number
  survivor_paired_delta: number
  weighted_paired_delta: number
  target_bucket: string
}

export interface StaminaSlice2Result {
  status: string
  method: string
  appearance_results: StaminaSlice2Appearance[]
  season_fixed_cohort: StaminaSlice2Season[]
  selection_models: StaminaSlice2SelectionModel[]
  tto_sensitivity: StaminaSlice2TTO[]
  extreme_comparison: StaminaSlice2Extreme[]
  warnings: string[]
}

export interface StaminaSlice3Pitcher {
  rank: number
  pitcher_id: number
  pitcher_name: string
  team: string
  role: 'SP' | 'RP'
  outcome: 'pitch_stuff_plus' | 'location_plus_pitch'
  outcome_label: string
  unit_pitches: number
  raw_slope: number
  standard_error?: number | null
  posterior_slope: number
  ci_low: number
  ci_high: number
  reliability: number
  reliability_label: 'strong' | 'moderate' | 'limited'
  retention_band: 'above_average' | 'below_average' | 'indistinguishable'
  appearances: number
  observations: number
  matched_pitches: number
  target_windows: number
}

export interface StaminaSlice3Prior {
  role: 'SP' | 'RP'
  outcome: 'pitch_stuff_plus' | 'location_plus_pitch'
  outcome_label: string
  unit_pitches: number
  candidate_pitchers: number
  eligible_pitchers: number
  minimum_appearances: number
  league_slope: number
  between_pitcher_sd: number
}

export interface StaminaSlice3Validation {
  role: 'SP' | 'RP'
  outcome: 'pitch_stuff_plus' | 'location_plus_pitch'
  outcome_label: string
  pitchers: number
  spearman_correlation: number | null
  mean_absolute_difference: number | null
  status: 'stable' | 'partial' | 'weak'
}

export interface StaminaSlice3Result {
  status: string
  method: string
  leaderboard: StaminaSlice3Pitcher[]
  priors: StaminaSlice3Prior[]
  split_half_validation: StaminaSlice3Validation[]
  warnings: string[]
}

export interface StaminaSlice4WorkloadAudit {
  feature: string
  field: string
  coverage_pct: number
  lagged_only: boolean
}

export interface StaminaSlice4Effect {
  analysis: string
  endpoint: 'readiness' | 'retention'
  role: 'SP' | 'RP'
  outcome: 'pitch_stuff_plus' | 'location_plus_pitch'
  outcome_label: string
  feature: string
  feature_label: string
  unit: string
  estimate: number
  ci_low: number
  ci_high: number
  within_pitcher_sd?: number | null
  standardized_effect?: number | null
  relative_strength_pct?: number | null
  significant: boolean
  appearances: number
  pitchers: number
}

export interface StaminaSlice4Diagnostic {
  endpoint: 'readiness' | 'retention'
  role: 'SP' | 'RP'
  outcome: 'pitch_stuff_plus' | 'location_plus_pitch'
  status: string
  appearances: number
  pitchers: number
  within_r_squared: number
}

export interface StaminaSlice4Validation {
  validation: string
  train_year?: number | null
  test_year?: number | null
  year?: number | null
  role?: 'SP' | 'RP' | null
  outcome?: 'pitch_stuff_plus' | 'location_plus_pitch' | null
  outcome_label?: string | null
  endpoint?: 'readiness' | 'retention' | null
  status: string
  train_appearances?: number | null
  test_appearances?: number | null
  correlation?: number | null
  rmse?: number | null
  baseline_rmse?: number | null
  mae?: number | null
  rmse_improvement_pct?: number | null
  source_coverage_pct?: number | null
  reason?: string | null
}

export interface StaminaSlice4Result {
  status: string
  method: string
  workload_audit: StaminaSlice4WorkloadAudit[]
  readiness_effects: StaminaSlice4Effect[]
  retention_effects: StaminaSlice4Effect[]
  season_effects: StaminaSlice4Effect[]
  diagnostics: StaminaSlice4Diagnostic[]
  time_validation: StaminaSlice4Validation[]
  cross_season_validation: StaminaSlice4Validation[]
  warnings: string[]
}

export interface StaminaSlice5Score {
  rank: number
  pitcher_id: number
  pitcher_name: string
  team: string
  role: 'SP' | 'RP'
  unit_pitches: number
  stamina_plus: number
  ci_low: number
  ci_high: number
  retention_advantage: number
  raw_advantage: number
  reliability: number
  reliability_label: 'strong' | 'moderate' | 'limited'
  sample_label: 'qualified' | 'limited' | 'provisional'
  seasons: number
  season?: number | null
  score_scope?: 'season' | 'trait' | null
  appearances: number
  matched_pitches: number
  publication_status: 'validated' | 'research_only' | 'season_estimate'
}

export interface StaminaSlice5Prior {
  role: 'SP' | 'RP'
  unit_pitches: number
  pitchers: number
  two_season_pitchers: number
  league_center: number
  between_pitcher_sd: number
}

export interface StaminaSlice5SeasonPrior {
  season: number
  role: 'SP' | 'RP'
  unit_pitches: number
  eligible_pitchers: number
  league_slope: number
  between_pitcher_sd: number
  split_half_spearman?: number | null
  split_half_status: string
}

export interface StaminaSlice5Validation {
  role: 'SP' | 'RP'
  train_year: number
  test_year: number
  status: 'validated' | 'research_only' | 'insufficient'
  common_pitchers: number
  reliable_pitchers: number
  source_coverage_pct: number
  spearman_correlation?: number | null
  pearson_correlation?: number | null
  rmse?: number | null
  baseline_rmse?: number | null
  rmse_improvement_pct?: number | null
  mae?: number | null
  calibration_slope?: number | null
  calibration_intercept?: number | null
  gates: Record<string, boolean>
}

export interface StaminaSlice5Result {
  status: string
  publication_status: 'validated' | 'research_only'
  method: string
  train_year: number
  test_year: number
  leaderboard: StaminaSlice5Score[]
  season_leaderboard: StaminaSlice5Score[]
  priors: StaminaSlice5Prior[]
  season_priors: StaminaSlice5SeasonPrior[]
  validations: StaminaSlice5Validation[]
  warnings: string[]
}

export interface StaminaSlice6Result {
  status: string
  method: string
  pitch_rows: number
  trait_rows: number
  expected_rows: number
  trait_coverage_pct: number
  expected_coverage_pct: number
  warnings: string[]
}

export interface StaminaSlice7FamilyCoverage {
  family: 'Fastball' | 'Breaking' | 'Offspeed'
  pitch_types: string[]
  pitches: number
  appearances: number
  pitchers: number
  stuff_coverage_pct: number
  velocity_coverage_pct: number
  early_pitches: number
  late_pitches: number
  early_usage_pct: number
  late_usage_pct: number
  late_usage_delta_pp: number
}

export interface StaminaSlice7MissingAudit {
  key: string
  label: string
  pitches: number
  pct: number
}

export interface StaminaSlice7BiasCorrelation {
  key: string
  label: string
  pitchers: number
  spearman?: number | null
}

export interface StaminaSlice7CeilingBand {
  band: string
  pitchers: number
  early_stuff: number
  late_stuff: number
  naive_delta: number
  mean_stamina_plus: number
}

export interface StaminaSlice7Target {
  key: string
  label: string
  definition: string
  purpose: string
}

export interface StaminaSlice7ReleaseGate {
  key: string
  scope: string
  threshold: string
}

export interface StaminaSlice7Result {
  status: string
  contract_version: string
  scope: string
  method: string
  classified_pitches: number
  classified_coverage_pct: number
  classified_stuff_coverage_pct: number
  pitchers_with_v1_audit: number
  family_coverage: StaminaSlice7FamilyCoverage[]
  unclassified_pitch_types: Array<{ pitch_type: string, pitches: number }>
  missing_audit: StaminaSlice7MissingAudit[]
  bias_correlations: StaminaSlice7BiasCorrelation[]
  ceiling_bands: StaminaSlice7CeilingBand[]
  targets: StaminaSlice7Target[]
  release_gates: StaminaSlice7ReleaseGate[]
  warnings: string[]
}

export interface StaminaSlice8FamilyAudit {
  family: 'Fastball' | 'Breaking' | 'Offspeed'
  pitches: number
  appearances: number
  pitchers: number
  ma5_rows: number
  ma5_coverage_pct: number
}

export interface StaminaSlice8CurvePoint {
  family: 'Overall' | 'Fastball' | 'Breaking' | 'Offspeed'
  bucket: string
  order: number
  pitches: number
  appearances: number
  pitchers: number
  adjusted_stuff?: number | null
  raw_stuff?: number | null
  trailing_ma5?: number | null
  fixed_weight_coverage_pct?: number | null
}

export interface StaminaSlice8Result {
  status: string
  contract_version: string
  method: string
  context_controls: string[]
  context_r_squared: number
  pitch_curve_rows: number
  appearance_curve_rows: number
  overall_curve_rows: number
  prior_weight_pitchers: number
  early_weight_appearances: number
  family_audit: StaminaSlice8FamilyAudit[]
  league_curves: StaminaSlice8CurvePoint[]
  warnings: string[]
}

export interface StaminaSlice9ModelComparison {
  model: string
  kind: 'baseline' | 'primary' | 'gamm' | 'ml_challenger'
  train_pitches: number
  test_pitches: number
  train_appearances: number
  test_appearances: number
  rmse: number
  mae: number
  correlation?: number | null
  rmse_improvement_pct: number
  status: string
}

export interface StaminaSlice9FamilyPrior {
  family: 'Fastball' | 'Breaking' | 'Offspeed'
  candidate_pitchers: number
  eligible_pitchers: number
  league_slope: number
  between_pitcher_sd: number
  median_reliability: number
}

export interface StaminaSlice9Influence {
  feature: string
  importance: number
  relative_strength_pct: number
}

export interface StaminaSlice9Result {
  status: string
  contract_version: string
  method: string
  development_split_date?: string | null
  selection_weighting: string
  hierarchical_estimate_rows: number
  comparisons: StaminaSlice9ModelComparison[]
  family_priors: StaminaSlice9FamilyPrior[]
  challenger_influence: StaminaSlice9Influence[]
  warnings: string[]
}

export interface StaminaSlice10ModelValidation {
  model: string
  kind: 'primary' | 'gamm' | 'ml_challenger'
  train_pitches: number
  test_pitches: number
  rmse: number
  baseline_rmse: number
  rmse_improvement_pct: number
  correlation?: number | null
  calibration_slope?: number | null
  calibration_intercept?: number | null
  residual_early_stuff_spearman?: number | null
  residual_early_velocity_spearman?: number | null
  gates: Record<string, boolean>
  status: string
}

export interface StaminaSlice10ScopeValidation {
  scope: 'Overall' | 'Fastball' | 'Breaking' | 'Offspeed'
  status: string
  common_pitchers: number
  source_coverage_pct: number
  spearman_correlation?: number | null
  rmse?: number | null
  baseline_rmse?: number | null
  rmse_improvement_pct?: number | null
  calibration_slope?: number | null
  calibration_intercept?: number | null
  residual_early_stuff_spearman?: number | null
  residual_early_velocity_spearman?: number | null
  gates: Record<string, boolean>
}

export interface StaminaSlice10Result {
  status: string
  publication_status: 'candidate_ready' | 'research_only'
  contract_version: string
  method: string
  train_year: number
  test_year: number
  selected_model?: string | null
  model_validations: StaminaSlice10ModelValidation[]
  scope_validations: StaminaSlice10ScopeValidation[]
  validated_scopes: string[]
  candidate_rows: number
  warnings: string[]
}

export interface StaminaSlice11Player {
  pitcher_id: number
  name: string
  team: string
  appearances: number
}

export interface StaminaSlice11Coverage {
  family: 'Fastball' | 'Breaking' | 'Offspeed'
  signal: string
  available_rows: number
  total_rows: number
  coverage_pct: number
}

export interface StaminaSlice11CurvePoint {
  family: 'Fastball' | 'Breaking' | 'Offspeed'
  bucket: string
  order: number
  pitches: number
  appearances: number
  pitchers: number
  stuff_delta?: number | null
  velocity_delta?: number | null
  spin_delta?: number | null
  movement_drift_inches?: number | null
  release_point_drift_inches?: number | null
  extension_delta?: number | null
  location_delta?: number | null
  usage_pct?: number | null
  usage_delta_pp?: number | null
}

export interface StaminaSlice11Transition {
  bucket: string
  order: number
  appearances: number
  speed_gap_mph?: number | null
  speed_gap_delta_mph?: number | null
}

export interface StaminaSlice11Result {
  status: string
  publication_status: 'research_only'
  contract_version: string
  method: string
  artifact_rows: number
  pitchers: number
  appearances: number
  minimum_early_pitches: number
  players: StaminaSlice11Player[]
  signal_coverage: StaminaSlice11Coverage[]
  league_curves: StaminaSlice11CurvePoint[]
  transitions: StaminaSlice11Transition[]
  warnings: string[]
}

export interface StaminaArchetypeCell {
  key: string
  label: string
  stuff_band: 'Low' | 'Average' | 'High'
  location_band: 'Low' | 'Average' | 'High'
  appearances: number
  pitchers: number
  reached_61_80: number
  early_stuff?: number | null
  early_location?: number | null
  support_status: 'supported' | 'limited'
}

export interface StaminaArchetypeCurve {
  archetype_key: string
  family: 'Fastball' | 'Breaking' | 'Offspeed'
  bucket: string
  order: number
  pitches: number
  appearances: number
  pitchers: number
  supported: boolean
  stuff_delta?: number | null
  velocity_delta?: number | null
  spin_delta?: number | null
  movement_drift_inches?: number | null
  release_point_drift_inches?: number | null
  extension_delta?: number | null
  location_delta?: number | null
  usage_pct?: number | null
  usage_delta_pp?: number | null
}

export interface StaminaArchetypeResult {
  status: string
  publication_status: 'research_only'
  contract_version: string
  method: string
  minimum_early_pitches: number
  minimum_curve_appearances: number
  minimum_curve_pitchers: number
  eligible_appearances: number
  excluded_appearances: number
  cells: StaminaArchetypeCell[]
  curves: StaminaArchetypeCurve[]
  warnings: string[]
}

export interface StaminaColdStartCheckpoint {
  checkpoint: number
  pitchers: number
  future_appearances: number
  rmse?: number | null
  baseline_rmse?: number | null
  rmse_improvement_pct?: number | null
  spearman_correlation?: number | null
  calibration_slope?: number | null
  interval_80_coverage_pct?: number | null
  residual_early_stuff_spearman?: number | null
  residual_early_velocity_spearman?: number | null
  median_reliability?: number | null
  gates: Record<string, boolean>
  status: string
}

export interface StaminaColdStartResult {
  status: string
  publication_status: 'research_only' | 'provisional_candidate'
  contract_version: string
  method: string
  train_year: number
  test_year: number
  target_window: string
  appearance_rows: number
  eligible_retention_appearances: number
  reached_61_80_appearances: number
  prior_pitchers: number
  prior_appearances: number
  between_pitcher_sd: number
  within_pitcher_sd: number
  pitch_model_rmse: number
  pitch_baseline_rmse: number
  pitch_rmse_improvement_pct: number
  checkpoints: StaminaColdStartCheckpoint[]
  validated_checkpoint?: number | null
  candidate_rows: number
  release_gates: string[]
  warnings: string[]
}

export interface StaminaColdStartV2Calibration {
  checkpoint: number
  personal_weight: number
  interval_80_halfwidth?: number | null
  development_pitchers: number
}

export interface StaminaColdStartV2Result {
  status: string
  publication_status: 'research_only'
  contract_version: string
  method: string
  development_year: number
  audit_year: number
  target_window: string
  development_rows: number
  audit_rows: number
  development_pitchers: number
  audit_pitchers: number
  prior_pitchers: number
  prior_appearances: number
  calibrations: StaminaColdStartV2Calibration[]
  development_checkpoints: StaminaColdStartCheckpoint[]
  audit_checkpoints: StaminaColdStartCheckpoint[]
  audit_passed_checkpoints: number[]
  formal_release_eligible: boolean
  candidate_rows: number
  release_gates: string[]
  warnings: string[]
}

export interface StaminaColdStartCandidate {
  pitcher: number
  pitcher_name: string
  team: string
  season: number
  stamina_plus: number
  posterior_retention: number
  ci_low: number
  ci_high: number
  reliability: number
  retention_appearances: number
  total_starts: number
  late_pitches: number
  prior_source: string
  status: string
  publication_status: string
}

export interface StaminaColdStartAppearance {
  pitcher: number
  pitcher_name: string
  team: string
  game_pk: number
  game_date: string
  season_start_number: number
  retention_start_number: number
  total_pitches: number
  reached_61_80: boolean
  retention_eligible: boolean
  early_stuff?: number | null
  early_location?: number | null
  early_velocity?: number | null
  game_retention?: number | null
  raw_retention_delta?: number | null
  observed_late_stuff?: number | null
  expected_late_stuff?: number | null
  velocity_delta?: number | null
  location_delta?: number | null
  late_pitches?: number | null
  observation_weight?: number | null
}

export interface StaminaColdStartPitcherResponse {
  year: number
  publication_status: 'research_only' | 'provisional_candidate'
  pitcher_id: number
  pitcher_name: string
  team: string
  candidate?: StaminaColdStartCandidate | null
  appearances: StaminaColdStartAppearance[]
  warnings: string[]
}

export interface StaminaResearchGame {
  game_pk: number
  game_date: string
  total_pitches: number
}

export interface StaminaResearchCurve {
  pitcher: number
  pitcher_name: string
  team: string
  game_pk: number
  game_date: string
  appearance_total_pitches: number
  pitch_family: 'Fastball' | 'Breaking' | 'Offspeed'
  analysis_bucket: string
  order: number
  pitches: number
  reference_pitches: number
  observation_weight: number
  stuff_delta?: number | null
  velocity_delta?: number | null
  spin_delta?: number | null
  movement_drift_inches?: number | null
  release_point_drift_inches?: number | null
  extension_delta?: number | null
  location_delta?: number | null
  usage_pct: number
  usage_delta_pp: number
}

export interface StaminaResearchCurvesResponse {
  year: number
  publication_status: 'research_only'
  pitcher_id: number
  pitcher_name: string
  team: string
  games: StaminaResearchGame[]
  curves: StaminaResearchCurve[]
  warnings: string[]
}

export interface StaminaGameStateScope {
  scope: 'Overall' | 'Fastball' | 'Breaking' | 'Offspeed'
  eligible_games: number
  league_retention: number
  state_sd: number
  median_reliability: number
}

export interface StaminaGameStateResult {
  status: string
  publication_status: 'observed_state'
  contract_version: string
  method: string
  reference_year: number
  season: number
  minimum_early_exact_pitches: number
  minimum_overall_late_pitches: number
  minimum_family_late_pitches: number
  minimum_fixed_mix_coverage_pct: number
  interval_method: string
  state_rows: number
  window_rows: number
  eligible_overall_games: number
  pitchers: number
  overall_start_coverage_pct: number
  median_interval_width: number
  pitch_model_rmse: number
  pitch_baseline_rmse: number
  pitch_rmse_improvement_pct: number
  early_stuff_spearman?: number | null
  early_velocity_spearman?: number | null
  within_game_split_spearman?: number | null
  scope_parameters: StaminaGameStateScope[]
  warnings: string[]
}

export interface StaminaGameState {
  pitcher: number
  game_pk: number
  game_date: string
  pitcher_name: string
  team: string
  season_start_number: number
  total_pitches: number
  scope: 'Overall' | 'Fastball' | 'Breaking' | 'Offspeed'
  pitches: number
  effective_pitches: number
  minimum_pitches: number
  eligible: boolean
  raw_retention: number
  posterior_retention?: number | null
  stamina_plus?: number | null
  ci_low?: number | null
  ci_high?: number | null
  reliability?: number | null
  confidence: 'high' | 'medium' | 'low'
  rolling_3?: number | null
  rolling_5?: number | null
  velocity_delta?: number | null
  early_stuff?: number | null
  early_velocity?: number | null
  sampling_variance: number
  clusters: number
  observed_mix_retention?: number | null
  fixed_mix_coverage?: number | null
  early_baseline_reliability?: number | null
}

export interface StaminaGameStateWindow {
  pitcher: number
  game_pk: number
  game_date: string
  pitcher_name: string
  team: string
  scope: 'Overall' | 'Fastball' | 'Breaking' | 'Offspeed'
  analysis_bucket: string
  order: number
  pitches: number
  effective_pitches: number
  retention?: number | null
  velocity_delta?: number | null
}

export interface StaminaGameStatesResponse {
  year: number
  publication_status: 'observed_state'
  pitcher_id: number
  pitcher_name: string
  team: string
  states: StaminaGameState[]
  windows: StaminaGameStateWindow[]
  warnings: string[]
}

export interface StaminaPhysicalSignal {
  key: string
  label: string
  unit: string
  weight: number
  direction: string
  definition: string
}

export interface StaminaPhysicalCoverage {
  year: number
  pitches: number
  appearances: number
  pitchers: number
  window_rows: number
  supported_late_pitches: number
  late_pitches: number
  supported_late_pct: number
  signal_coverage_pct: Record<string, number>
}

export interface StaminaSlice15Result {
  status: string
  publication_status: string
  contract_version: string
  development_year: number
  covered_years: number[]
  minimum_early_exact_pitches: number
  minimum_late_pitches: number
  minimum_component_coverage_pct: number
  method: string
  signals: StaminaPhysicalSignal[]
  coverage: StaminaPhysicalCoverage[]
  warnings: string[]
}

export interface StaminaPhysicalPlayer {
  pitcher_id: number
  name: string
  team: string
  appearances: number
}

export interface StaminaPhysicalYearAudit {
  year: number
  window_rows: number
  game_rows: number
  eligible_games: number
  pitchers: number
  median_reliability: number
  median_interval_width: number
  split_window_spearman?: number | null
  velocity_vs_physical_spearman?: number | null
  score_p05?: number | null
  score_p50?: number | null
  score_p95?: number | null
}

export interface StaminaSlice16Result {
  status: string
  publication_status: string
  model_version: string
  contract_version: string
  development_year: number
  scoring_year: number
  method: string
  players: StaminaPhysicalPlayer[]
  year_audits: StaminaPhysicalYearAudit[]
  warnings: string[]
}

export interface StaminaPhysicalGame {
  pitcher: number
  game_pk: number
  game_date: string
  pitcher_name: string
  team: string
  season_start_number: number
  windows: number
  late_pitches: number
  supported_pitches: number
  component_coverage: number
  velocity_plus?: number | null
  spin_plus?: number | null
  movement_plus?: number | null
  release_point_plus?: number | null
  extension_plus?: number | null
  arm_angle_plus?: number | null
  raw_physical_stability_plus: number
  physical_stability_plus: number
  ci_low: number
  ci_high: number
  reliability: number
  eligible: boolean
  confidence: string
}

export interface StaminaPhysicalWindow {
  pitcher: number
  game_pk: number
  game_date: string
  pitcher_name: string
  team: string
  analysis_bucket: string
  order: number
  total_pitches: number
  supported_pitches: number
  support_pct: number
  component_coverage: number
  velocity_plus?: number | null
  spin_plus?: number | null
  movement_plus?: number | null
  release_point_plus?: number | null
  extension_plus?: number | null
  arm_angle_plus?: number | null
  raw_physical_stability_plus: number
  physical_stability_plus: number
  ci_low: number
  ci_high: number
  reliability: number
  eligible: boolean
}

export interface StaminaPhysicalStabilityResponse {
  year: number
  publication_status: string
  pitcher_id: number
  pitcher_name: string
  team: string
  games: StaminaPhysicalGame[]
  windows: StaminaPhysicalWindow[]
  warnings: string[]
}

export interface StaminaCommandYearAudit {
  year: number; pitch_rows: number; window_rows: number; game_rows: number; eligible_overall_games: number; pitchers: number
  pitch_model_rmse: number; pitch_baseline_rmse: number; pitch_rmse_improvement_pct: number
  early_location_spearman?: number | null; fixed_vs_observed_mix_spearman?: number | null; split_window_spearman?: number | null
  median_reliability: number; median_interval_width: number; score_p05?: number | null; score_p50?: number | null; score_p95?: number | null
}

export interface StaminaSlice17Result {
  status: string; publication_status: string; contract_version: string; model_version: string
  development_year: number; scoring_year: number; covered_years: number[]
  minimum_early_exact_pitches: number; minimum_window_pitches: number; minimum_game_pitches: number; minimum_fixed_mix_coverage_pct: number
  method: string; players: StaminaPhysicalPlayer[]; year_audits: StaminaCommandYearAudit[]; warnings: string[]
}

export interface StaminaValidationGate { key: string; label: string; threshold: string; value: unknown; passed: boolean }
export interface StaminaSlice18Result {
  status: string; publication_status: string; validation_version: string; train_year: number; test_year: number
  predictor_window: string; target_window: string; method: string; train_rows: number; test_rows: number
  train_pair_coverage_pct: number; test_pair_coverage_pct: number
  models: Record<string, { rmse?: number | null; spearman?: number | null; calibration_slope?: number | null }>
  rmse_improvement_pct: number; rmse_improvement_over_velocity_pct: number
  pairwise_spearman: Record<string, number | null>; challenger_standardized_coefficients: Record<string, number>
  gates: StaminaValidationGate[]; composite_release_eligible: boolean; decision: string; warnings: string[]
}

export interface StaminaProductRepresentative {
  case: string; pitcher_id: number; name: string; team: string
  quality_games: number; physical_games: number; command_games: number
  quality_stamina_plus: number; physical_stability_plus: number; command_retention_plus: number
  quality_reliability: number; physical_reliability: number; command_reliability: number
}

export interface StaminaSlice19Result {
  status: string; publication_status: string; contract_version: string; year: number
  decision: string; composite_release_eligible: boolean; method: string; qualified_three_signal_pitchers: number
  representative_pitchers: StaminaProductRepresentative[]; product_rules: string[]; warnings: string[]
}

export interface StaminaCommandGame {
  pitcher: number; game_pk: number; game_date: string; pitcher_name: string; team: string; year: number; scope: string
  windows: number; late_pitches: number; raw_retention: number; raw_command_retention_plus: number; command_retention_plus: number
  ci_low: number; ci_high: number; reliability: number; fixed_mix_coverage: number; early_location: number
  early_baseline_reliability: number; eligible: boolean; confidence: string; season_start_number: number
}

export interface StaminaCommandWindow {
  pitcher: number; game_pk: number; game_date: string; order: number; analysis_bucket: string; pitcher_name: string; team: string
  scope: string; pitches: number; retention: number; observed_mix_retention?: number | null; fixed_mix_coverage?: number | null
  observed_location_change: number; early_location: number; early_baseline_reliability: number; year: number
  sampling_variance: number; raw_command_retention_plus: number; reliability: number; command_retention_plus: number
  ci_low: number; ci_high: number; eligible: boolean
}

export interface StaminaCommandRetentionResponse {
  year: number; publication_status: string; pitcher_id: number; pitcher_name: string; team: string
  games: StaminaCommandGame[]; windows: StaminaCommandWindow[]; warnings: string[]
}

export interface StaminaSeasonSummaryRow {
  pitcher: number
  pitcher_name: string
  team: string
  scope: 'Overall' | 'Fastball' | 'Breaking' | 'Offspeed'
  total_starts: number
  eligible_games: number
  supported_pitches: number
  effective_games: number
  average_pitches: number
  mean_game_reliability: number
  raw_stamina_plus: number
  unweighted_stamina_plus: number
  season_sampling_variance: number
  qualified: boolean
  minimum_games: number
  minimum_pitches: number
  stamina_plus: number
  ci_low: number
  ci_high: number
  reliability: number
  confidence: 'high' | 'medium' | 'low'
  rank?: number | null
}

export interface StaminaSeasonSummariesResponse {
  year: number
  publication_status: 'research_only'
  contract_version: string
  rows: StaminaSeasonSummaryRow[]
  warnings: string[]
}

export interface StaminaSeasonSummaryAudit {
  scope: 'Overall' | 'Fastball' | 'Breaking' | 'Offspeed'
  pitchers: number
  qualified_pitchers: number
  minimum_games: number
  minimum_pitches: number
  median_reliability: number
  median_interval_width: number
  weighted_vs_unweighted_spearman?: number | null
}

export interface StaminaSlice12Result {
  status: string
  publication_status: 'research_only'
  contract_version: string
  season: number
  method: string
  minimum_season_reliability: number
  rows: number
  scope_audits: StaminaSeasonSummaryAudit[]
  warnings: string[]
}

export interface StaminaExternalValidationGate {
  key: string
  label: string
  threshold: string
  value: unknown
  passed: boolean
}

export interface StaminaExternalSeasonAudit {
  year: number
  qualified_pitchers: number
  stamina_vs_early_stuff_spearman?: number | null
  stamina_vs_early_velocity_spearman?: number | null
  stamina_vs_eligible_games_spearman?: number | null
  stamina_vs_average_pitches_spearman?: number | null
}

export interface StaminaSlice13Result {
  status: string
  publication_status: 'validated_observed_state' | 'research_only'
  contract_version: string
  validation_year: number
  test_year: number
  leaderboard_release_eligible: boolean
  gates: StaminaExternalValidationGate[]
  season_audits: StaminaExternalSeasonAudit[]
  common_qualified_pitchers: number
  cross_season_stamina_spearman?: number | null
  cross_season_note: string
  warnings: string[]
}

export interface StaminaBiasRepairModelAudit {
  scope: 'Overall' | 'Fastball' | 'Breaking' | 'Offspeed'
  development_pitchers: number
  ridge_alpha: number
  spline_knots: number
  spline_degree: number
  prediction_center: number
}

export interface StaminaBiasRepairSeasonAudit {
  year: number
  scope: 'Overall' | 'Fastball' | 'Breaking' | 'Offspeed'
  qualified_pitchers: number
  before_early_stuff_spearman?: number | null
  after_early_stuff_spearman?: number | null
  before_early_velocity_spearman?: number | null
  after_early_velocity_spearman?: number | null
  median_reliability: number
  median_interval_width: number
  weighted_vs_unweighted_spearman?: number | null
  spread_retained_ratio?: number | null
}

export interface StaminaSlice13AResult {
  status: string
  publication_status: 'validated_observed_state' | 'research_only'
  contract_version: string
  development_year: number
  test_year: number
  leaderboard_release_eligible: boolean
  method: string
  model_audits: StaminaBiasRepairModelAudit[]
  season_audits: StaminaBiasRepairSeasonAudit[]
  gates: StaminaExternalValidationGate[]
  warnings: string[]
}

export interface StaminaLeaderboardRow {
  rank: number
  pitcher_id: number
  name: string
  team: string
  starts: number
  eligible_games: number
  average_pitches: number
  fastball_stamina_plus?: number | null
  breaking_stamina_plus?: number | null
  offspeed_stamina_plus?: number | null
  ci_low: number
  ci_high: number
  reliability: number
  stamina_plus: number
  quality_game_stamina_plus?: number | null
  physical_stability_plus?: number | null
  command_retention_plus?: number | null
}

export interface StaminaLeaderboardResponse {
  year: number
  data_as_of?: string | null
  publication_status: 'validated_observed_state'
  contract_version: string
  correction_version: string
  development_year: number
  test_year: number
  rows: StaminaLeaderboardRow[]
  warnings: string[]
}

export interface StaminaOverviewResponse {
  year: number
  data_as_of: string | null
  generated_at: string
  dataset_status: string
  model_version: string
  dataset_rows: number
  appearances: number
  pitchers: number
  dual_role_pitchers: number
  cleaning: StaminaCleaningStep[]
  roles: StaminaRoleSummary[]
  coverage: StaminaCoverageRow[]
  pitch_buckets: StaminaPitchBucket[]
  feature_audit: StaminaFeatureAudit[]
  hypotheses: StaminaHypothesis[]
  arm_angle_audit: StaminaArmAngleAudit
  slice1: StaminaSlice1Result
  slice2: StaminaSlice2Result
  slice3: StaminaSlice3Result
  slice4: StaminaSlice4Result
  slice5?: StaminaSlice5Result | null
  slice6?: StaminaSlice6Result | null
  slice7?: StaminaSlice7Result | null
  slice8?: StaminaSlice8Result | null
  slice9?: StaminaSlice9Result | null
  slice10?: StaminaSlice10Result | null
  slice11?: StaminaSlice11Result | null
  slice11_game_state?: StaminaGameStateResult | null
  slice15?: StaminaSlice15Result | null
  slice16?: StaminaSlice16Result | null
  slice17?: StaminaSlice17Result | null
  slice18?: StaminaSlice18Result | null
  slice19?: StaminaSlice19Result | null
  slice12?: StaminaSlice12Result | null
  slice13?: StaminaSlice13Result | null
  slice13a?: StaminaSlice13AResult | null
  warnings: string[]
}

export type PerformanceStateTarget = 'process_collapse' | 'result_collapse' | 'return_to_baseline' | 'strong_rebound'

export interface PerformanceStateMetricSummary {
  rows: number
  events: number
  prevalence: number | null
  average_precision: number | null
  brier: number | null
  log_loss: number | null
  calibration?: {
    ece?: number | null
    intercept?: number | null
    slope?: number | null
    bins?: Array<{ rows: number; mean_probability: number; observed_rate: number }>
  }
}

export interface PerformanceStateValidation {
  external_rows: number
  primary: PerformanceStateMetricSummary
  development_prevalence_baseline: PerformanceStateMetricSummary
  xgboost_challenger: PerformanceStateMetricSummary
  fixed_false_alert_metrics: { threshold: number; alert_rate: number; recall: number; false_alert_rate: number }
  pitcher_cluster_bootstrap: {
    requested_samples: number
    successful_samples: number
    average_precision_delta_95_interval: Array<number | null>
    brier_delta_95_interval: Array<number | null>
  }
  release_gate: {
    average_precision_gain: number
    minimum_average_precision_gain: number
    brier_not_worse: boolean
    log_loss_not_worse: boolean
    passed: boolean
  }
  excess_recovery_diagnostic?: Record<string, number | string | null> | null
}

export interface PerformanceStateModelAudit {
  eligible_development_rows: number
  split_rows: Record<string, number>
  selected_primary_layer: string
  selected_features: string[]
  validation_ablations: Record<string, PerformanceStateMetricSummary>
  validation_xgboost_challenger: PerformanceStateMetricSummary
  primary_feature_importance: Array<{ feature: string; importance: number }>
  xgboost_feature_importance: Array<{ feature: string; importance: number }>
  fixed_false_alert_threshold: number
}

export interface PerformanceStateLeaderboardRow {
  rank: number
  pitcher_id: number
  pitcher_name: string
  team: string | null
  role: 'SP' | 'RP'
  appearances: number
  eligible_forecasts: number
  latest_game_date: string
  latest_probability: number
  season_mean_probability: number
  actual_events: number
  actual_rate: number
  latest_actual: boolean
}

export interface PerformanceStateLeaderboardResponse {
  year: number
  role: 'SP' | 'RP'
  target: PerformanceStateTarget
  target_label: string
  model_version: string
  status: string
  data_as_of: string | null
  evaluation_status: string
  selected_primary_layer: string
  model: PerformanceStateModelAudit
  validation: PerformanceStateValidation
  rows: PerformanceStateLeaderboardRow[]
  warnings: string[]
}

export interface PerformanceStateV2LabRow extends PerformanceStateLeaderboardRow {
  shadow_slice18_latest_probability: number | null
  shadow_slice18_season_mean_probability: number | null
  shadow_slice19_latest_probability: number | null
  shadow_slice19_season_mean_probability: number | null
  shadow_slice18_delta: number | null
  shadow_slice19_delta: number | null
}

export interface PerformanceStateV2LabResponse {
  year: number
  role: 'SP' | 'RP'
  target: string
  target_label: string
  model_version: string
  status: string
  data_as_of: string | null
  evaluation_status: string
  selected_primary_layer: string
  rows: PerformanceStateV2LabRow[]
  primary_source: Record<string, unknown>
  shadow: Record<string, Record<string, unknown>>
  subgroup_monitor: Record<string, unknown>
  freeze_decision: Record<string, unknown>
  strict_replay: Record<string, unknown>
  fallback: { available: boolean; endpoint: string; model_version: string }
  warnings: string[]
}

export interface PerformanceStatePlayerRow {
  pitcher_id: number
  pitcher_name: string
  team: string | null
  role: 'SP' | 'RP'
  game_pk: number
  game_date: string
  pitches: number
  plate_appearances: number | null
  mean_stuff_plus: number | null
  mean_location_plus: number | null
  re24: number | null
  re24_per_pa: number | null
  wpa: number | null
  wpa_li: number | null
  wpa_li_per_pa: number | null
  process_score: number | null
  result_score: number | null
  stuff_state_forecast: number | null
  command_state_forecast: number | null
  result_state_forecast: number | null
  process_collapse: boolean
  result_collapse: boolean
  return_to_baseline: boolean
  strong_rebound: boolean
  excess_recovery: number | null
  regime_filtered_label: string | null
  regime_prior_collapse: number | null
  gas_har_variance_forecast: number | null
  evt_extreme_probability: number | null
  evt_tail_supported: boolean | null
  process_collapse_probability: number | null
  process_collapse_alert: boolean | null
  result_collapse_probability: number | null
  result_collapse_alert: boolean | null
  return_to_baseline_probability: number | null
  return_to_baseline_alert: boolean | null
  strong_rebound_probability: number | null
  strong_rebound_alert: boolean | null
}

export interface PerformanceStatePlayerResponse {
  year: number
  pitcher_id: number
  pitcher_name: string
  roles: Array<'SP' | 'RP'>
  model_version: string
  status: string
  rows: PerformanceStatePlayerRow[]
  warnings: string[]
}

export interface PerformanceStateShadowResponse {
  version: string
  status: string
  generated_at: string
  evaluation_year: number
  source_forecast_model_version: string
  observation_mode: string
  ledger_rows: number
  appended_rows: number
  probability_conflicts_preserved: number
  prospective_rows: number
  monitoring: Record<string, Record<string, {
    rows: number
    pitchers: number
    data_as_of: string | null
    metrics: PerformanceStateMetricSummary
    confusion: { hits: number; misses: number; false_alerts: number; correct_negatives: number }
  }>>
  integration_gate: { eligible: boolean; required_untouched_year: number; minimum_prospective_rows_per_role_target: number; reason: string }
  dataset_status: string
  warnings: string[]
}
export interface InGameCountPitchRow {
  pitch:string; pitches:number; usage_pct:number|null; velocity:number|null
  strike_pct:number|null; zone_pct:number|null; swing_pct:number|null; contact_pct:number|null; whiff_pct:number|null
  avg:number|null; woba:number|null; hard_hit_pct:number|null; sample_status:string
  denominators:{pitches:number;swings:number;ab:number;woba:number;tracked_bbe:number}
}
export interface InGameCountContext {
  source_status:'available'|'unavailable'
  contract_version:string;year:number;scope:string;count:string;pitcher_id:number;batter_id:number
  pitcher_name:string|null;batter_name:string|null;batter_side:string;pitcher_hand:string
  pitcher:{status:string;summary:InGameCountPitchRow;pitches:InGameCountPitchRow[]}
  batter:{status:string;summary:InGameCountPitchRow;pitches:InGameCountPitchRow[]}
}
