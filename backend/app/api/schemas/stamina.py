from typing import Any

from pydantic import BaseModel, Field


class StaminaCleaningStep(BaseModel):
    key: str
    label: str
    input_rows: int
    output_rows: int
    removed_rows: int
    status: str
    note: str


class StaminaRoleSummary(BaseModel):
    role: str
    pitches: int
    appearances: int
    pitchers: int
    dual_role_pitchers: int


class StaminaCoverageRow(BaseModel):
    role: str
    pitches: int
    stuff_scored: int
    stuff_coverage_pct: float
    location_scored: int
    location_coverage_pct: float
    both_scored: int
    both_coverage_pct: float


class StaminaPitchBucket(BaseModel):
    role: str
    bucket: str
    pitches: int
    appearances: int
    pitchers: int
    stuff_coverage_pct: float
    location_coverage_pct: float


class StaminaFeatureAudit(BaseModel):
    group: str
    feature: str
    status: str
    coverage_pct: float
    note: str


class StaminaHypothesis(BaseModel):
    key: str
    title: str
    status: str
    question: str
    primary_outcomes: list[str] = Field(default_factory=list)
    required_controls: list[str] = Field(default_factory=list)


class StaminaArmAngleAudit(BaseModel):
    coverage_pct: float
    missing_pitches: int
    otherwise_trackable_missing: int
    dates: int
    zero_coverage_dates: list[str] = Field(default_factory=list)
    zero_coverage_date_count: int
    pattern: str
    note: str


class StaminaSlice1Point(BaseModel):
    role: str
    dimension: str
    outcome: str
    outcome_label: str
    bucket: str
    order: int
    reference: bool
    adjusted_delta: float
    ci_low: float
    ci_high: float
    standard_error: float
    raw_mean: float
    pitches: int
    appearances: int
    pitchers: int


class StaminaSlice1Summary(BaseModel):
    role: str
    dimension: str
    outcome: str
    outcome_label: str
    reference_bucket: str
    terminal_bucket: str
    adjusted_delta: float
    ci_low: float
    ci_high: float
    direction: str


class StaminaSlice1Diagnostic(BaseModel):
    role: str
    status: str
    pitches: int
    appearances: int | None = None
    pitchers: int | None = None
    clusters: int | None = None
    fixed_effects: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    outcomes: dict[str, dict[str, float]] = Field(default_factory=dict)


class StaminaSlice1Result(BaseModel):
    status: str
    method: str
    interpretation: str
    points: list[StaminaSlice1Point] = Field(default_factory=list)
    summaries: list[StaminaSlice1Summary] = Field(default_factory=list)
    diagnostics: list[StaminaSlice1Diagnostic] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaSlice2Appearance(BaseModel):
    role: str
    outcome: str
    outcome_label: str
    reference_bucket: str
    target_bucket: str
    order: int
    appearances: int
    pitchers: int
    unweighted_delta: float
    unweighted_ci_low: float
    unweighted_ci_high: float
    weighted_delta: float
    weighted_ci_low: float
    weighted_ci_high: float


class StaminaSlice2SelectionModel(BaseModel):
    role: str
    bucket: str
    auc: float
    features: list[str] = Field(default_factory=list)
    cross_fit: str
    at_risk_appearances: int
    reached_appearances: int
    marginal_reach_pct: float
    effective_sample_size: float
    max_weight: float


class StaminaSlice2TTO(BaseModel):
    role: str
    outcome: str
    outcome_label: str
    target_bucket: str
    tto: str
    appearances: int
    pitchers: int
    weighted_delta: float
    ci_low: float
    ci_high: float


class StaminaSlice2Season(BaseModel):
    role: str
    outcome: str
    outcome_label: str
    reference_bucket: str
    target_bucket: str
    order: int
    pitchers: int
    paired_delta: float
    ci_low: float
    ci_high: float


class StaminaSlice2Extreme(BaseModel):
    role: str
    outcome: str
    outcome_label: str
    slice1_adjusted_delta: float
    survivor_paired_delta: float
    weighted_paired_delta: float
    target_bucket: str


class StaminaSlice2Result(BaseModel):
    status: str
    method: str
    appearance_results: list[StaminaSlice2Appearance] = Field(default_factory=list)
    season_fixed_cohort: list[StaminaSlice2Season] = Field(default_factory=list)
    selection_models: list[StaminaSlice2SelectionModel] = Field(default_factory=list)
    tto_sensitivity: list[StaminaSlice2TTO] = Field(default_factory=list)
    extreme_comparison: list[StaminaSlice2Extreme] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaSlice3Pitcher(BaseModel):
    rank: int
    pitcher_id: int
    pitcher_name: str
    team: str
    role: str
    outcome: str
    outcome_label: str
    unit_pitches: int
    raw_slope: float
    standard_error: float | None = None
    posterior_slope: float
    ci_low: float
    ci_high: float
    reliability: float
    reliability_label: str
    retention_band: str
    appearances: int
    observations: int
    matched_pitches: int
    target_windows: int


class StaminaSlice3Prior(BaseModel):
    role: str
    outcome: str
    outcome_label: str
    unit_pitches: int
    candidate_pitchers: int
    eligible_pitchers: int
    minimum_appearances: int
    league_slope: float
    between_pitcher_sd: float


class StaminaSlice3Validation(BaseModel):
    role: str
    outcome: str
    outcome_label: str
    pitchers: int
    spearman_correlation: float | None = None
    mean_absolute_difference: float | None = None
    status: str


class StaminaSlice3Result(BaseModel):
    status: str
    method: str
    leaderboard: list[StaminaSlice3Pitcher] = Field(default_factory=list)
    priors: list[StaminaSlice3Prior] = Field(default_factory=list)
    split_half_validation: list[StaminaSlice3Validation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaSlice4WorkloadAudit(BaseModel):
    feature: str
    field: str
    coverage_pct: float
    lagged_only: bool


class StaminaSlice4Effect(BaseModel):
    analysis: str
    endpoint: str
    role: str
    outcome: str
    outcome_label: str
    feature: str
    feature_label: str
    unit: str
    estimate: float
    ci_low: float
    ci_high: float
    within_pitcher_sd: float | None = None
    standardized_effect: float | None = None
    relative_strength_pct: float | None = None
    significant: bool
    appearances: int
    pitchers: int


class StaminaSlice4Diagnostic(BaseModel):
    endpoint: str
    role: str
    outcome: str
    status: str
    appearances: int
    pitchers: int
    within_r_squared: float


class StaminaSlice4Validation(BaseModel):
    validation: str
    train_year: int | None = None
    test_year: int | None = None
    year: int | None = None
    role: str | None = None
    outcome: str | None = None
    outcome_label: str | None = None
    endpoint: str | None = None
    status: str
    train_appearances: int | None = None
    test_appearances: int | None = None
    correlation: float | None = None
    rmse: float | None = None
    baseline_rmse: float | None = None
    mae: float | None = None
    rmse_improvement_pct: float | None = None
    source_coverage_pct: float | None = None
    reason: str | None = None


class StaminaSlice4Result(BaseModel):
    status: str
    method: str
    workload_audit: list[StaminaSlice4WorkloadAudit] = Field(default_factory=list)
    readiness_effects: list[StaminaSlice4Effect] = Field(default_factory=list)
    retention_effects: list[StaminaSlice4Effect] = Field(default_factory=list)
    season_effects: list[StaminaSlice4Effect] = Field(default_factory=list)
    diagnostics: list[StaminaSlice4Diagnostic] = Field(default_factory=list)
    time_validation: list[StaminaSlice4Validation] = Field(default_factory=list)
    cross_season_validation: list[StaminaSlice4Validation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaSlice5Score(BaseModel):
    rank: int
    pitcher_id: int
    pitcher_name: str
    team: str
    role: str
    unit_pitches: int
    stamina_plus: float
    ci_low: float
    ci_high: float
    retention_advantage: float
    raw_advantage: float
    reliability: float
    reliability_label: str
    sample_label: str
    seasons: int
    season: int | None = None
    score_scope: str | None = None
    appearances: int
    matched_pitches: int
    publication_status: str


class StaminaSlice5Prior(BaseModel):
    role: str
    unit_pitches: int
    pitchers: int
    two_season_pitchers: int
    league_center: float
    between_pitcher_sd: float


class StaminaSlice5SeasonPrior(BaseModel):
    season: int
    role: str
    unit_pitches: int
    eligible_pitchers: int
    league_slope: float
    between_pitcher_sd: float
    split_half_spearman: float | None = None
    split_half_status: str


class StaminaSlice5Validation(BaseModel):
    role: str
    train_year: int
    test_year: int
    status: str
    common_pitchers: int
    reliable_pitchers: int
    source_coverage_pct: float
    spearman_correlation: float | None = None
    pearson_correlation: float | None = None
    rmse: float | None = None
    baseline_rmse: float | None = None
    rmse_improvement_pct: float | None = None
    mae: float | None = None
    calibration_slope: float | None = None
    calibration_intercept: float | None = None
    gates: dict[str, bool] = Field(default_factory=dict)


class StaminaSlice5Result(BaseModel):
    status: str
    publication_status: str
    method: str
    train_year: int
    test_year: int
    leaderboard: list[StaminaSlice5Score] = Field(default_factory=list)
    season_leaderboard: list[StaminaSlice5Score] = Field(default_factory=list)
    priors: list[StaminaSlice5Prior] = Field(default_factory=list)
    season_priors: list[StaminaSlice5SeasonPrior] = Field(default_factory=list)
    validations: list[StaminaSlice5Validation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaSlice6Result(BaseModel):
    status: str
    method: str
    pitch_rows: int
    trait_rows: int
    expected_rows: int
    trait_coverage_pct: float
    expected_coverage_pct: float
    warnings: list[str] = Field(default_factory=list)


class StaminaSlice7FamilyCoverage(BaseModel):
    family: str
    pitch_types: list[str] = Field(default_factory=list)
    pitches: int
    appearances: int
    pitchers: int
    stuff_coverage_pct: float
    velocity_coverage_pct: float
    early_pitches: int
    late_pitches: int
    early_usage_pct: float
    late_usage_pct: float
    late_usage_delta_pp: float


class StaminaSlice7UnclassifiedPitch(BaseModel):
    pitch_type: str
    pitches: int


class StaminaSlice7MissingAudit(BaseModel):
    key: str
    label: str
    pitches: int
    pct: float


class StaminaSlice7BiasCorrelation(BaseModel):
    key: str
    label: str
    pitchers: int
    spearman: float | None = None


class StaminaSlice7CeilingBand(BaseModel):
    band: str
    pitchers: int
    early_stuff: float
    late_stuff: float
    naive_delta: float
    mean_stamina_plus: float


class StaminaSlice7Target(BaseModel):
    key: str
    label: str
    definition: str
    purpose: str


class StaminaSlice7ReleaseGate(BaseModel):
    key: str
    scope: str
    threshold: str


class StaminaSlice7Result(BaseModel):
    status: str
    contract_version: str
    scope: str
    method: str
    classified_pitches: int
    classified_coverage_pct: float
    classified_stuff_coverage_pct: float
    pitchers_with_v1_audit: int
    family_coverage: list[StaminaSlice7FamilyCoverage] = Field(default_factory=list)
    unclassified_pitch_types: list[StaminaSlice7UnclassifiedPitch] = Field(default_factory=list)
    missing_audit: list[StaminaSlice7MissingAudit] = Field(default_factory=list)
    bias_correlations: list[StaminaSlice7BiasCorrelation] = Field(default_factory=list)
    ceiling_bands: list[StaminaSlice7CeilingBand] = Field(default_factory=list)
    targets: list[StaminaSlice7Target] = Field(default_factory=list)
    release_gates: list[StaminaSlice7ReleaseGate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaSlice8FamilyAudit(BaseModel):
    family: str
    pitches: int
    appearances: int
    pitchers: int
    ma5_rows: int
    ma5_coverage_pct: float


class StaminaSlice8CurvePoint(BaseModel):
    family: str
    bucket: str
    order: int
    pitches: int
    appearances: int
    pitchers: int
    adjusted_stuff: float | None = None
    raw_stuff: float | None = None
    trailing_ma5: float | None = None
    fixed_weight_coverage_pct: float | None = None


class StaminaSlice8Result(BaseModel):
    status: str
    contract_version: str
    method: str
    context_controls: list[str] = Field(default_factory=list)
    context_r_squared: float
    pitch_curve_rows: int
    appearance_curve_rows: int
    overall_curve_rows: int
    prior_weight_pitchers: int
    early_weight_appearances: int
    family_audit: list[StaminaSlice8FamilyAudit] = Field(default_factory=list)
    league_curves: list[StaminaSlice8CurvePoint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaSlice9ModelComparison(BaseModel):
    model: str
    kind: str
    train_pitches: int
    test_pitches: int
    train_appearances: int
    test_appearances: int
    rmse: float
    mae: float
    correlation: float | None = None
    rmse_improvement_pct: float
    status: str


class StaminaSlice9FamilyPrior(BaseModel):
    family: str
    candidate_pitchers: int
    eligible_pitchers: int
    league_slope: float
    between_pitcher_sd: float
    median_reliability: float


class StaminaSlice9Influence(BaseModel):
    feature: str
    importance: float
    relative_strength_pct: float


class StaminaSlice9Result(BaseModel):
    status: str
    contract_version: str
    method: str
    development_split_date: str | None = None
    selection_weighting: str
    hierarchical_estimate_rows: int
    comparisons: list[StaminaSlice9ModelComparison] = Field(default_factory=list)
    family_priors: list[StaminaSlice9FamilyPrior] = Field(default_factory=list)
    challenger_influence: list[StaminaSlice9Influence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaSlice10ModelValidation(BaseModel):
    model: str
    kind: str
    train_pitches: int
    test_pitches: int
    rmse: float
    baseline_rmse: float
    rmse_improvement_pct: float
    correlation: float | None = None
    calibration_slope: float | None = None
    calibration_intercept: float | None = None
    residual_early_stuff_spearman: float | None = None
    residual_early_velocity_spearman: float | None = None
    gates: dict[str, bool] = Field(default_factory=dict)
    status: str


class StaminaSlice10ScopeValidation(BaseModel):
    scope: str
    status: str
    common_pitchers: int
    source_coverage_pct: float
    spearman_correlation: float | None = None
    rmse: float | None = None
    baseline_rmse: float | None = None
    rmse_improvement_pct: float | None = None
    calibration_slope: float | None = None
    calibration_intercept: float | None = None
    residual_early_stuff_spearman: float | None = None
    residual_early_velocity_spearman: float | None = None
    gates: dict[str, bool] = Field(default_factory=dict)


class StaminaSlice10Result(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    method: str
    train_year: int
    test_year: int
    selected_model: str | None = None
    model_validations: list[StaminaSlice10ModelValidation] = Field(default_factory=list)
    scope_validations: list[StaminaSlice10ScopeValidation] = Field(default_factory=list)
    validated_scopes: list[str] = Field(default_factory=list)
    candidate_rows: int
    warnings: list[str] = Field(default_factory=list)


class StaminaSlice11Player(BaseModel):
    pitcher_id: int
    name: str
    team: str
    appearances: int


class StaminaSlice11Coverage(BaseModel):
    family: str
    signal: str
    available_rows: int
    total_rows: int
    coverage_pct: float


class StaminaSlice11CurvePoint(BaseModel):
    family: str
    bucket: str
    order: int
    pitches: int
    appearances: int
    pitchers: int
    stuff_delta: float | None = None
    velocity_delta: float | None = None
    spin_delta: float | None = None
    movement_drift_inches: float | None = None
    release_point_drift_inches: float | None = None
    extension_delta: float | None = None
    location_delta: float | None = None
    usage_pct: float | None = None
    usage_delta_pp: float | None = None


class StaminaSlice11Transition(BaseModel):
    bucket: str
    order: int
    appearances: int
    speed_gap_mph: float | None = None
    speed_gap_delta_mph: float | None = None


class StaminaSlice11Result(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    method: str
    artifact_rows: int
    pitchers: int
    appearances: int
    minimum_early_pitches: int
    players: list[StaminaSlice11Player] = Field(default_factory=list)
    signal_coverage: list[StaminaSlice11Coverage] = Field(default_factory=list)
    league_curves: list[StaminaSlice11CurvePoint] = Field(default_factory=list)
    transitions: list[StaminaSlice11Transition] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaArchetypeCell(BaseModel):
    key: str
    label: str
    stuff_band: str
    location_band: str
    appearances: int
    pitchers: int
    reached_61_80: int
    early_stuff: float | None = None
    early_location: float | None = None
    support_status: str


class StaminaArchetypeCurve(BaseModel):
    archetype_key: str
    family: str
    bucket: str
    order: int
    pitches: int
    appearances: int
    pitchers: int
    supported: bool
    stuff_delta: float | None = None
    velocity_delta: float | None = None
    spin_delta: float | None = None
    movement_drift_inches: float | None = None
    release_point_drift_inches: float | None = None
    extension_delta: float | None = None
    location_delta: float | None = None
    usage_pct: float | None = None
    usage_delta_pp: float | None = None


class StaminaArchetypeResult(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    method: str
    minimum_early_pitches: int
    minimum_curve_appearances: int
    minimum_curve_pitchers: int
    eligible_appearances: int
    excluded_appearances: int
    cells: list[StaminaArchetypeCell] = Field(default_factory=list)
    curves: list[StaminaArchetypeCurve] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaColdStartCheckpoint(BaseModel):
    checkpoint: int
    pitchers: int
    future_appearances: int
    rmse: float | None = None
    baseline_rmse: float | None = None
    rmse_improvement_pct: float | None = None
    spearman_correlation: float | None = None
    calibration_slope: float | None = None
    interval_80_coverage_pct: float | None = None
    residual_early_stuff_spearman: float | None = None
    residual_early_velocity_spearman: float | None = None
    median_reliability: float | None = None
    gates: dict[str, bool] = Field(default_factory=dict)
    status: str


class StaminaColdStartResult(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    method: str
    train_year: int
    test_year: int
    target_window: str
    appearance_rows: int
    eligible_retention_appearances: int
    reached_61_80_appearances: int
    prior_pitchers: int
    prior_appearances: int
    between_pitcher_sd: float
    within_pitcher_sd: float
    pitch_model_rmse: float
    pitch_baseline_rmse: float
    pitch_rmse_improvement_pct: float
    checkpoints: list[StaminaColdStartCheckpoint] = Field(default_factory=list)
    validated_checkpoint: int | None = None
    candidate_rows: int
    release_gates: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaColdStartV2Calibration(BaseModel):
    checkpoint: int
    personal_weight: float
    interval_80_halfwidth: float | None = None
    development_pitchers: int


class StaminaColdStartV2Result(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    method: str
    development_year: int
    audit_year: int
    target_window: str
    development_rows: int
    audit_rows: int
    development_pitchers: int
    audit_pitchers: int
    prior_pitchers: int
    prior_appearances: int
    calibrations: list[StaminaColdStartV2Calibration] = Field(default_factory=list)
    development_checkpoints: list[StaminaColdStartCheckpoint] = Field(default_factory=list)
    audit_checkpoints: list[StaminaColdStartCheckpoint] = Field(default_factory=list)
    audit_passed_checkpoints: list[int] = Field(default_factory=list)
    formal_release_eligible: bool
    candidate_rows: int
    release_gates: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaColdStartCandidate(BaseModel):
    pitcher: int
    pitcher_name: str
    team: str
    season: int
    stamina_plus: float
    posterior_retention: float
    ci_low: float
    ci_high: float
    reliability: float
    retention_appearances: int
    total_starts: int
    late_pitches: int
    prior_source: str
    status: str
    publication_status: str


class StaminaColdStartAppearance(BaseModel):
    pitcher: int
    pitcher_name: str
    team: str
    game_pk: int
    game_date: str
    season_start_number: int
    retention_start_number: int
    total_pitches: int
    reached_61_80: bool
    retention_eligible: bool
    early_stuff: float | None = None
    early_location: float | None = None
    early_velocity: float | None = None
    game_retention: float | None = None
    raw_retention_delta: float | None = None
    observed_late_stuff: float | None = None
    expected_late_stuff: float | None = None
    velocity_delta: float | None = None
    location_delta: float | None = None
    late_pitches: int | None = None
    observation_weight: float | None = None


class StaminaColdStartPitcherResponse(BaseModel):
    year: int
    publication_status: str
    pitcher_id: int
    pitcher_name: str
    team: str
    candidate: StaminaColdStartCandidate | None = None
    appearances: list[StaminaColdStartAppearance] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaResearchGame(BaseModel):
    game_pk: int
    game_date: str
    total_pitches: int


class StaminaResearchCurve(BaseModel):
    pitcher: int
    pitcher_name: str
    team: str
    game_pk: int
    game_date: str
    appearance_total_pitches: int
    pitch_family: str
    analysis_bucket: str
    order: int
    pitches: int
    reference_pitches: int
    observation_weight: float
    stuff_delta: float | None = None
    velocity_delta: float | None = None
    spin_delta: float | None = None
    movement_drift_inches: float | None = None
    release_point_drift_inches: float | None = None
    extension_delta: float | None = None
    location_delta: float | None = None
    usage_pct: float
    usage_delta_pp: float


class StaminaResearchCurvesResponse(BaseModel):
    year: int
    publication_status: str
    pitcher_id: int
    pitcher_name: str
    team: str
    games: list[StaminaResearchGame] = Field(default_factory=list)
    curves: list[StaminaResearchCurve] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaGameStateScope(BaseModel):
    scope: str
    eligible_games: int
    league_retention: float
    state_sd: float
    median_reliability: float


class StaminaGameStateResult(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    method: str
    reference_year: int
    season: int
    minimum_early_exact_pitches: int
    minimum_overall_late_pitches: int
    minimum_family_late_pitches: int
    minimum_fixed_mix_coverage_pct: float
    interval_method: str
    state_rows: int
    window_rows: int
    eligible_overall_games: int
    pitchers: int
    overall_start_coverage_pct: float
    median_interval_width: float
    pitch_model_rmse: float
    pitch_baseline_rmse: float
    pitch_rmse_improvement_pct: float
    early_stuff_spearman: float | None = None
    early_velocity_spearman: float | None = None
    within_game_split_spearman: float | None = None
    scope_parameters: list[StaminaGameStateScope] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaGameState(BaseModel):
    pitcher: int
    game_pk: int
    game_date: str
    pitcher_name: str
    team: str
    season_start_number: int
    total_pitches: int
    scope: str
    pitches: int
    effective_pitches: float
    minimum_pitches: int
    eligible: bool
    raw_retention: float
    posterior_retention: float | None = None
    stamina_plus: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    reliability: float | None = None
    confidence: str
    rolling_3: float | None = None
    rolling_5: float | None = None
    velocity_delta: float | None = None
    early_stuff: float | None = None
    early_velocity: float | None = None
    sampling_variance: float
    clusters: int
    observed_mix_retention: float | None = None
    fixed_mix_coverage: float | None = None
    early_baseline_reliability: float | None = None


class StaminaGameStateWindow(BaseModel):
    pitcher: int
    game_pk: int
    game_date: str
    pitcher_name: str
    team: str
    scope: str
    analysis_bucket: str
    order: int
    pitches: int
    effective_pitches: float
    retention: float | None = None
    velocity_delta: float | None = None


class StaminaGameStatesResponse(BaseModel):
    year: int
    publication_status: str
    pitcher_id: int
    pitcher_name: str
    team: str
    states: list[StaminaGameState] = Field(default_factory=list)
    windows: list[StaminaGameStateWindow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaSeasonSummaryRow(BaseModel):
    pitcher: int
    pitcher_name: str
    team: str
    scope: str
    total_starts: int
    eligible_games: int
    supported_pitches: int
    effective_games: float
    average_pitches: float
    mean_game_reliability: float
    raw_stamina_plus: float
    unweighted_stamina_plus: float
    season_sampling_variance: float
    qualified: bool
    minimum_games: int
    minimum_pitches: int
    stamina_plus: float
    ci_low: float
    ci_high: float
    reliability: float
    confidence: str
    rank: float | None = None


class StaminaSeasonSummariesResponse(BaseModel):
    year: int
    publication_status: str
    contract_version: str
    rows: list[StaminaSeasonSummaryRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaSeasonSummaryAudit(BaseModel):
    scope: str
    pitchers: int
    qualified_pitchers: int
    minimum_games: int
    minimum_pitches: int
    median_reliability: float
    median_interval_width: float
    weighted_vs_unweighted_spearman: float | None = None


class StaminaSlice12Result(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    season: int
    method: str
    minimum_season_reliability: float
    rows: int
    scope_audits: list[StaminaSeasonSummaryAudit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaExternalValidationGate(BaseModel):
    key: str
    label: str
    threshold: str
    value: Any
    passed: bool


class StaminaExternalSeasonAudit(BaseModel):
    year: int
    qualified_pitchers: int
    stamina_vs_early_stuff_spearman: float | None = None
    stamina_vs_early_velocity_spearman: float | None = None
    stamina_vs_eligible_games_spearman: float | None = None
    stamina_vs_average_pitches_spearman: float | None = None


class StaminaSlice13Result(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    validation_year: int
    test_year: int
    leaderboard_release_eligible: bool
    gates: list[StaminaExternalValidationGate] = Field(default_factory=list)
    season_audits: list[StaminaExternalSeasonAudit] = Field(default_factory=list)
    common_qualified_pitchers: int
    cross_season_stamina_spearman: float | None = None
    cross_season_note: str
    warnings: list[str] = Field(default_factory=list)


class StaminaBiasRepairModelAudit(BaseModel):
    scope: str
    development_pitchers: int
    ridge_alpha: float
    spline_knots: int
    spline_degree: int
    prediction_center: float


class StaminaBiasRepairSeasonAudit(BaseModel):
    year: int
    scope: str
    qualified_pitchers: int
    before_early_stuff_spearman: float | None = None
    after_early_stuff_spearman: float | None = None
    before_early_velocity_spearman: float | None = None
    after_early_velocity_spearman: float | None = None
    median_reliability: float
    median_interval_width: float
    weighted_vs_unweighted_spearman: float | None = None
    spread_retained_ratio: float | None = None


class StaminaSlice13AResult(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    development_year: int
    test_year: int
    leaderboard_release_eligible: bool
    method: str
    model_audits: list[StaminaBiasRepairModelAudit] = Field(default_factory=list)
    season_audits: list[StaminaBiasRepairSeasonAudit] = Field(default_factory=list)
    gates: list[StaminaExternalValidationGate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaLeaderboardRow(BaseModel):
    rank: int
    pitcher_id: int
    name: str
    team: str
    starts: int
    eligible_games: int
    average_pitches: float
    fastball_stamina_plus: float | None = None
    breaking_stamina_plus: float | None = None
    offspeed_stamina_plus: float | None = None
    ci_low: float
    ci_high: float
    reliability: float
    stamina_plus: float
    quality_game_stamina_plus: float | None = None
    physical_stability_plus: float | None = None
    command_retention_plus: float | None = None


class StaminaLeaderboardResponse(BaseModel):
    year: int
    data_as_of: str | None = None
    publication_status: str
    contract_version: str
    correction_version: str
    development_year: int
    test_year: int
    rows: list[StaminaLeaderboardRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaPhysicalSignal(BaseModel):
    key: str
    label: str
    unit: str
    weight: float
    direction: str
    definition: str


class StaminaPhysicalCoverage(BaseModel):
    year: int
    pitches: int
    appearances: int
    pitchers: int
    window_rows: int
    supported_late_pitches: int
    late_pitches: int
    supported_late_pct: float
    signal_coverage_pct: dict[str, float] = Field(default_factory=dict)


class StaminaSlice15Result(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    development_year: int
    covered_years: list[int] = Field(default_factory=list)
    minimum_early_exact_pitches: int
    minimum_late_pitches: int
    minimum_component_coverage_pct: float
    method: str
    signals: list[StaminaPhysicalSignal] = Field(default_factory=list)
    coverage: list[StaminaPhysicalCoverage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaPhysicalPlayer(BaseModel):
    pitcher_id: int
    name: str
    team: str
    appearances: int


class StaminaPhysicalYearAudit(BaseModel):
    year: int
    window_rows: int
    game_rows: int
    eligible_games: int
    pitchers: int
    median_reliability: float
    median_interval_width: float
    split_window_spearman: float | None = None
    velocity_vs_physical_spearman: float | None = None
    score_p05: float | None = None
    score_p50: float | None = None
    score_p95: float | None = None


class StaminaSlice16Result(BaseModel):
    status: str
    publication_status: str
    model_version: str
    contract_version: str
    development_year: int
    scoring_year: int
    method: str
    players: list[StaminaPhysicalPlayer] = Field(default_factory=list)
    year_audits: list[StaminaPhysicalYearAudit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaPhysicalGame(BaseModel):
    pitcher: int
    game_pk: int
    game_date: str
    pitcher_name: str
    team: str
    season_start_number: int
    windows: int
    late_pitches: int
    supported_pitches: int
    component_coverage: float
    velocity_plus: float | None = None
    spin_plus: float | None = None
    movement_plus: float | None = None
    release_point_plus: float | None = None
    extension_plus: float | None = None
    arm_angle_plus: float | None = None
    raw_physical_stability_plus: float
    physical_stability_plus: float
    ci_low: float
    ci_high: float
    reliability: float
    eligible: bool
    confidence: str


class StaminaPhysicalWindow(BaseModel):
    pitcher: int
    game_pk: int
    game_date: str
    pitcher_name: str
    team: str
    analysis_bucket: str
    order: int
    total_pitches: int
    supported_pitches: int
    support_pct: float
    component_coverage: float
    velocity_plus: float | None = None
    spin_plus: float | None = None
    movement_plus: float | None = None
    release_point_plus: float | None = None
    extension_plus: float | None = None
    arm_angle_plus: float | None = None
    raw_physical_stability_plus: float
    physical_stability_plus: float
    ci_low: float
    ci_high: float
    reliability: float
    eligible: bool


class StaminaPhysicalStabilityResponse(BaseModel):
    year: int
    publication_status: str
    pitcher_id: int
    pitcher_name: str
    team: str
    games: list[StaminaPhysicalGame] = Field(default_factory=list)
    windows: list[StaminaPhysicalWindow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaCommandYearAudit(BaseModel):
    year: int
    pitch_rows: int
    window_rows: int
    game_rows: int
    eligible_overall_games: int
    pitchers: int
    pitch_model_rmse: float
    pitch_baseline_rmse: float
    pitch_rmse_improvement_pct: float
    early_location_spearman: float | None = None
    fixed_vs_observed_mix_spearman: float | None = None
    split_window_spearman: float | None = None
    median_reliability: float
    median_interval_width: float
    score_p05: float | None = None
    score_p50: float | None = None
    score_p95: float | None = None


class StaminaSlice17Result(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    model_version: str
    development_year: int
    scoring_year: int
    covered_years: list[int] = Field(default_factory=list)
    minimum_early_exact_pitches: int
    minimum_window_pitches: int
    minimum_game_pitches: int
    minimum_fixed_mix_coverage_pct: float
    method: str
    players: list[StaminaPhysicalPlayer] = Field(default_factory=list)
    year_audits: list[StaminaCommandYearAudit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaSlice18Result(BaseModel):
    status: str
    publication_status: str
    validation_version: str
    train_year: int
    test_year: int
    predictor_window: str
    target_window: str
    method: str
    train_rows: int
    test_rows: int
    train_pair_coverage_pct: float
    test_pair_coverage_pct: float
    models: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    rmse_improvement_pct: float
    rmse_improvement_over_velocity_pct: float
    pairwise_spearman: dict[str, float | None] = Field(default_factory=dict)
    challenger_standardized_coefficients: dict[str, float] = Field(default_factory=dict)
    gates: list[StaminaExternalValidationGate] = Field(default_factory=list)
    composite_release_eligible: bool
    decision: str
    warnings: list[str] = Field(default_factory=list)


class StaminaProductRepresentative(BaseModel):
    case: str
    pitcher_id: int
    name: str
    team: str
    quality_games: int
    physical_games: int
    command_games: int
    quality_stamina_plus: float
    physical_stability_plus: float
    command_retention_plus: float
    quality_reliability: float
    physical_reliability: float
    command_reliability: float


class StaminaSlice19Result(BaseModel):
    status: str
    publication_status: str
    contract_version: str
    year: int
    decision: str
    composite_release_eligible: bool
    method: str
    qualified_three_signal_pitchers: int
    representative_pitchers: list[StaminaProductRepresentative] = Field(default_factory=list)
    product_rules: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaCommandGame(BaseModel):
    pitcher: int
    game_pk: int
    game_date: str
    pitcher_name: str
    team: str
    year: int
    scope: str
    windows: int
    late_pitches: int
    raw_retention: float
    raw_command_retention_plus: float
    command_retention_plus: float
    ci_low: float
    ci_high: float
    reliability: float
    fixed_mix_coverage: float
    early_location: float
    early_baseline_reliability: float
    eligible: bool
    confidence: str
    season_start_number: int


class StaminaCommandWindow(BaseModel):
    pitcher: int
    game_pk: int
    game_date: str
    order: int
    analysis_bucket: str
    pitcher_name: str
    team: str
    scope: str
    pitches: int
    retention: float
    observed_mix_retention: float | None = None
    fixed_mix_coverage: float | None = None
    observed_location_change: float
    early_location: float
    early_baseline_reliability: float
    year: int
    sampling_variance: float
    raw_command_retention_plus: float
    reliability: float
    command_retention_plus: float
    ci_low: float
    ci_high: float
    eligible: bool


class StaminaCommandRetentionResponse(BaseModel):
    year: int
    publication_status: str
    pitcher_id: int
    pitcher_name: str
    team: str
    games: list[StaminaCommandGame] = Field(default_factory=list)
    windows: list[StaminaCommandWindow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaminaOverviewResponse(BaseModel):
    year: int
    data_as_of: str | None = None
    generated_at: str
    dataset_status: str
    model_version: str
    dataset_rows: int
    appearances: int
    pitchers: int
    dual_role_pitchers: int
    cleaning: list[StaminaCleaningStep] = Field(default_factory=list)
    roles: list[StaminaRoleSummary] = Field(default_factory=list)
    coverage: list[StaminaCoverageRow] = Field(default_factory=list)
    pitch_buckets: list[StaminaPitchBucket] = Field(default_factory=list)
    feature_audit: list[StaminaFeatureAudit] = Field(default_factory=list)
    hypotheses: list[StaminaHypothesis] = Field(default_factory=list)
    arm_angle_audit: StaminaArmAngleAudit
    slice1: StaminaSlice1Result
    slice2: StaminaSlice2Result
    slice3: StaminaSlice3Result
    slice4: StaminaSlice4Result
    slice5: StaminaSlice5Result | None = None
    slice6: StaminaSlice6Result | None = None
    slice7: StaminaSlice7Result | None = None
    slice8: StaminaSlice8Result | None = None
    slice9: StaminaSlice9Result | None = None
    slice10: StaminaSlice10Result | None = None
    slice11: StaminaSlice11Result | None = None
    slice11_game_state: StaminaGameStateResult | None = None
    slice12: StaminaSlice12Result | None = None
    slice13: StaminaSlice13Result | None = None
    slice13a: StaminaSlice13AResult | None = None
    slice15: StaminaSlice15Result | None = None
    slice16: StaminaSlice16Result | None = None
    slice17: StaminaSlice17Result | None = None
    slice18: StaminaSlice18Result | None = None
    slice19: StaminaSlice19Result | None = None
    warnings: list[str] = Field(default_factory=list)
