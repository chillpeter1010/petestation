import type { SwingTimingLeaderboardRow } from '../types/api'

export function timingMetricValue(row: SwingTimingLeaderboardRow, key: string): number | null {
  const value = row.axis_metrics?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function timingRegressionPoints(rows: SwingTimingLeaderboardRow[], xKey: string, yKey: string) {
  return rows.flatMap(row => {
    const x = timingMetricValue(row, xKey), y = timingMetricValue(row, yKey)
    return x === null || y === null ? [] : [{ row, x, y }]
  })
}

export function timingRegressionDomain(values: number[]): [number, number] {
  if (!values.length) return [0, 1]
  const lo = Math.min(...values), hi = Math.max(...values)
  const pad = Math.max(hi - lo, Math.abs(lo) * .05, .1) * .1
  return [lo - pad, hi + pad]
}
