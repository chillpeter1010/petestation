<template>
  <section class="trend-card">
    <header>
      <div><span>Recent form</span><h2>Game-by-game trend</h2></div>
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
  { key: 'rolling_avg', label: '15-game AVG' },
  { key: 'max_ev', label: 'Max EV' },
  { key: 'home_runs', label: 'Home runs' }
] as const
const metric = ref<(typeof metrics)[number]['key']>('rolling_avg')

const activeLabel = computed(() => metrics.find(item => item.key === metric.value)?.label || '')
const chronologicalRows = computed(() => props.rows.slice().reverse())
const values = computed(() => chronologicalRows.value.map((row, index, rows) => {
  if (metric.value === 'max_ev') return nullableNumeric(row['Max EV'])
  if (metric.value === 'home_runs') return nullableNumeric(row.HR)
  if (index < 14) return null
  const sample = rows.slice(index - 14, index + 1)
  const atBats = sample.reduce((sum, item) => sum + numeric(item.AB), 0)
  const hits = sample.reduce((sum, item) => sum + numeric(item.H), 0)
  return atBats > 0 ? hits / atBats : null
}))
const finiteValues = computed(() => values.value.filter((value): value is number => value !== null && Number.isFinite(value)))
const bounds = computed(() => {
  if (!finiteValues.value.length) return { min: 0, max: 1 }
  if (metric.value === 'rolling_avg') return { min: 0, max: Math.max(0.4, Math.max(...finiteValues.value) * 1.12) }
  const min = Math.min(...finiteValues.value)
  const max = Math.max(...finiteValues.value)
  const padding = Math.max((max - min) * 0.12, metric.value === 'home_runs' ? 0.3 : 2)
  return { min: Math.max(0, min - padding), max: max + padding }
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
  return `${points[0].x},365 ${polylinePoints.value} ${points.at(-1)!.x},365`
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
function shortDate(value: string) { const parts = value.split('-'); return parts.length === 3 ? `${parts[1]}/${parts[2]}` : value }
function formatAxis(value: number) { if (metric.value === 'rolling_avg') return value.toFixed(3); if (metric.value === 'max_ev') return value.toFixed(1); return value.toFixed(0) }
</script>

<style scoped>
.trend-card { min-width: 0; overflow: hidden; border: 1px solid var(--color-border); border-radius: 16px; background: var(--color-surface); box-shadow: var(--shadow-sm); }
.trend-card > header { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 20px 22px; border-bottom: 1px solid var(--color-border); }
.trend-card header span { color: var(--color-primary); font-size: 16px; font-weight: 900; letter-spacing: .07em; text-transform: uppercase; }
h2 { margin: 5px 0 0; color: var(--color-foreground); font-size: 28px; }
.metric-switch { display: flex; gap: 5px; border-radius: 10px; padding: 5px; background: var(--color-muted); }
.metric-switch button { min-height: 44px; border: 0; border-radius: 7px; padding: 8px 15px; color: var(--color-muted-text); background: transparent; cursor: pointer; font-size: 16px; font-weight: 800; }
.metric-switch button.active { color: #111; background: var(--color-primary); }
.chart-wrap { height: 520px; overflow-x: auto; padding: 14px 18px 4px; }
svg { display: block; width: 100%; min-width: 1000px; height: 100%; overflow: visible; }
.grid-lines line { stroke: var(--color-border); stroke-width: 1.2; vector-effect: non-scaling-stroke; }
.axis-labels text { fill: var(--color-muted-text); font: 600 15px "Fira Code", monospace; }
.area { fill: rgba(255, 153, 0, .1); }
.trend-line { fill: none; stroke: var(--color-primary); stroke-width: 3.5; stroke-linejoin: round; stroke-linecap: round; vector-effect: non-scaling-stroke; }
circle { fill: var(--color-primary); stroke: var(--color-surface); stroke-width: 2; vector-effect: non-scaling-stroke; }
.empty { margin: 0; padding: 50px 22px; color: var(--color-muted-text); font-size: 17px; }
@media (max-width: 700px) { .trend-card > header { align-items: flex-start; flex-direction: column; } .metric-switch { width: 100%; overflow-x: auto; } .metric-switch button { flex: 1 0 auto; } .chart-wrap { height: 430px; padding-inline: 4px; } }
</style>
