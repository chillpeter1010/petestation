export type SignalState = 'gray' | 'green' | 'yellow' | 'red'
export type GateState = 'unknown' | 'pass' | 'fail'
export type SignalId = 'A' | 'B' | 'C' | 'D'
export interface SignalLight {
  id: SignalId
  title: string
  state: SignalState
  calibrated: boolean
  supportKnown: boolean
  reason: string
  evidence: string[]
}
export interface SignalGates {
  value: GateState
  legal: GateState
  availability: GateState
  statePersistence: GateState
  validation?: GateState
}
export interface SignalCase {
  id: string
  label: string
  gamePk: number
  decisionId: string
  pitcherName: string
  role: string
  inning: number
  half: string
  pitches: number
  observationMature: boolean
  lights: SignalLight[]
  gates: SignalGates
  valueNote: string
  matchupNote: string
  li: number | null
}
export interface SignalLightsSnapshot {
  version: string
  updatedAt: string
  mode: 'observed'
  cases: SignalCase[]
  counts: { cases: number; belowObservationMinimum: number; matureObservation: number }
  scoreStatus: string
  recommendationAllowed: false
  calibrationSummary?: {
    blocks: number
    actorRows: number
    outcomeModels: { role: string; n: number; selected: string; referenceLL: number; variants: { variant: string; LL: number; passed: boolean }[] }[]
    normal2024: { role: string; group: string; n: number; smooth_brier: number; raw_brier: number; constant_brier: number; predictive_gate: boolean }[]
    replay: {
      flow: { raw_boundaries: number; modeled: number; full_four: number; state_episodes: number; observed_recovery: number; nominal_research_alerts: number; official_events: number; operational_recommendations: number }
      roles: { role: string; modeled: number; full_four: number; state_episodes: number; research_alerts: number }[]
    }
  }
}

export const SIGNAL_STATES: { id: SignalState; label: string }[] = [
  { id: 'gray', label: '灰 · 證據不足' }, { id: 'green', label: '綠 · 未見異常' },
  { id: 'yellow', label: '黃 · 尾端偏離' }, { id: 'red', label: '紅 · 明顯偏離' }
]
export const SIGNAL_BANDS = [
  { color: 'green', label: '未見異常', range: '0', minimum: 0, maximum: 0 },
  { color: 'lime', label: '留意變化', range: '1–2', minimum: 1, maximum: 2 },
  { color: 'yellow', label: '注意狀態', range: '3–4', minimum: 3, maximum: 4 },
  { color: 'orange', label: '多項警戒', range: '5–6', minimum: 5, maximum: 6 },
  { color: 'red', label: '高度異常', range: '7–8', minimum: 7, maximum: 8 }
] as const

export function assessSignalLights(lights: SignalLight[], gates: SignalGates, mode: 'observed' | 'demo') {
  if (lights.length !== 4 || new Set(lights.map(light => light.id)).size !== 4 || lights.some(light => !['A', 'B', 'C', 'D'].includes(light.id))) {
    throw new Error('Exactly one A/B/C/D signal is required')
  }
  if (lights.some(light => !SIGNAL_STATES.some(item => item.id === light.state))) throw new Error('Unknown signal state')
  const normalized = lights.map(light => ({
    ...light,
    state: !light.supportKnown || (mode === 'observed' && !light.calibrated) ? 'gray' as const : light.state
  }))
  const weights = { green: 0, yellow: 1, red: 2 }
  const known = normalized.filter(light => light.state !== 'gray')
  const knownScore = known.reduce((sum, light) => sum + weights[light.state as keyof typeof weights], 0)
  const unknown = 4 - known.length
  // Missing groups are never assigned zero or normalized out of the denominator.
  const score = unknown === 0 ? knownScore : null
  const band = score === null ? null : SIGNAL_BANDS.find(item => score >= item.minimum && score <= item.maximum)!
  const red = normalized.filter(light => light.state === 'red')
  const coreRed = red.some(light => light.id === 'A' || light.id === 'B')
  const stateCondition = unknown === 0 && red.length >= 2 && coreRed && gates.statePersistence === 'pass'
  const blockers: string[] = []
  if (unknown) blockers.push(`${unknown}個原因群尚不能判讀`)
  if (red.length < 2 || !coreRed) blockers.push('尚無兩群異常且包含球質或位置證據')
  if (gates.statePersistence !== 'pass') blockers.push('原因訊號的持續性尚未確認')
  if (gates.value !== 'pass') blockers.push(gates.value === 'fail' ? '替代收益未通過' : '替代收益未知')
  if (gates.legal !== 'pass') blockers.push(gates.legal === 'fail' ? '名義合法條件未通過' : '合法條件未知')
  if (gates.availability !== 'pass') blockers.push(gates.availability === 'fail' ? '替代方案不可用' : '實際可用性未確認')
  if (gates.validation !== 'pass') blockers.push(gates.validation === 'fail' ? '多燈組合尚未取得預測支持' : '多燈組合的預測支持未知')
  const researchCandidate = stateCondition && gates.value === 'pass' && gates.legal === 'pass' && gates.availability === 'pass' && gates.validation === 'pass'
  return {
    normalized, score, knownScore, scoreRange: [knownScore, knownScore + unknown * 2], known: known.length,
    color: band?.color ?? 'gray', label: band?.label ?? '觀察中 · 證據未齊', redCount: red.length,
    stateCondition, researchCandidate, blockers,
    // This display prototype can never enable an operational recommendation.
    recommendationAllowed: false as const
  }
}
