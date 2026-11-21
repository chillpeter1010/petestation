export interface DecisionActionValue {
  decision_id: string
  game_pk: number
  inning: number
  half: string
  role: string
  outgoing_pitcher_id: number
  observed_action: string
  research_pa_li: number | null
  wpa_continue: number
  wpa_pool: number
  wpa_delta: number
  wpa_mc95_low: number
  wpa_mc95_high: number
  wpa_bootstrap80_low: number
  wpa_bootstrap80_high: number
  re24_continue: number
  re24_pool: number
  re24_delta: number
  simulation_supported: boolean
  research_direction: string
  recommendation_allowed: boolean
}

export interface DecisionTimelinePoint {
  decisionId: string
  atBat: number
  inning: number
  half: string
  phase: string
  x: number
  homeWe: number | null
  homeWpa: number | null
  outs: number | null
  bases: number | null
  homeScore: number
  awayScore: number
  pitcherId: number | null
  pitcherName: string
  batterName: string
  description: string
}

export interface DecisionTimelineGame {
  gamePk: number
  year: number
  date: string
  home: string
  away: string
  points: DecisionTimelinePoint[]
  actualChanges: { eventId: string; at: string | null; x: number; incomingId: number; outgoingId: number | null; description: string }[]
  researchPoints: DecisionActionValue[]
  playerNames: Record<string, string | undefined>
  exploratory?: boolean
  shadowWarnings?: { decisionId: string; x: number; risk: number; threshold: number; role: string; match: string; targetObserved: boolean }[]
  scenarios?: DecisionExploratoryValue[]
}

export interface DecisionExploratoryValue {
  decision_id: string
  pa_supported: boolean
  half_supported: boolean
  pool_n: number
  pa_wpa_delta: number
  pa_re24_delta: number
  half_wpa_delta: number
  half_re24_delta: number
  half_wpa_mc95_low: number
  half_wpa_mc95_high: number
}
