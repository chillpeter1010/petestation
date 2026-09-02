<template>
  <section class="trend-card">
    <header>
      <h2>{{ activeLabel }}</h2>
      <div class="metric-switch" aria-label="Trend metric">
        <button v-for="item in metrics" :key="item.key" type="button" :class="{ active: metric === item.key }" @click="metric = item.key">{{ item.label }}</button>
      </div>
    </header>

    <div v-if="chartPoints.length" class="chart-wrap">
      <svg viewBox="0 0 1000 420" preserveAspectRatio="xMidYMid meet" role="img" :aria-label="`${activeLabel} by game`">
        <g class="grid-lines">
          <line v-for="tick in yTicks" :key="tick.value" x1="70" x2="970" :y1="tick.y" :y2="tick.y" />
        </g>
        <g class="axis-labels">
          <text v-for="tick in yTicks" :key="`label-${tick.value}`" x="58" :y="tick.y + 5" text-anchor="end">{{ formatAxis(tick.value) }}</text>
          <text x="70" y="402">{{ firstDate }}</text>
          <text x="970" y="402" text-anchor="end">{{ lastDate }}</text>
        </g>
        <polygon class="area" :points="areaPoints" />
        <line v-if="metric === 'cumulative_wpa'" class="zero-line" x1="70" x2="970" :y1="zeroY" :y2="zeroY" />
        <polyline class="trend-line" :points="polylinePoints" />
        <circle v-for="point in visibleDots" :key="point.key" :cx="point.x" :cy="point.y" r="4">
          <title>{{ point.date }} · {{ formatAxis(point.value) }}</title>
        </circle>
      </svg>
    </div>
    <p v-else class="empty">No game-level data available.</p>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{ rows: Record<string, unknown>[] }>()
const metrics = [
  { key: 'cumulative_wpa', label: 'Cumulative WPA' },
  { key: 'rolling_woba', label: '5-day wOBA' }
] as const
const metric = ref<(typeof metrics)[number]['key']>('cumulative_wpa')

const activeLabel = computed(() => metrics.find(item => item.key === metric.value)?.label || '')
const chronologicalRows = computed(() => props.rows.slice().sort((left, right) => String(left.Date).localeCompare(String(right.Date))))
const values = computed(() => {
  if (metric.value === 'cumulative_wpa') {
    let cumulative = 0
    return chronologicalRows.value.map((row) => {
      const value = nullableNumeric(row['Game WPA'])
      if (value === null) return null
      cumulative += value
      return cumulative
    })
  }
  return chronologicalRows.value.map((row, index, rows) => {
    const currentDate = parseDate(row.Date)
    if (!currentDate) return null
    const windowStart = new Date(currentDate)
    windowStart.setUTCDate(windowStart.getUTCDate() - 4)
    const sample = rows.slice(0, index + 1).filter((item) => {
      const itemDate = parseDate(item.Date)
      return itemDate && itemDate >= windowStart && itemDate <= currentDate
    })
    const weighted = sample.reduce((sum, item) => sum + numeric(item.wOBA) * numeric(item.PA), 0)
    const plateAppearances = sample.reduce((sum, item) => sum + numeric(item.PA), 0)
    return plateAppearances > 0 ? weighted / plateAppearances : null
  })
})
const finiteValues = computed(() => values.value.filter((value): value is number => value !== null && Number.isFinite(value)))
const bounds = computed(() => {
  if (!finiteValues.value.length) return { min: 0, max: 1 }
  const min = Math.min(...finiteValues.value)
  const max = Math.max(...finiteValues.value)
  if (metric.value === 'rolling_woba') return { min: Math.max(0, min - 0.025), max: Math.max(0.45, max + 0.025) }
  const padding = Math.max((max - min) * 0.12, 0.015)
  return { min: Math.min(0, min - padding), max: Math.max(0, max + padding) }
})
const chartPoints = computed(() => {
  const visibleValues = values.value.flatMap((value, index) => {
    if (value === null || !Number.isFinite(value)) return []
    return [{ key: `${index}-${value}`, value, date: String(chronologicalRows.value[index]?.Date || '') }]
  })
  const count = Math.max(visibleValues.length - 1, 1)
  const range = bounds.value.max - bounds.value.min || 1
  return visibleValues.map((point, index) => ({
    ...point,
    x: 70 + (index / count) * 900,
    y: 365 - ((point.value - bounds.value.min) / range) * 300,
  }))
})
const polylinePoints = computed(() => chartPoints.value.map(point => `${point.x},${point.y}`).join(' '))
const areaPoints = computed(() => {
  const points = chartPoints.value
  if (!points.length) return ''
  const baseline = metric.value === 'cumulative_wpa' ? zeroY.value : 365
  return `${points[0].x},${baseline} ${polylinePoints.value} ${points.at(-1)!.x},${baseline}`
})
const zeroY = computed(() => {
  const range = bounds.value.max - bounds.value.min || 1
  return 365 - ((0 - bounds.value.min) / range) * 300
})
const visibleDots = computed(() => {
  const step = Math.max(1, Math.ceil(chartPoints.value.length / 24))
  return chartPoints.value.filter((_, index) => index % step === 0 || index === chartPoints.value.length - 1)
})
const yTicks = computed(() => [0, 0.5, 1].map(ratio => ({ value: bounds.value.max - (bounds.value.max - bounds.value.min) * ratio, y: 65 + 300 * ratio })))
const firstDate = computed(() => shortDate(chartPoints.value[0]?.date || ''))
const lastDate = computed(() => shortDate(chartPoints.value.at(-1)?.date || ''))

function numeric(value: unknown) { const number = Number(value); return Number.isFinite(number) ? number : 0 }
function nullableNumeric(value: unknown) { if (value === null || value === undefined || value === '-') return null; const number = Number(value); return Number.isFinite(number) ? number : null }
function parseDate(value: unknown) { const date = new Date(`${String(value || '')}T00:00:00Z`); return Number.isNaN(date.getTime()) ? null : date }
function shortDate(value: string) { const parts = value.split('-'); return parts.length === 3 ? `${parts[1]}/${parts[2]}` : value }
function formatAxis(value: number) { return metric.value === 'rolling_woba' ? value.toFixed(3) : `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%` }
</script>

<style scoped>
.trend-card { display: flex; min-width: 0; overflow: hidden; flex-direction: column; border: 1px solid var(--color-border); border-radius: 0; background: var(--color-surface); box-shadow: var(--shadow-sm); }
.trend-card > header { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 20px 22px; border-bottom: 1px solid var(--color-border); }
h2 { margin: 0; color: var(--color-foreground); font-size: 28px; }
.metric-switch { display: flex; gap: 5px; border-radius: 0; padding: 5px; background: var(--color-muted); }
.metric-switch button { min-height: 44px; border: 0; border-radius: 0; padding: 8px 15px; color: var(--color-muted-text); background: transparent; cursor: pointer; font-size: 16px; font-weight: 800; }
.metric-switch button.active { color: #111; background: var(--color-primary); }
.chart-wrap { min-height: 320px; overflow-x: auto; flex: 1; padding: 14px 18px 4px; }
svg { display: block; width: 100%; min-width: 0; height: 100%; overflow: hidden; }
.grid-lines line { stroke: var(--color-border); stroke-width: 1.2; vector-effect: non-scaling-stroke; }
.axis-labels text { fill: var(--color-muted-text); font: 600 15px "Fira Code", monospace; }
.area { fill: rgba(255, 153, 0, .1); }
.trend-line { fill: none; stroke: var(--color-primary); stroke-width: 3.5; stroke-linejoin: round; stroke-linecap: round; vector-effect: non-scaling-stroke; }
.zero-line { stroke: color-mix(in srgb, var(--color-muted-text) 68%, transparent); stroke-width: 1.2; stroke-dasharray: 6 6; vector-effect: non-scaling-stroke; }
circle { fill: var(--color-primary); stroke: var(--color-surface); stroke-width: 2; vector-effect: non-scaling-stroke; }
.empty { margin: 0; padding: 50px 22px; color: var(--color-muted-text); font-size: 17px; }
@media (max-width: 700px) { .trend-card > header { align-items: flex-start; flex-direction: column; } .metric-switch { width: 100%; overflow-x: auto; } .metric-switch button { flex: 1 0 auto; } .chart-wrap { height: 430px; padding-inline: 4px; } }
</style>
