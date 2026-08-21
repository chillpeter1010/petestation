<template>
  <section class="team-wpa-chart">
    <header>
      <h3>{{ chartTitle }}</h3>
      <div class="team-wpa-chart__controls" role="group" aria-label="Season performance metric">
        <button type="button" :aria-pressed="mode === 'wpa'" @click="mode = 'wpa'">WPA</button>
        <button type="button" :aria-pressed="mode === 'game-score'" @click="mode = 'game-score'">Game Score</button>
      </div>
      <span>{{ points.length }} appearances</span>
    </header>
    <svg v-if="points.length" viewBox="0 0 520 250" role="img" :aria-label="chartAriaLabel">
      <g class="grid">
        <line v-for="tick in yTicks" :key="tick" x1="52" x2="502" :y1="scaleY(tick)" :y2="scaleY(tick)" />
        <line v-if="mode === 'wpa'" x1="52" x2="502" :y1="scaleY(0)" :y2="scaleY(0)" class="zero" />
      </g>
      <polyline :points="linePoints" />
      <circle v-for="point in points" :key="point.gamePk" :cx="scaleX(point.index)" :cy="scaleY(point.value)" r="3.5">
        <title>{{ point.tooltip }}</title>
      </circle>
      <g class="labels">
        <text x="52" y="238">{{ points[0]?.date }}</text>
        <text x="502" y="238" text-anchor="end">{{ points.at(-1)?.date }}</text>
        <text v-for="tick in yTicks" :key="`label-${tick}`" x="44" :y="scaleY(tick) + 4" text-anchor="end">{{ tickLabel(tick) }}</text>
      </g>
    </svg>
    <p v-else>No appearance WPA is available.</p>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{ rows: Record<string, unknown>[] }>()
const mode = ref<'wpa' | 'game-score'>('wpa')
const chartTitle = computed(() => mode.value === 'wpa' ? 'Cumulative WPA' : 'Game Score by appearance')
const chartAriaLabel = computed(() => mode.value === 'wpa'
  ? 'Season cumulative WPA from oldest to newest appearance'
  : 'Game Score for each appearance from oldest to newest')
const points = computed(() => props.rows.flatMap(row => {
  const rawValue = mode.value === 'wpa' ? row.cum_wpa : row.game_score
  if (rawValue === null || rawValue === undefined || rawValue === '') return []
  const value = Number(rawValue)
  const gamePk = Number(row.game_pk)
  if (!Number.isFinite(value) || !Number.isFinite(gamePk)) return []
  const date = String(row.game_date || '').slice(5, 10)
  const tooltip = mode.value === 'wpa'
    ? `${date} · ${signed(Number(row.game_wpa) || 0)} game WPA · ${signed(value)} cumulative`
    : `${date} · Game Score ${Math.round(value)}`
  return [{ gamePk, value, date, tooltip }]
}).map((point, index) => ({ ...point, index })))
const extent = computed(() => {
  const values = points.value.map(point => point.value).concat(mode.value === 'wpa' ? [0] : [])
  const min = Math.min(...values); const max = Math.max(...values)
  const pad = Math.max(mode.value === 'wpa' ? .08 : 5, (max - min) * .14)
  return [min - pad, max + pad] as const
})
const yTicks = computed(() => Array.from({ length: 4 }, (_, index) => extent.value[0] + (extent.value[1] - extent.value[0]) / 3 * index))
const linePoints = computed(() => points.value.map(point => `${scaleX(point.index)},${scaleY(point.value)}`).join(' '))
function scaleX(index: number) { return points.value.length <= 1 ? 277 : 52 + index / (points.value.length - 1) * 450 }
function scaleY(value: number) { return 210 - (value - extent.value[0]) / (extent.value[1] - extent.value[0] || 1) * 180 }
function signed(value: number) { return `${value >= 0 ? '+' : ''}${value.toFixed(3)}` }
function tickLabel(value: number) { return mode.value === 'wpa' ? value.toFixed(2) : Math.round(value).toString() }
</script>

<style scoped>
.team-wpa-chart { min-width: 0; border: 1px solid var(--team-panel-border); border-radius: 14px; background: var(--color-surface); }
.team-wpa-chart header { display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 12px; border-bottom: 1px solid var(--team-panel-border); padding: 10px 12px 10px 16px; }
.team-wpa-chart h3 { margin: 0; color: var(--color-text); font-size: 15px; }
.team-wpa-chart header span, .team-wpa-chart p { color: var(--color-muted-text); font-size: 11px; }
.team-wpa-chart__controls { display: flex; gap: 3px; border: 1px solid var(--team-panel-border); border-radius: 8px; padding: 3px; background: var(--team-panel-bg); }
.team-wpa-chart__controls button { min-height: 28px; border: 0; border-radius: 6px; padding: 4px 8px; color: var(--color-muted-text); background: transparent; font-size: 9px; font-weight: 900; cursor: pointer; }
.team-wpa-chart__controls button[aria-pressed="true"] { color: #fff; background: var(--team-primary); }
.team-wpa-chart svg { display: block; width: 100%; height: auto; }
.grid line { stroke: color-mix(in srgb, var(--color-muted-text) 35%, transparent); stroke-width: 1; }
.grid .zero { stroke: var(--color-muted-text); stroke-width: 1.3; }
polyline { fill: none; stroke: var(--team-primary); stroke-linecap: round; stroke-linejoin: round; stroke-width: 2.8; }
circle { fill: var(--team-primary); stroke: #fff; stroke-width: 1.6; }
.labels text { fill: var(--color-muted-text); font-size: 9px; }
.team-wpa-chart p { margin: 0; padding: 20px 16px; }
@media (max-width: 560px) { .team-wpa-chart header { grid-template-columns: 1fr auto; } .team-wpa-chart header > span { display: none; } }
</style>
