<template>
  <section class="fatigue-pa-chart">
    <header class="chart-header">
      <div>
        <h2>Rule estimate vs PA results</h2>
        <p>The orange line is a fixed-rate readiness rule, not observed physical decline.</p>
      </div>
      <span>{{ points.length }} PA</span>
    </header>

    <div v-if="points.length" class="plot-wrap">
      <div class="chart-legend">
        <span><i class="fatigue-swatch" /> Rule estimate</span>
        <span><i class="suppression-swatch" /> Suppression</span>
      </div>
      <svg viewBox="0 0 760 310" role="img" aria-label="Plate appearance fatigue trend" @mouseleave="hoveredPoint = null">
        <g class="grid">
          <line v-for="tick in yTicks" :key="`y-${tick}`" :x1="plot.left" :x2="plot.right" :y1="scaleY(tick)" :y2="scaleY(tick)" />
          <line v-for="tick in xTicks" :key="`x-${tick}`" :x1="scaleX(tick)" :x2="scaleX(tick)" :y1="plot.top" :y2="plot.bottom" />
        </g>
        <polyline class="trend-line" :points="linePoints" />
        <polyline class="suppression-line" :points="suppressionLinePoints" />
        <g>
          <rect
            v-for="point in pointsWithSuppression"
            :key="`suppression-${point.paIndex}-${point.pitchCount}`"
            :x="scaleX(point.cumulativePitches) - 4"
            :y="scaleY(point.suppressionScore) - 4"
            width="8"
            height="8"
            rx="2"
            class="suppression-point"
            @mouseenter="hoveredPoint = point"
            @mousemove="hoveredPoint = point"
          >
            <title>
              Pitch {{ point.cumulativePitches }} | {{ point.batterName }} | Suppression {{ formatNumber(point.suppressionScore, 1) }}
            </title>
          </rect>
        </g>
        <g>
          <circle
            v-for="point in points"
            :key="`${point.paIndex}-${point.pitchCount}`"
            :cx="scaleX(point.cumulativePitches)"
            :cy="scaleY(point.fatigueScore)"
            r="5"
            :class="resultClass(point.event)"
            @mouseenter="hoveredPoint = point"
            @mousemove="hoveredPoint = point"
          >
            <title>
              Pitch {{ point.cumulativePitches }} | {{ point.batterName }} | Fatigue {{ formatNumber(point.fatigueScore, 1) }}
            </title>
          </circle>
        </g>
        <g class="labels">
          <text v-for="tick in yTicks" :key="`yl-${tick}`" :x="plot.left - 12" :y="scaleY(tick) + 4" text-anchor="end">{{ formatNumber(tick, 0) }}</text>
          <text v-for="tick in xTicks" :key="`xl-${tick}`" :x="scaleX(tick)" :y="plot.bottom + 26" text-anchor="middle">{{ tick }}</text>
          <text :x="plot.left + plot.width / 2" :y="plot.bottom + 52" text-anchor="middle">Cumulative Pitches</text>
          <text :x="22" :y="plot.top + plot.height / 2" class="axis-title" text-anchor="middle" transform="rotate(-90 22 146)">Score</text>
        </g>
      </svg>
      <div v-if="hoveredPoint" class="point-tooltip" :style="tooltipStyle">
        <strong>PA {{ hoveredPoint.paIndex }} | Pitch {{ hoveredPoint.cumulativePitches }}</strong>
        <span>Batter {{ hoveredPoint.batterName }}</span>
        <span>Fatigue {{ formatNumber(hoveredPoint.fatigueScore, 1) }}</span>
        <span v-if="Number.isFinite(hoveredPoint.suppressionScore)">Suppression {{ formatNumber(hoveredPoint.suppressionScore, 1) }}</span>
        <span v-if="Number.isFinite(hoveredPoint.suppressionScore)">CSW {{ hoveredPoint.csw }} | Whiff {{ hoveredPoint.whiffs }} | HH {{ hoveredPoint.hardHits }}</span>
        <span v-if="Number.isFinite(hoveredPoint.veloDrop)">FB velo drop {{ formatNumber(hoveredPoint.veloDrop, 1) }} mph</span>
        <span>Result {{ hoveredPoint.event }}</span>
      </div>
    </div>

    <p v-else class="empty">No plate appearance fatigue data for the selected game.</p>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{
  rows: Array<Record<string, unknown>>
}>()

type FatiguePoint = {
  paIndex: number
  cumulativePitches: number
  batterName: string
  fatigueScore: number
  suppressionScore: number
  suppressionDelta: number
  csw: number
  whiffs: number
  hardHits: number
  veloDrop: number
  event: string
  description: string
  pitchCount: number
  inning: string
}

const hoveredPoint = ref<FatiguePoint | null>(null)

const plot = {
  left: 66,
  right: 728,
  top: 24,
  bottom: 244,
  width: 662,
  height: 220
}

const points = computed<FatiguePoint[]>(() => props.rows.flatMap((row, index) => {
  const cumulativePitches = Number(row.cumulative_pitches)
  const fatigueScore = Number(row.fatigue_score)
  if (!Number.isFinite(cumulativePitches) || !Number.isFinite(fatigueScore)) {
    return []
  }
  return [{
    paIndex: Number(row.pa_index) || index + 1,
    cumulativePitches,
    batterName: String(row.batter_name || '-'),
    fatigueScore,
    suppressionScore: Number(row.suppression_score),
    suppressionDelta: Number(row.suppression_delta),
    csw: Number(row.csw) || 0,
    whiffs: Number(row.whiffs) || 0,
    hardHits: Number(row.hard_hits) || 0,
    veloDrop: Number(row.velo_drop),
    event: String(row.event || '-'),
    description: String(row.description || '-'),
    pitchCount: Number(row.pitch_count) || 0,
    inning: String(row.inning || '-')
  }]
}))

const pointsWithSuppression = computed(() => points.value.filter((point) => Number.isFinite(point.suppressionScore)))

const tooltipStyle = computed(() => {
  const point = hoveredPoint.value
  if (!point) {
    return {}
  }
  const x = Math.min(scaleX(point.cumulativePitches) + 16, plot.right - 190)
  const y = Math.max(scaleY(point.fatigueScore) - 74, plot.top + 8)
  return {
    left: `${x}px`,
    top: `${y}px`
  }
})

const yExtent = computed(() => {
  const values = points.value
    .flatMap((point) => [point.fatigueScore, point.suppressionScore])
    .filter(Number.isFinite)
    .concat([45, 100])
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pad = Math.max(4, (max - min) * 0.16)
  return [Math.max(0, min - pad), Math.min(110, max + pad)] as const
})

const xExtent = computed(() => {
  const maxPitch = Math.max(...points.value.map((point) => point.cumulativePitches), 1)
  return [0, Math.ceil(maxPitch / 10) * 10] as const
})

const yTicks = computed(() => {
  const [min, max] = yExtent.value
  const step = (max - min) / 4
  return Array.from({ length: 5 }, (_, index) => min + step * index)
})

const xTicks = computed(() => {
  const [, max] = xExtent.value
  const step = Math.max(10, Math.ceil(max / 5 / 5) * 5)
  const ticks: number[] = []
  for (let value = 0; value <= max; value += step) {
    ticks.push(value)
  }
  if (!ticks.includes(max)) {
    ticks.push(max)
  }
  return ticks
})

const linePoints = computed(() => {
  return points.value.map((point) => `${scaleX(point.cumulativePitches)},${scaleY(point.fatigueScore)}`).join(' ')
})

const suppressionLinePoints = computed(() => {
  return pointsWithSuppression.value.map((point) => `${scaleX(point.cumulativePitches)},${scaleY(point.suppressionScore)}`).join(' ')
})

function scaleX(value: number) {
  const [min, max] = xExtent.value
  return plot.left + ((value - min) / (max - min || 1)) * plot.width
}

function scaleY(value: number) {
  const [min, max] = yExtent.value
  return plot.bottom - ((value - min) / (max - min || 1)) * plot.height
}

function resultClass(event: string) {
  const text = event.toLowerCase()
  if (text.includes('strikeout')) {
    return 'result-strikeout'
  }
  if (text.includes('walk') || text.includes('hit_by_pitch')) {
    return 'result-walk'
  }
  if (text.includes('single') || text.includes('double') || text.includes('triple') || text.includes('home_run')) {
    return 'result-hit'
  }
  if (text.includes('field_out') || text.includes('force_out') || text.includes('grounded_into')) {
    return 'result-out'
  }
  return 'result-other'
}

function formatNumber(value: number, digits: number) {
  return Number.isFinite(value) ? value.toFixed(digits) : '-'
}

</script>

<style scoped>
.fatigue-pa-chart {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.chart-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}

.chart-header h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

.chart-header p,
.chart-header span,
.empty {
  margin: 3px 0 0;
  color: var(--color-muted-text);
  font-size: 13px;
}

.plot-wrap {
  position: relative;
  overflow-x: auto;
  padding: 8px 10px 6px;
}

.chart-legend {
  display: flex;
  gap: 14px;
  padding: 0 0 4px 58px;
  color: var(--color-muted-text);
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
}

.chart-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.chart-legend i {
  display: inline-block;
  width: 16px;
  height: 3px;
  border-radius: 99px;
}

.fatigue-swatch {
  background: var(--color-primary);
}

.suppression-swatch {
  background: #38bdf8;
}

svg {
  display: block;
  width: 100%;
  min-width: 620px;
}

.grid line {
  stroke: var(--color-border);
  stroke-width: 1;
}

.trend-line {
  fill: none;
  stroke: var(--color-primary);
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2.6;
}

.suppression-line {
  fill: none;
  stroke: #38bdf8;
  stroke-dasharray: 7 6;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2.3;
}

.suppression-point {
  fill: #38bdf8;
  stroke: rgba(3, 7, 18, 0.9);
  stroke-width: 1.1;
}

circle {
  stroke: rgba(3, 7, 18, 0.9);
  stroke-width: 1.2;
}

.result-strikeout {
  fill: #3b82f6;
}

.result-out {
  fill: #22c55e;
}

.result-hit {
  fill: #ef4444;
}

.result-walk {
  fill: #f59e0b;
}

.result-other {
  fill: #94a3b8;
}

.labels text {
  fill: var(--color-muted-text);
  font-size: 12px;
  font-weight: 700;
}

.labels .axis-title {
  font-size: 12px;
  text-transform: uppercase;
}

.empty {
  padding: 16px;
}

.point-tooltip {
  position: absolute;
  z-index: 3;
  display: grid;
  gap: 5px;
  min-width: 190px;
  max-width: 240px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  color: var(--color-foreground);
  background: rgba(15, 23, 42, 0.96);
  box-shadow: var(--shadow-md);
  pointer-events: none;
}

.point-tooltip strong {
  color: #fff;
  font-size: 13px;
}

.point-tooltip span {
  color: #dbeafe;
  font-size: 12px;
  font-weight: 800;
}
</style>
