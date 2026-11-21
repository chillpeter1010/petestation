export interface DecisionAlertResearch {
  version: string
  flow: {
    games: number
    raw_boundaries: number
    prepared_boundaries: number
    modeled: number
    simulation_supported: number
    qualifying_points: number
    persistent_points: number
    independent_alerts: number
    official_changes: number
    official_modeled_exact: number
    official_modeled_window: number
    same_boundary: number
    advance_window: number
    matched_alerts: number
    unmatched_alerts: number
    unmatched_events: number
    operational_recommendations: number
  }
  rules: {
    minimum_wpa_gain: number
    maximum_unsupported_mass: number
    persistence_boundaries: number
    cooldown_defensive_pa: number
    advance_defensive_pa: number
    advance_seconds: number
  }
  rule_review: {
    modeled_exact_boundaries: number
    exact_qualified_points: number
    exact_qualified_persistent_points: number
    events_with_qualified_point_in_original_window: number
    events_with_persistent_point_in_original_window: number
    early_alerts_innings_1_to_3: number
    median_lead_pa: number | null
    persistent_window_points: { event_id: string; decision_id: string; suppression: string }[]
  }
  games: {
    game_pk: number
    date: string
    home: string
    away: string
    boundaries: number
    modeled: number
    supported: number
    qualifying: number
    alerts: number
    official_changes: number
    same_boundary: number
    advance: number
    unmatched_alerts: number
  }[]
  roles: { role: string; modeled: number; qualifying: number; alerts: number; same_boundary: number; advance: number }[]
  alerts: {
    decision_id: string
    game_pk: number
    inning: number
    half: string
    role: string
    pitcher_name: string
    wpa_delta: number
    mc95: number[]
    bootstrap80: number[]
    re24_delta: number
    match_reason: string
    event_id: string | null
    lead_pa: number | null
    lead_seconds: number | null
  }[]
  point_reasons: Record<string, number>
  alert_reasons: Record<string, number>
  unmatched_alert_reasons: Record<string, number>
  event_reasons: Record<string, number>
}
