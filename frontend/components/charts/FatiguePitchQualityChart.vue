<template>
  <section class="quality-chart">
    <header>
      <div>
        <span>Observed pitch quality</span>
        <h3>Stuff+ by pitch sequence</h3>
      </div>
      <div class="mode-switch" role="group" aria-label="Stuff plus smoothing">
        <button type="button" :aria-pressed="mode === 'ma5'" @click="mode = 'ma5'">MA5</button>
        <button type="button" :aria-pressed="mode === 'raw'" @click="mode = 'raw'">Raw</button>
      </div>
    </header>

    <svg v-if="series.length" viewBox="0 0 920 390" role="img" aria-label="Stuff plus by pitch sequence and pitch type">
      <g class="grid">
        <line v-for="tick in yTicks" :key="tick" x1="58" x2="894" :y1="scaleY(tick)" :y2="scaleY(tick)" />
        <line x1="58" x2="894" :y1="scaleY(100)" :y2="scaleY(100)" class="average" />
      </g>
      <g v-for="group in series" :key="group.pitch">
        <polyline :points="linePoints(group.points)" :style="{ stroke: group.color }" />
        <circle
          v-for="point in group.points"
          :key="`${group.pitch}-${point.x}`"
          :cx="scaleX(point.x)"
          :cy="scaleY(point.y)"
          :fill="group.color"
          r="4"
        >
          <title>Pitch {{ point.x }} · {{ group.pitch }} · Stuff+ {{ point.y.toFixed(1) }}</title>
        </circle>
      </g>
      <g class="labels">
        <text v-for="tick in yTicks" :key="`y-${tick}`" x="50" :y="scaleY(tick) + 4" text-anchor="end">{{ tick }}</text>
        <text x="58" y="374">Pitch 1</text>
        <text x="894" y="374" text-anchor="end">Pitch {{ maxPitch }}</text>
      </g>
    </svg>
    <p v-else>No cached per-pitch Stuff+ is available for this outing.</p>

    <footer v-if="series.length">
      <span v-for="group in series" :key="`legend-${group.pitch}`">
        <i :style="{ background: group.color }" />{{ group.pitch }}
        <b :class="trendClass(group.slope)">{{ formatSlope(group.slope) }}/10 pitches</b>
      </span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { getPitchColor } from '~/utils/pitchColors'

const props = defineProps<{ rows: Record<string, unknown>[] }>()
const mode = ref<'ma5' | 'raw'>('ma5')

const validRows = computed(() => props.rows.flatMap((row) => {
  const x = Number(row.pitch_index)
  const rawY = mode.value === 'ma5' ? row.stuff_ma5 : row.stuff_plus
  if (rawY === null || rawY === undefined || rawY === '' || rawY === '-') return []
  const y = Number(rawY)
  if (!Number.isFinite(x) || !Number.isFinite(y)) return []
  return [{ x, y, pitch: String(row.pitch || 'Unknown') }]
}))
const series = computed(() => {
  const groups = new Map<string, { x: number; y: number }[]>()
  for (const row of validRows.value) {
    if (!groups.has(row.pitch)) groups.set(row.pitch, [])
    groups.get(row.pitch)!.push({ x: row.x, y: row.y })
  }
  return [...groups.entries()].map(([pitch, points]) => ({
    pitch,
    points,
    color: getPitchColor(pitch),
    slope: linearSlope(points) * 10
  }))
})
const maxPitch = computed(() => Math.max(1, ...validRows.value.map(row => row.x)))
const extent = computed(() => {
  const values = validRows.value.map(row => row.y).concat([100])
  const min = Math.min(...values); const max = Math.max(...values)
  const pad = Math.max(5, (max - min) * 0.1)
  return [Math.floor((min - pad) / 10) * 10, Math.ceil((max + pad) / 10) * 10] as const
})
const yTicks = computed(() => Array.from({ length: 5 }, (_, index) => Math.round(extent.value[0] + (extent.value[1] - extent.value[0]) * index / 4)))
function scaleX(value: number) { return 58 + (value - 1) / Math.max(maxPitch.value - 1, 1) * 836 }
function scaleY(value: number) { return 342 - (value - extent.value[0]) / Math.max(extent.value[1] - extent.value[0], 1) * 300 }
function linePoints(points: { x: number; y: number }[]) { return points.map(point => `${scaleX(point.x)},${scaleY(point.y)}`).join(' ') }
function linearSlope(points: { x: number; y: number }[]) {
  if (points.length < 3) return Number.NaN
  const meanX = points.reduce((sum, point) => sum + point.x, 0) / points.length
  const meanY = points.reduce((sum, point) => sum + point.y, 0) / points.length
  const denominator = points.reduce((sum, point) => sum + (point.x - meanX) ** 2, 0)
  if (!denominator) return Number.NaN
  return points.reduce((sum, point) => sum + (point.x - meanX) * (point.y - meanY), 0) / denominator
}
function formatSlope(value: number) { return Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${value.toFixed(1)}` : '-' }
function trendClass(value: number) { return !Number.isFinite(value) ? '' : value < -1 ? 'down' : value > 1 ? 'up' : '' }
</script>

<style scoped>
.quality-chart { min-width: 0; overflow: hidden; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); }
header { display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--color-border); padding: 16px 18px; }
header span { color: var(--color-primary); font-size: 11px; font-weight: 900; text-transform: uppercase; }
h3 { margin: 4px 0 0; color: var(--color-foreground); font-size: 20px; }
.mode-switch { display: flex; gap: 3px; border: 1px solid var(--color-border); border-radius: 9px; padding: 3px; }
button { border: 0; border-radius: 7px; padding: 8px 12px; color: var(--color-muted-text); background: transparent; font-weight: 900; cursor: pointer; }
button[aria-pressed="true"] { color: #111; background: var(--color-primary); }
svg { display: block; width: 100%; height: auto; }
.grid line { stroke: color-mix(in srgb, var(--color-muted-text) 24%, transparent); stroke-width: 1; }
.grid .average { stroke: var(--color-foreground); stroke-dasharray: 7 6; stroke-width: 1.4; }
polyline { fill: none; stroke-width: 2.6; stroke-linecap: round; stroke-linejoin: round; }
circle { stroke: var(--color-surface); stroke-width: 1.3; }
.labels text { fill: var(--color-muted-text); font-size: 11px; }
p { margin: 0; padding: 26px 18px; color: var(--color-muted-text); }
footer { display: flex; flex-wrap: wrap; gap: 10px 18px; border-top: 1px solid var(--color-border); padding: 12px 18px 16px; color: var(--color-muted-text); font-size: 12px; font-weight: 800; }
footer span { display: inline-flex; align-items: center; gap: 6px; }
footer i { width: 10px; height: 10px; border-radius: 50%; }
footer b { color: var(--color-muted-text); font-family: "Fira Code", "Consolas", monospace; font-size: 10px; }
footer b.down { color: #e76455; }
footer b.up { color: #72c98b; }
</style>
