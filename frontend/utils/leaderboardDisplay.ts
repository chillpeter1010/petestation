import { performanceColorStyle } from '~/utils/performanceColor'

export type LeaderboardDisplayMode = 'actual' | 'percentile'
export type LeaderboardMetricDirection = 'higher' | 'lower'

export type LeaderboardMetric<Row> = {
  value: (row: Row) => number | null | undefined
  direction: LeaderboardMetricDirection
}

export function buildLeaderboardPercentiles<Row>(
  rows: Row[],
  identity: (row: Row) => string,
  metrics: Record<string, LeaderboardMetric<Row>>
) {
  const result = new Map<string, Record<string, number>>()
  for (const [label, metric] of Object.entries(metrics)) {
    const entries = rows
      .map(row => ({ id: identity(row), value: metric.value(row) }))
      .filter((entry): entry is { id: string; value: number } => typeof entry.value === 'number' && Number.isFinite(entry.value))
      .sort((left, right) => left.value - right.value)
    let index = 0
    while (index < entries.length) {
      let end = index + 1
      while (end < entries.length && entries[end].value === entries[index].value) end += 1
      const raw = entries.length === 1 ? 50 : (((index + end - 1) / 2) / (entries.length - 1)) * 100
      const percentile = metric.direction === 'lower' ? 100 - raw : raw
      for (let position = index; position < end; position += 1) {
        const current = result.get(entries[position].id) || {}
        current[label] = percentile
        result.set(entries[position].id, current)
      }
      index = end
    }
  }
  return result
}

export function leaderboardMetricValue(
  mode: LeaderboardDisplayMode,
  percentiles: Record<string, number>,
  label: string,
  actual: string | number | null | undefined
) {
  if (mode !== 'percentile') return actual ?? '—'
  const percentile = percentiles[label]
  return Number.isFinite(percentile) ? Math.round(percentile) : '—'
}

export function leaderboardHeatStyle(percentile: number | null | undefined, enabled: boolean) {
  return enabled && typeof percentile === 'number' && Number.isFinite(percentile)
    ? performanceColorStyle((percentile - 50) / 50)
    : undefined
}
