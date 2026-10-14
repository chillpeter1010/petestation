from typing import Any

from pydantic import BaseModel, Field


class PerformanceStateOverviewResponse(BaseModel):
    contract_version: str
    warehouse_version: str
    baseline_version: str
    state_model_version: str
    status: str
    generated_at: str
    development_year: int
    test_year: int
    data_as_of: dict[str, str] = Field(default_factory=dict)
    source_modified_at: dict[str, int] = Field(default_factory=dict)
    slice0: dict[str, Any] = Field(default_factory=dict)
    slice1: dict[str, Any] = Field(default_factory=dict)
    slice2: dict[str, Any] = Field(default_factory=dict)
    slice3: dict[str, Any] = Field(default_factory=dict)
    slice3a: dict[str, Any] = Field(default_factory=dict)
    slice4: dict[str, Any] = Field(default_factory=dict)
    slice5: dict[str, Any] = Field(default_factory=dict)
    slice6: dict[str, Any] = Field(default_factory=dict)
    slice7: dict[str, Any] = Field(default_factory=dict)
    slice8: dict[str, Any] = Field(default_factory=dict)
    slice9: dict[str, Any] = Field(default_factory=dict)
    slice11: dict[str, Any] = Field(default_factory=dict)
    advanced_model_version: str | None = None
    advanced_dataset_status: str | None = None
    tail_model_version: str | None = None
    tail_dataset_status: str | None = None
    forecast_model_version: str | None = None
    forecast_dataset_status: str | None = None
    shadow_model_version: str | None = None
    shadow_dataset_status: str | None = None
    dataset_status: str
    warnings: list[str] = Field(default_factory=list)


class PitcherPerformanceStateRow(BaseModel):
    pitcher_id: int
    pitcher_name: str
    team: str | None = None
    role: str
    game_pk: int
    game_date: str
    pitches: int
    calendar_days_since_prior: float | None = None
    plate_appearances: float | None = None
    mean_stuff_plus: float | None = None
    mean_location_plus: float | None = None
    re24: float | None = None
    re24_per_pa: float | None = None
    wpa: float | None = None
    wpa_li: float | None = None
    wpa_li_per_pa: float | None = None
    process_score: float | None = None
    result_score: float | None = None
    process_collapse: bool
    result_collapse: bool
    combined_collapse: bool
    return_to_baseline: bool
    strong_rebound: bool
    excess_recovery: float | None = None
    stuff_state_forecast: float | None = None
    stuff_state_forecast_sd: float | None = None
    stuff_state_filtered: float | None = None
    stuff_state_filtered_sd: float | None = None
    stuff_state_innovation: float | None = None
    stuff_state_standardized_innovation: float | None = None
    command_state_forecast: float | None = None
    command_state_forecast_sd: float | None = None
    command_state_filtered: float | None = None
    command_state_filtered_sd: float | None = None
    command_state_innovation: float | None = None
    command_state_standardized_innovation: float | None = None
    result_state_forecast: float | None = None
    result_state_forecast_sd: float | None = None
    result_state_filtered: float | None = None
    result_state_filtered_sd: float | None = None
    result_state_innovation: float | None = None
    result_state_standardized_innovation: float | None = None
    regime_filtered_label: str | None = None
    regime_prior_stable: float | None = None
    regime_prior_declining: float | None = None
    regime_prior_collapse: float | None = None
    regime_prior_recovering: float | None = None
    regime_prior_high_volatility: float | None = None
    regime_filtered_stable: float | None = None
    regime_filtered_declining: float | None = None
    regime_filtered_collapse: float | None = None
    regime_filtered_recovering: float | None = None
    regime_filtered_high_volatility: float | None = None
    ewma_variance_forecast: float | None = None
    gas_variance_forecast: float | None = None
    gas_har_variance_forecast: float | None = None
    gjr_variance_forecast: float | None = None
    evt_extreme_probability: float | None = None
    evt_expected_loss_severity: float | None = None
    evt_tail_supported: bool | None = None
    caviar_var95: float | None = None
    extreme_innovation: bool | None = None
    evt_alert: bool | None = None
    caviar_alert: bool | None = None
    process_collapse_probability: float | None = None
    process_collapse_alert: bool | None = None
    result_collapse_probability: float | None = None
    result_collapse_alert: bool | None = None
    return_to_baseline_probability: float | None = None
    return_to_baseline_alert: bool | None = None
    strong_rebound_probability: float | None = None
    strong_rebound_alert: bool | None = None


class PitcherPerformanceStatesResponse(BaseModel):
    year: int
    pitcher_id: int
    pitcher_name: str
    roles: list[str] = Field(default_factory=list)
    model_version: str
    status: str
    rows: list[PitcherPerformanceStateRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PerformanceStateLeaderboardRow(BaseModel):
    rank: int
    pitcher_id: int
    pitcher_name: str
    team: str | None = None
    role: str
    appearances: int
    eligible_forecasts: int
    latest_game_date: str
    latest_probability: float
    season_mean_probability: float
    actual_events: int
    actual_rate: float
    latest_actual: bool


class PerformanceStateLeaderboardResponse(BaseModel):
    year: int
    role: str
    target: str
    target_label: str
    model_version: str
    status: str
    data_as_of: str | None = None
    evaluation_status: str
    selected_primary_layer: str
    model: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    rows: list[PerformanceStateLeaderboardRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PerformanceStateShadowResponse(BaseModel):
    version: str
    status: str
    generated_at: str
    evaluation_year: int
    source_forecast_model_version: str
    observation_mode: str
    ledger_rows: int
    appended_rows: int
    probability_conflicts_preserved: int
    prospective_rows: int
    monitoring: dict[str, Any] = Field(default_factory=dict)
    integration_gate: dict[str, Any] = Field(default_factory=dict)
    dataset_status: str
    warnings: list[str] = Field(default_factory=list)


class PerformanceStateV2LabRow(BaseModel):
    rank: int
    pitcher_id: int
    pitcher_name: str
    team: str | None = None
    role: str
    appearances: int
    eligible_forecasts: int
    latest_game_date: str
    latest_probability: float
    season_mean_probability: float
    actual_events: int
    actual_rate: float
    latest_actual: bool
    shadow_slice18_latest_probability: float | None = None
    shadow_slice18_season_mean_probability: float | None = None
    shadow_slice19_latest_probability: float | None = None
    shadow_slice19_season_mean_probability: float | None = None
    shadow_slice18_delta: float | None = None
    shadow_slice19_delta: float | None = None


class PerformanceStateV2LabResponse(BaseModel):
    year: int
    role: str
    target: str
    target_label: str
    model_version: str
    status: str
    data_as_of: str | None = None
    evaluation_status: str
    selected_primary_layer: str
    rows: list[PerformanceStateV2LabRow] = Field(default_factory=list)
    primary_source: dict[str, Any] = Field(default_factory=dict)
    shadow: dict[str, Any] = Field(default_factory=dict)
    subgroup_monitor: dict[str, Any] = Field(default_factory=dict)
    freeze_decision: dict[str, Any] = Field(default_factory=dict)
    strict_replay: dict[str, Any] = Field(default_factory=dict)
    fallback: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PerformanceStateV2AuditResponse(BaseModel):
    version: str
    status: str
    generated_at: str
    source_modified_at: dict[str, int] = Field(default_factory=dict)
    slice11a: dict[str, Any] = Field(default_factory=dict)
    slice12: dict[str, Any] = Field(default_factory=dict)
    slice13: dict[str, Any] = Field(default_factory=dict)
    dataset_status: str


class PerformanceStateV2Slice14AuditResponse(BaseModel):
    version: str
    status: str
    generated_at: str
    source_modified_at: dict[str, int] = Field(default_factory=dict)
    slice14a: dict[str, Any] = Field(default_factory=dict)
    slice14b: dict[str, Any] = Field(default_factory=dict)
    prediction_rows: int
    dataset_status: str


class PerformanceStateV2Slice15AuditResponse(BaseModel):
    version: str
    status: str
    generated_at: str
    evaluation_status: str
    source_year: int
    source: dict[str, Any] = Field(default_factory=dict)
    frozen_model: dict[str, Any] = Field(default_factory=dict)
    prospective: dict[str, Any] = Field(default_factory=dict)
    integration_gate: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    dataset_status: str


class PerformanceStateV2Slice16AuditResponse(BaseModel):
    version: str
    status: str
    generated_at: str
    development_years: list[int] = Field(default_factory=list)
    selection_year: int
    diagnostic_year: int
    prospective_year: int
    roles: dict[str, Any] = Field(default_factory=dict)
    prediction_rows: int
    gate_policy: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PerformanceStateV2Slice17AuditResponse(BaseModel):
    version: str
    status: str
    generated_at: str
    development_years: list[int] = Field(default_factory=list)
    selection_year: int
    diagnostic_year: int
    prospective_year: int
    roles: dict[str, Any] = Field(default_factory=dict)
    prediction_rows: int
    policy: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PerformanceStateV2Slice18To20AuditResponse(BaseModel):
    version: str
    status: str
    generated_at: str
    development_years: list[int] = Field(default_factory=list)
    selection_year: int
    diagnostic_year: int
    prospective_year: int
    slice18_partial_pooling: dict[str, Any] = Field(default_factory=dict)
    slice19_workload_bias_sensitivity: dict[str, Any] = Field(default_factory=dict)
    slice20_subgroup_calibration: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PerformanceStateV2Slice21To22AuditResponse(BaseModel):
    version: str
    status: str
    generated_at: str
    development_years: list[int] = Field(default_factory=list)
    folds: list[dict[str, Any]] = Field(default_factory=list)
    diagnostic_year: int
    prospective_year: int
    slice21_rolling_origin: dict[str, Any] = Field(default_factory=dict)
    slice22_freeze_decision: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PerformanceStateV2StrictReplayResponse(BaseModel):
    version: str
    status: str
    generated_at: str
    train_years: list[int] = Field(default_factory=list)
    calibration_year: int
    test_year: int
    layer_map: dict[str, Any] = Field(default_factory=dict)
    calibration_policy: str
    threshold_policy: str
    no_2026_model_selection: bool
    model_fingerprint: str
    roles: dict[str, Any] = Field(default_factory=dict)
    prediction_rows: int
    integration_gate: str
    warnings: list[str] = Field(default_factory=list)
