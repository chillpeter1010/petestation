<script setup lang="ts">
import type { PerformanceStatePlayerRow, PerformanceStateTarget } from '~/types/api'

const props = defineProps<{
  rows: PerformanceStatePlayerRow[]
  target: PerformanceStateTarget
  metricLabel: string
}>()

const hoveredGamePk = ref<number | null>(null)
const plot = { left: 82, right: 1060, top: 34, bottom: 330, width: 978, height: 296 }

const points = computed(() => props.rows.map((row, index, rows) => {
  const actual = actualPerformance(row)
  const forecast = forecastPerformance(row)
  return {
    row,
    actual,
    forecast,
    index,
    x: rows.length <= 1 ? plot.left + plot.width / 2 : plot.left + (index / (rows.length - 1)) * plot.width,
  }
}).filter(point => point.actual !== null))

const extent = computed(() => {
  const values = points.value.flatMap(point => [point.actual, point.forecast]).filter((value): value is number => value !== null)
  if (!values.length) return [-1, 1] as const
  const minimum = Math.min(...values, 0)
  const maximum = Math.max(...values, 0)
  const padding = Math.max(0.25, (maximum - minimum) * 0.12)
  return [minimum - padding, maximum + padding] as const
})
const yTicks = computed(() => Array.from({ length: 5 }, (_, index) => extent.value[1] - ((extent.value[1] - extent.value[0]) * index / 4)))
const actualPath = computed(() => seriesPath('actual'))
const forecastPath = computed(() => seriesPath('forecast'))
const dateLabelStep = computed(() => Math.max(1, Math.ceil(points.value.length / 9)))
const hoveredPoint = computed(() => points.value.find(point => point.row.game_pk === hoveredGamePk.value) || null)

function actualPerformance(row: PerformanceStatePlayerRow): number | null {
  return props.target === 'result_collapse' ? numeric(row.result_score) : numeric(row.process_score)
}

function forecastPerformance(row: PerformanceStatePlayerRow): number | null {
  if (props.target === 'result_collapse') return numeric(row.result_state_forecast)
  const signals = [numeric(row.stuff_state_forecast), numeric(row.command_state_forecast)].filter((value): value is number => value !== null)
  return signals.length ? signals.reduce((sum, value) => sum + value, 0) / signals.length : null
}

function probability(row: PerformanceStatePlayerRow, target: PerformanceStateTarget): number | null {
  return numeric(row[`${target}_probability` as keyof PerformanceStatePlayerRow])
}

function actualEvent(row: PerformanceStatePlayerRow) {
  return Boolean(row[props.target as keyof PerformanceStatePlayerRow])
}

function alerted(row: PerformanceStatePlayerRow) {
  return Boolean(row[`${props.target}_alert` as keyof PerformanceStatePlayerRow])
}

function outcome(row: PerformanceStatePlayerRow) {
  if (actualEvent(row) && alerted(row)) return 'Hit · actual and alerted'
  if (actualEvent(row)) return 'Miss · actual only'
  if (alerted(row)) return 'False alert · predicted only'
  return 'Correct negative'
}

function outcomeClass(row: PerformanceStatePlayerRow) {
  if (actualEvent(row) && alerted(row)) return 'is-hit'
  if (actualEvent(row)) return 'is-miss'
  if (alerted(row)) return 'is-false-alert'
  return 'is-negative'
}

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function scaleY(value: number) {
  const [minimum, maximum] = extent.value
  return plot.bottom - ((value - minimum) / Math.max(maximum - minimum, 0.0001)) * plot.height
}

function seriesPath(key: 'actual' | 'forecast') {
  let open = false
  return points.value.map(point => {
    const value = point[key]
    if (value === null) {
      open = false
      return ''
    }
    const command = open ? 'L' : 'M'
    open = true
    return `${command} ${point.x.toFixed(2)} ${scaleY(value).toFixed(2)}`
  }).filter(Boolean).join(' ')
}

function showDate(index: number) {
  return index === 0 || index === points.value.length - 1 || index % dateLabelStep.value === 0
}

function decimal(value: number | null | undefined, digits = 3) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—'
}

function signed(value: number | null | undefined, digits = 3) {
  return typeof value === 'number' && Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${value.toFixed(digits)}` : '—'
}

function pct(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '—'
}
</script>

<template>
  <section class="state-timeline">
    <header>
      <div><h3>Actual vs pre-appearance forecast</h3><p>{{ metricLabel }} by game · dashed connectors show forecast error</p></div>
      <span>{{ points.length }} appearances</span>
    </header>
    <div v-if="points.length" class="plot-wrap">
      <svg viewBox="0 0 1100 410" role="img" :aria-label="`${metricLabel} actual and forecast values by appearance date`">
        <g class="grid">
          <line v-for="tick in yTicks" :key="tick" :x1="plot.left" :x2="plot.right" :y1="scaleY(tick)" :y2="scaleY(tick)" />
          <line :x1="plot.left" :x2="plot.right" :y1="scaleY(0)" :y2="scaleY(0)" class="zero" />
        </g>
        <g class="forecast-errors">
          <line v-for="point in points.filter(item => item.forecast !== null)" :key="`error-${point.row.game_pk}`" :x1="point.x" :x2="point.x" :y1="scaleY(point.forecast as number)" :y2="scaleY(point.actual as number)" />
        </g>
        <path :d="forecastPath" class="forecast-line" />
        <path :d="actualPath" class="actual-line" />
        <g v-for="point in points" :key="point.row.game_pk" class="game-point" tabindex="0" role="button" :aria-label="`${point.row.game_date}, actual ${decimal(point.actual)}, forecast ${decimal(point.forecast)}`" @mouseenter="hoveredGamePk = point.row.game_pk" @mouseleave="hoveredGamePk = null" @focus="hoveredGamePk = point.row.game_pk" @blur="hoveredGamePk = null">
          <rect v-if="point.forecast !== null" :x="point.x - 4.5" :y="scaleY(point.forecast) - 4.5" width="9" height="9" class="forecast-point" :transform="`rotate(45 ${point.x} ${scaleY(point.forecast)})`" />
          <circle :cx="point.x" :cy="scaleY(point.actual as number)" r="5.5" class="actual-point" :class="outcomeClass(point.row)" />
          <circle :cx="point.x" :cy="scaleY(point.actual as number)" r="14" class="hit-target" />
        </g>
        <g class="axis-labels">
          <text v-for="tick in yTicks" :key="`y-${tick}`" :x="plot.left - 13" :y="scaleY(tick) + 4" text-anchor="end">{{ decimal(tick, 1) }}</text>
          <g v-for="point in points" :key="`date-${point.row.game_pk}`">
            <line :x1="point.x" :x2="point.x" :y1="plot.bottom" :y2="plot.bottom + 5" />
            <text v-if="showDate(point.index)" :x="point.x" :y="plot.bottom + 24" text-anchor="middle">{{ point.row.game_date.slice(5) }}</text>
          </g>
        </g>
      </svg>
      <aside v-if="hoveredPoint" class="chart-tooltip" :style="{ left: `${Math.min(82, Math.max(7, hoveredPoint.x / 11))}%`, top: `${Math.max(5, Math.min(scaleY(hoveredPoint.actual as number) / 4.1, 62))}%` }">
        <header><strong>{{ hoveredPoint.row.game_date }}</strong><span>{{ hoveredPoint.row.team || '—' }} · {{ hoveredPoint.row.pitches }} pitches</span></header>
        <dl>
          <div><dt>Actual {{ metricLabel }}</dt><dd>{{ decimal(hoveredPoint.actual) }}</dd></div>
          <div><dt>Forecast {{ metricLabel }}</dt><dd>{{ decimal(hoveredPoint.forecast) }}</dd></div>
          <div><dt>WPA</dt><dd>{{ signed(hoveredPoint.row.wpa) }}</dd></div>
          <div><dt>RE24</dt><dd>{{ signed(hoveredPoint.row.re24) }}</dd></div>
          <div><dt>WPA/LI</dt><dd>{{ signed(hoveredPoint.row.wpa_li) }}</dd></div>
          <div><dt>Stuff+ / Location+</dt><dd>{{ decimal(hoveredPoint.row.mean_stuff_plus, 1) }} / {{ decimal(hoveredPoint.row.mean_location_plus, 1) }}</dd></div>
          <div><dt>Process / Result</dt><dd>{{ decimal(hoveredPoint.row.process_score) }} / {{ decimal(hoveredPoint.row.result_score) }}</dd></div>
          <div><dt>Collapse P</dt><dd>{{ pct(probability(hoveredPoint.row, 'process_collapse')) }} / {{ pct(probability(hoveredPoint.row, 'result_collapse')) }}</dd></div>
          <div><dt>Rebound P</dt><dd>{{ pct(probability(hoveredPoint.row, 'return_to_baseline')) }} / {{ pct(probability(hoveredPoint.row, 'strong_rebound')) }}</dd></div>
        </dl>
        <p :class="outcomeClass(hoveredPoint.row)">{{ outcome(hoveredPoint.row) }}</p>
      </aside>
    </div>
    <p v-else class="empty">No eligible appearance timeline is available.</p>
    <footer>
      <span><i class="actual-key" />Actual {{ metricLabel }}</span>
      <span><i class="forecast-key" />Pre-appearance forecast</span>
      <span><i class="error-key" />Forecast-to-actual error</span>
      <span><b class="hit-key" />Purple ring = event hit</span>
    </footer>
  </section>
</template>

<style scoped>
.state-timeline { border-top: 1px solid var(--color-border); background: var(--color-background); }
.state-timeline > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; padding: 16px 18px 10px; }
.state-timeline h3 { margin: 0; font-size: 17px; }
.state-timeline header p, .state-timeline header span, .empty { margin: 4px 0 0; color: var(--color-muted-text); font-size: 13px; }
.plot-wrap { position: relative; overflow-x: auto; padding: 0 12px; }
svg { display: block; width: 100%; min-width: 820px; }
.grid line { stroke: var(--color-border); stroke-width: 1; }
.grid .zero { stroke: color-mix(in srgb, var(--color-muted-text) 70%, transparent); stroke-width: 1.5; }
.actual-line { fill: none; stroke: #dc655d; stroke-linecap: round; stroke-linejoin: round; stroke-width: 3.2; }
.forecast-line { fill: none; stroke: #6092dc; stroke-dasharray: 9 7; stroke-linecap: round; stroke-linejoin: round; stroke-width: 2.5; }
.forecast-errors line { stroke: color-mix(in srgb, #8aa4c9 52%, transparent); stroke-dasharray: 3 4; stroke-width: 1.3; }
.actual-point { fill: #dc655d; stroke: var(--color-background); stroke-width: 2.2; }
.actual-point.is-hit { stroke: #b982e5; stroke-width: 4; }
.actual-point.is-miss { stroke: #dc655d; }
.actual-point.is-false-alert { stroke: #6092dc; stroke-width: 4; }
.forecast-point { fill: #6092dc; stroke: var(--color-background); stroke-width: 1.5; }
.hit-target { fill: transparent; stroke: transparent; pointer-events: all; }
.game-point { cursor: crosshair; outline: none; }
.game-point:focus .hit-target { stroke: var(--color-primary); stroke-width: 1.5; }
.axis-labels text { fill: var(--color-muted-text); font-size: 11px; }
.axis-labels line { stroke: var(--color-muted-text); stroke-width: 1; }
.chart-tooltip { position: absolute; z-index: 4; width: min(360px, calc(100vw - 48px)); transform: translate(-50%, -8px); border: 1px solid var(--color-border-strong); padding: 12px; background: color-mix(in srgb, var(--color-surface) 96%, transparent); box-shadow: 0 12px 32px rgba(0, 0, 0, .32); pointer-events: none; }
.chart-tooltip header { display: flex; justify-content: space-between; gap: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--color-border); }
.chart-tooltip header span { margin: 0; font-size: 12px; }
.chart-tooltip dl { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 14px; margin: 10px 0; }
.chart-tooltip dl div { min-width: 0; }
.chart-tooltip dt { color: var(--color-muted-text); font-size: 10px; font-weight: 850; text-transform: uppercase; }
.chart-tooltip dd { margin: 3px 0 0; font-size: 13px; font-weight: 800; }
.chart-tooltip > p { margin: 0; border-top: 1px solid var(--color-border); padding-top: 8px; font-size: 12px; font-weight: 900; }
.chart-tooltip > p.is-hit { color: #c9a0ed; }
.chart-tooltip > p.is-miss { color: #ee918a; }
.chart-tooltip > p.is-false-alert { color: #8fb5ed; }
.chart-tooltip > p.is-negative { color: var(--color-muted-text); }
.state-timeline > footer { display: flex; flex-wrap: wrap; gap: 16px; padding: 0 18px 16px; color: var(--color-muted-text); font-size: 12px; }
.state-timeline > footer span { display: inline-flex; align-items: center; gap: 7px; }
.state-timeline > footer i { display: inline-block; width: 24px; height: 4px; }
.actual-key { background: #dc655d; }
.forecast-key { border-top: 3px dashed #6092dc; }
.error-key { border-top: 2px dashed #8aa4c9; }
.hit-key { display: inline-block; width: 11px; height: 11px; border: 3px solid #b982e5; border-radius: 50%; }
.empty { padding: 20px 18px; }
@media (max-width: 720px) {
  .state-timeline > header { flex-direction: column; }
  .chart-tooltip { left: 50% !important; top: 8% !important; }
}
</style>
