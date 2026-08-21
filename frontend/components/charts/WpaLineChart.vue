<template>
  <section class="wpa-chart">
    <header class="chart-header">
      <h2>Cumulative WPA</h2>
      <span>{{ rows.length }} starts</span>
    </header>
    <div v-if="points.length" class="plot-wrap">
      <svg viewBox="0 0 760 290" role="img" aria-label="Cumulative WPA line chart">
        <g class="grid">
          <line v-for="tick in yTicks" :key="tick" :x1="plot.left" :x2="plot.right" :y1="scaleY(tick)" :y2="scaleY(tick)" />
          <line :x1="plot.left" :x2="plot.right" :y1="scaleY(0)" :y2="scaleY(0)" class="zero" />
        </g>
        <polyline class="line" :points="linePoints" />
        <g>
          <circle v-for="point in points" :key="point.gamePk" :cx="scaleX(point.index)" :cy="scaleY(point.cumWpa)" r="4">
            <title>{{ point.label }} | Game WPA {{ formatNumber(point.gameWpa) }} | Cum WPA {{ formatNumber(point.cumWpa) }}</title>
          </circle>
        </g>
        <g class="labels">
          <text :x="plot.left" :y="plot.bottom + 28">{{ firstDate }}</text>
          <text :x="plot.right" :y="plot.bottom + 28" text-anchor="end">{{ lastDate }}</text>
          <text v-for="tick in yTicks" :key="`yl-${tick}`" :x="plot.left - 12" :y="scaleY(tick) + 4" text-anchor="end">{{ formatNumber(tick) }}</text>
        </g>
      </svg>
    </div>
    <p v-else class="empty">No WPA data available for the current filters.</p>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{
  rows: Array<Record<string, unknown>>
}>()

const plot = {
  left: 58,
  right: 730,
  top: 26,
  bottom: 238,
  width: 672,
  height: 212
}

const points = computed(() => props.rows.flatMap((row, index) => {
  const cumWpa = Number(row.cum_wpa)
  const gameWpa = Number(row.game_wpa)
  const gamePk = Number(row.game_pk)
  if (!Number.isFinite(cumWpa) || !Number.isFinite(gamePk)) {
    return []
  }
  return [{
    index,
    gamePk,
    cumWpa,
    gameWpa: Number.isFinite(gameWpa) ? gameWpa : 0,
    date: String(row.game_date || '').slice(0, 10),
    label: String(row.label || row.game_date || gamePk)
  }]
}))

const yExtent = computed(() => {
  const values = points.value.map((point) => point.cumWpa).concat(0)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pad = Math.max(0.1, (max - min) * 0.16)
  return [min - pad, max + pad] as const
})

const yTicks = computed(() => {
  const [min, max] = yExtent.value
  const step = (max - min) / 4
  return Array.from({ length: 5 }, (_, index) => min + step * index)
})

const linePoints = computed(() => {
  return points.value.map((point) => `${scaleX(point.index)},${scaleY(point.cumWpa)}`).join(' ')
})

const firstDate = computed(() => points.value[0]?.date || '')
const lastDate = computed(() => points.value.at(-1)?.date || '')

function scaleX(index: number) {
  if (points.value.length <= 1) {
    return plot.left + plot.width / 2
  }
  return plot.left + (index / (points.value.length - 1)) * plot.width
}

function scaleY(value: number) {
  const [min, max] = yExtent.value
  return plot.bottom - ((value - min) / (max - min || 1)) * plot.height
}

function formatNumber(value: number) {
  return Number.isFinite(value) ? value.toFixed(3) : '-'
}
</script>

<style scoped>
.wpa-chart {
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

.chart-header span,
.empty {
  color: var(--color-muted-text);
  font-size: 13px;
}

.plot-wrap {
  overflow-x: auto;
  padding: 8px 10px 0;
}

svg {
  display: block;
  width: 100%;
  min-width: 600px;
}

.grid line {
  stroke: #e2e8f0;
  stroke-width: 1;
}

.grid .zero {
  stroke: #94a3b8;
  stroke-width: 1.4;
}

.line {
  fill: none;
  stroke: var(--color-primary);
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2.6;
}

circle {
  fill: var(--color-primary);
  stroke: rgba(255, 255, 255, 0.92);
  stroke-width: 2;
}

.labels text {
  fill: #64748b;
  font-size: 12px;
}

.empty {
  margin: 0;
  padding: 16px;
}
</style>
