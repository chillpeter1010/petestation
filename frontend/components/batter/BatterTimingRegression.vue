<template>
  <section class="regression-workbench">
    <p class="method">保留 Stuff Attack 的研究欄位，加入 Swing Timing 全部對位指標；資料依本頁條件篩選，未套用 Stuff Attack 的 Stuff+ 門檻。回歸使用實際值，不使用 PR 值。</p>
    <p v-if="pending" role="status">正在載入本條件的回歸資料…</p>
    <p v-else-if="error" role="alert">{{ error }} <button type="button" @click="load">重新載入</button></p>
    <template v-else-if="response">
      <div class="axis-controls">
        <label>X axis<select v-model="xKey"><option v-for="option in options" :key="option.key" :value="option.key">{{ option.label }} · {{ available(option.key) }}</option></select><small>{{ xOption?.population }} · {{ xOption?.description }}</small></label>
        <label>Y axis<select v-model="yKey"><option v-for="option in options" :key="option.key" :value="option.key">{{ option.label }} · {{ available(option.key) }}</option></select><small>{{ yOption?.population }} · {{ yOption?.description }}</small></label>
        <button class="run-button" type="button" :disabled="points.length < 3 || xKey === yKey" @click="run">執行回歸</button>
      </div>
      <p class="sample-note">{{ eligibleRows.length }} 位符合篩選與搜尋條件的打者；{{ points.length }} 位 X／Y 皆有資料，{{ eligibleRows.length - points.length }} 位因缺值排除。每位打者等權重。</p>
      <div v-if="result" class="result-grid" aria-live="polite">
        <div><span>樣本</span><strong>{{ result.n }}</strong></div>
        <div><span>Pearson r</span><strong>{{ result.correlation.toFixed(3) }}</strong></div>
        <div><span>R²</span><strong>{{ result.rSquared.toFixed(3) }}</strong></div>
        <div><span>斜率</span><strong>{{ result.slope.toFixed(3) }}</strong></div>
        <div><span>p-value</span><strong>{{ result.pValue < .001 ? '< 0.001' : result.pValue.toFixed(3) }}</strong></div>
        <div><span>雙尾檢定 · p &lt; 0.05</span><strong>{{ result.significant ? '達統計顯著' : '未達統計顯著' }}</strong></div>
      </div>
      <p v-if="degenerate" role="status">所選指標沒有足夠變異，無法估計回歸。請改選其他指標或條件。</p>
      <div class="plot-scroll">
        <svg viewBox="0 0 760 420" role="img" :aria-label="`${xOption?.label} 與 ${yOption?.label} 的打者散點圖`">
          <defs>
            <clipPath id="timing-reg-plot"><rect x="70" y="20" width="650" height="330" /></clipPath>
            <clipPath v-for="point in points" :id="`timing-reg-head-${point.row.batter_id}`" :key="point.row.batter_id"><circle :cx="sx(point.x)" :cy="sy(point.y)" r="7" /></clipPath>
          </defs>
          <rect class="plot-bg" x="70" y="20" width="650" height="330" />
          <g v-for="tick in ticks" :key="tick">
            <line class="grid-line" :x1="70 + tick * 650" :x2="70 + tick * 650" y1="20" y2="350" />
            <line class="grid-line" x1="70" x2="720" :y1="350 - tick * 330" :y2="350 - tick * 330" />
            <text :x="70 + tick * 650" y="374" text-anchor="middle">{{ format(xDomain[0] + tick * (xDomain[1] - xDomain[0]), xOption?.unit) }}</text>
            <text x="62" :y="354 - tick * 330" text-anchor="end">{{ format(yDomain[0] + tick * (yDomain[1] - yDomain[0]), yOption?.unit) }}</text>
          </g>
          <g clip-path="url(#timing-reg-plot)">
            <line v-if="result" class="fit-line" :x1="sx(xDomain[0])" :x2="sx(xDomain[1])" :y1="sy(result.intercept + result.slope * xDomain[0])" :y2="sy(result.intercept + result.slope * xDomain[1])" />
            <g v-for="point in points" :key="point.row.batter_id" class="point" :class="{ selected: selectedBatterId === point.row.batter_id }" tabindex="0" role="button" :aria-label="`${point.row.name}: ${format(point.x, xOption?.unit)}, ${format(point.y, yOption?.unit)}`" @click="emit('select-batter', point.row.batter_id)" @keydown.enter.prevent="emit('select-batter', point.row.batter_id)" @keydown.space.prevent="emit('select-batter', point.row.batter_id)">
              <circle :cx="sx(point.x)" :cy="sy(point.y)" r="7" />
              <image :href="`https://img.mlbstatic.com/mlb-photos/image/upload/w_80,q_auto:eco,f_auto/v1/people/${point.row.batter_id}/headshot/silo/current`" :x="sx(point.x) - 7" :y="sy(point.y) - 7" width="14" height="14" :clip-path="`url(#timing-reg-head-${point.row.batter_id})`" />
              <title>{{ point.row.name }} · {{ xOption?.label }} {{ format(point.x, xOption?.unit) }} · {{ yOption?.label }} {{ format(point.y, yOption?.unit) }}</title>
            </g>
          </g>
          <text class="axis-label" x="395" y="407" text-anchor="middle">{{ xOption?.label }} ({{ xOption?.unit }})</text>
          <text class="axis-label" x="14" y="185" transform="rotate(-90 14 185)" text-anchor="middle">{{ yOption?.label }} ({{ yOption?.unit }})</text>
        </svg>
      </div>
      <p class="method">相關不代表因果。反覆嘗試多組指標會提高偽陽性機率；本區為樣本內單變量線性回歸，未宣稱樣本外預測能力。切換條件或 X／Y 軸後需重新執行。</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import type { SwingTimingResponse } from '~/types/api'
import { linearRegression, type LinearRegressionResult } from '~/utils/linearRegression'
import { timingMetricValue as value, timingRegressionPoints, timingRegressionDomain as domain } from '~/utils/timingRegression'
type Filters = { year: number; pitchGroup: string; pitchType: string; pitcherHand: 'All' | 'L' | 'R'; batterSide: 'All' | 'L' | 'R'; batterTeam: string; pitcherTeam: string; minimumSwings: number; minimumPlateAppearances: number }
const props = defineProps<{ filters: Filters; search: string; selectedBatterId: number | null }>()
const emit = defineEmits<{ 'select-batter': [id: number] }>()
const api = useApi()
const response = shallowRef<SwingTimingResponse | null>(null)
const pending = ref(false), error = ref(''), degenerate = ref(false)
const xKey = ref('on_time_pct'), yKey = ref('k_pct')
const result = ref<LinearRegressionResult | null>(null)
let requestId = 0
const options = computed(() => response.value?.filters.axis_options || [])
const xOption = computed(() => options.value.find(option => option.key === xKey.value))
const yOption = computed(() => options.value.find(option => option.key === yKey.value))
const eligibleRows = computed(() => {
  const needle = props.search.trim().toLowerCase()
  return (response.value?.leaderboard || []).filter(row => !needle || `${row.name} ${row.team} ${row.teams.join(' ')}`.toLowerCase().includes(needle))
})
const points = computed(() => timingRegressionPoints(eligibleRows.value, xKey.value, yKey.value))
const xDomain = computed(() => domain(points.value.map(point => point.x)))
const yDomain = computed(() => domain(points.value.map(point => point.y)))
const ticks = [0, .25, .5, .75, 1]
function sx(x: number) { return 70 + (x - xDomain.value[0]) / (xDomain.value[1] - xDomain.value[0]) * 650 }
function sy(y: number) { return 350 - (y - yDomain.value[0]) / (yDomain.value[1] - yDomain.value[0]) * 330 }
function available(key: string) { return eligibleRows.value.filter(row => value(row, key) !== null).length }
function format(n: number, unit?: string) { return unit === '%' ? `${n.toFixed(1)}%` : unit === 'rate' ? n.toFixed(3) : `${n.toFixed(['PA', 'swings', 'years'].includes(unit || '') ? 0 : 1)}${unit ? ` ${unit}` : ''}` }
function run() { result.value = linearRegression(points.value.map(({ x, y }) => ({ x, y }))); degenerate.value = result.value === null }
async function load() {
  const id = ++requestId
  pending.value = true; error.value = ''; response.value = null; result.value = null; degenerate.value = false
  try {
    const payload = await api.batterSwingTiming({ ...props.filters, includeRegression: true })
    if (id === requestId) response.value = payload
  } catch { if (id === requestId) error.value = '回歸資料載入失敗。' }
  finally { if (id === requestId) pending.value = false }
}
watch(() => JSON.stringify(props.filters), load, { immediate: true })
watch([xKey, yKey, () => props.search], () => { result.value = null; degenerate.value = false })
onBeforeUnmount(() => { requestId++ })
</script>

<style scoped>
.regression-workbench { padding: 18px; border-top: 1px solid var(--color-border); }
.method, .sample-note { color: var(--color-muted-text); font-size: 12px; line-height: 1.65; }
.axis-controls { display: grid; grid-template-columns: 1fr 1fr auto; gap: 14px; align-items: start; }
label { display: grid; gap: 7px; color: var(--color-muted-text); font-size: 12px; font-weight: 800; }
select, button { min-height: 42px; border: 1px solid var(--color-border); border-radius: 7px; padding: 8px 12px; color: var(--color-foreground); background: var(--color-background); }
small { font-size: 11px; line-height: 1.5; font-weight: 400; }
.run-button { margin-top: 22px; background: var(--color-primary); color: var(--color-on-primary); font-weight: 850; cursor: pointer; }
button:disabled { opacity: .45; cursor: not-allowed; }
.result-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 1px; background: var(--color-border); }
.result-grid > div { padding: 12px; background: var(--color-surface); }
.result-grid span { display: block; color: var(--color-muted-text); font-size: 11px; }
.result-grid strong { display: block; margin-top: 7px; color: var(--color-foreground); font-size: 20px; }
.plot-scroll { overflow-x: auto; margin-top: 16px; }
svg { display: block; width: 100%; min-width: 680px; }
.plot-bg { fill: var(--color-surface); stroke: var(--color-border); }
.grid-line { stroke: var(--color-border); opacity: .55; }
text { fill: var(--color-muted-text); font-size: 10px; }
.axis-label { font-weight: 800; }
.fit-line { stroke: var(--color-primary); stroke-width: 2; }
.point { cursor: pointer; }
.point circle { fill: #b9def0; stroke: var(--color-primary); }
.point.selected circle, .point:focus circle { stroke: white; stroke-width: 2.5; }
@media (max-width: 850px) { .axis-controls { grid-template-columns: 1fr; } .run-button { margin-top: 0; } .result-grid { grid-template-columns: repeat(3, 1fr); } }
</style>
