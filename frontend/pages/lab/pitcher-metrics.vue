<template>
  <main class="explorer-page">
    <ComparisonPageHeader
      eyebrow="Pitcher Lab · Season level"
      title="Pitcher Metric Explorer"
      description="Compare compatible pitcher-season metrics without mixing game, pitch, or window-level observations."
      back-to="/lab"
      back-label="Pitcher Lab"
    />

    <section class="filter-panel" aria-label="Pitcher metric filters">
      <label><span>Season</span><select v-model.number="year"><option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option></select></label>
      <label><span>Role</span><select v-model="role"><option value="All">All</option><option value="SP">Starter</option><option value="RP">Reliever</option></select></label>
      <label><span>Team</span><select v-model="team"><option value="All">All</option><option v-for="option in response?.teams || []" :key="option" :value="option">{{ option }}</option></select></label>
      <label><span>Minimum IP</span><input v-model.number="minimumIp" type="number" min="0" step="5"></label>
      <label class="search"><span>Find pitcher</span><input v-model.trim="searchText" type="search" placeholder="Pitcher or team"></label>
    </section>

    <p v-if="pending" class="state-card"><strong>Preparing pitcher-season rows…</strong><span>Joining basic, Plus, advanced, and available Stamina sources.</span></p>
    <p v-else-if="error" class="state-card error">Unable to load Pitcher Metric Explorer.</p>
    <template v-else-if="response">
      <details v-if="response.warnings.length" class="warning-card">
        <summary>{{ response.warnings.length }} source note{{ response.warnings.length === 1 ? '' : 's' }}</summary>
        <p v-for="warning in response.warnings" :key="warning">{{ warning }}</p>
      </details>

      <section class="source-strip" aria-label="Source status">
        <article v-for="(status, source) in response.source_status" :key="source"><span>{{ source }}</span><strong :class="status">{{ status }}</strong></article>
      </section>

      <section class="workbench">
        <header>
          <div><span>Complete-case pitcher sample</span><h2>Build a pitcher-season lens</h2></div>
          <div class="axis-controls">
            <label><span>X axis</span><select v-model="xMetric"><optgroup v-for="group in metricGroups" :key="`x-${group.category}`" :label="group.category"><option v-for="metric in group.metrics" :key="`x-${metric.key}`" :value="metric.key">{{ metric.label }} · {{ coverage(metric.key) }}</option></optgroup></select></label>
            <label><span>Y axis</span><select v-model="yMetric"><optgroup v-for="group in metricGroups" :key="`y-${group.category}`" :label="group.category"><option v-for="metric in group.metrics" :key="`y-${metric.key}`" :value="metric.key">{{ metric.label }} · {{ coverage(metric.key) }}</option></optgroup></select></label>
            <button type="button" class="regression-button" :disabled="plotRows.length < 3 || xMetric === yMetric" @click="runRegression"><Calculator :size="17" aria-hidden="true" />執行回歸</button>
          </div>
        </header>

        <div class="metric-notes">
          <p><strong>{{ xDefinition?.label }}</strong>{{ xDefinition?.description }} <small>{{ coverage(xMetric) }} available after filters</small></p>
          <p><strong>{{ yDefinition?.label }}</strong>{{ yDefinition?.description }} <small>{{ coverage(yMetric) }} available after filters</small></p>
        </div>

        <section v-if="regressionResult" class="regression-summary" aria-live="polite">
          <article><span>Sample</span><strong>{{ regressionResult.n }}</strong></article>
          <article><span>Pearson r</span><strong>{{ regressionResult.correlation.toFixed(3) }}</strong></article>
          <article><span>Spearman ρ</span><strong>{{ spearman == null ? '—' : spearman.toFixed(3) }}</strong></article>
          <article><span>R²</span><strong>{{ regressionResult.rSquared.toFixed(3) }}</strong></article>
          <article><span>Slope</span><strong>{{ regressionResult.slope.toFixed(3) }}</strong></article>
          <article><span>p-value</span><strong>{{ pValue(regressionResult.pValue) }}</strong></article>
          <article class="significance" :class="{ significant: regressionResult.significant }"><span>雙尾檢定</span><strong>{{ regressionResult.significant ? '達統計顯著' : '未達統計顯著' }}</strong><small>門檻 p &lt; 0.05</small></article>
          <p>每位投手等權重；相關不代表因果。重複嘗試許多軸會提高偽陽性的機率，p-value 不應單獨作為結論。</p>
        </section>

        <div class="chart-wrap">
          <svg viewBox="0 0 900 520" role="img" :aria-label="`${xDefinition?.label} by ${yDefinition?.label} pitcher scatter plot`">
            <defs>
              <clipPath v-for="row in headshotRows" :id="`pitcher-headshot-${row.player_id}`" :key="`clip-${row.player_id}`">
                <circle :cx="xPosition(metricValue(row, xMetric))" :cy="yPosition(metricValue(row, yMetric))" :r="pointRadius(row)" />
              </clipPath>
            </defs>
            <rect x="80" y="30" width="780" height="410" rx="14" class="plot-background" />
            <g class="grid-lines"><line v-for="tick in 5" :key="`v-${tick}`" :x1="80 + tick * 130" y1="30" :x2="80 + tick * 130" y2="440"/><line v-for="tick in 4" :key="`h-${tick}`" x1="80" :y1="30 + tick * 82" x2="860" :y2="30 + tick * 82"/></g>
            <line v-if="regressionLine" :x1="regressionLine.x1" :y1="regressionLine.y1" :x2="regressionLine.x2" :y2="regressionLine.y2" class="regression-line" />
            <g v-for="row in plotRows" :key="row.player_id" class="pitcher-point" tabindex="0" role="link" @click="openPitcher(row)" @keydown.enter="openPitcher(row)">
              <circle :cx="xPosition(metricValue(row, xMetric))" :cy="yPosition(metricValue(row, yMetric))" :r="pointRadius(row)" />
              <image v-if="headshotIds.has(row.player_id)" :href="headshotUrl(row.player_id)" :x="xPosition(metricValue(row, xMetric)) - pointRadius(row)" :y="yPosition(metricValue(row, yMetric)) - pointRadius(row)" :width="pointRadius(row) * 2" :height="pointRadius(row) * 2" :clip-path="`url(#pitcher-headshot-${row.player_id})`" preserveAspectRatio="xMidYMid slice" />
              <title>{{ row.name }} — {{ formatMetric(metricValue(row, xMetric), xDefinition?.unit) }} / {{ formatMetric(metricValue(row, yMetric), yDefinition?.unit) }}</title>
            </g>
            <text x="470" y="493" text-anchor="middle" class="axis-label">{{ xDefinition?.label }} →</text>
            <text x="22" y="235" text-anchor="middle" class="axis-label" transform="rotate(-90 22 235)">{{ yDefinition?.label }} →</text>
          </svg>
        </div>
        <footer><span>{{ plotRows.length }} complete cases from {{ filteredRows.length }} filtered pitchers · headshots limited to the 200 highest-IP rows</span><span>Each pitcher is weighted equally. Association does not establish causation.</span></footer>
      </section>

      <section class="metric-table-grid" :class="{ merged: activeMetricTables.length === 1 }" aria-label="Metrics related to the selected axes">
        <article v-for="group in activeMetricTables" :key="group.category" class="sample-table">
          <header>
            <div><span>{{ axisBadge(group.category) }}</span><h2>{{ categoryLabel(group.category) }}</h2></div>
            <strong>{{ group.metrics.length }} metrics · {{ plotRows.length }} rows</strong>
          </header>
          <div>
            <table>
              <thead><tr><th>Pitcher</th><th>Team</th><th>Role</th><th>IP</th><th v-for="metric in group.metrics" :key="`head-${group.category}-${metric.key}`" :class="{ selected: selectedMetric(metric.key) }">{{ metric.label }}</th></tr></thead>
              <tbody><tr v-for="row in tableRows(group.sortKey)" :key="`${group.category}-${row.player_id}`"><td><NuxtLink :to="pitcherLink(row)">{{ row.name }}</NuxtLink></td><td>{{ row.team }}</td><td>{{ row.role }}</td><td>{{ formatMetric(row.metrics.ip, 'innings') }}</td><td v-for="metric in group.metrics" :key="`${row.player_id}-${metric.key}`" :class="{ selected: selectedMetric(metric.key) }">{{ formatMetric(metricValue(row, metric.key), metric.unit) }}</td></tr></tbody>
            </table>
          </div>
        </article>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import type { PitcherMetricDefinition, PitcherMetricExplorerRow } from '~/types/api'
import { linearRegression, spearmanCorrelation, type LinearRegressionResult } from '~/utils/linearRegression'
import { Calculator } from '@lucide/vue'

const api = useApi()
const route = useRoute()
const router = useRouter()
const year = ref(Number(route.query.year) || 2026)
const role = ref('All')
const team = ref('All')
const minimumIp = ref(20)
const searchText = ref('')
const xMetric = ref('stuff_plus')
const yMetric = ref('stamina_plus')
const regressionResult = ref<LinearRegressionResult | null>(null)
const spearman = ref<number | null>(null)

const { data: response, pending, error } = await useAsyncData(
  () => `pitcher-metric-explorer-${year.value}`,
  () => api.pitcherMetricExplorer(year.value),
  { watch: [year] }
)

const yearOptions = computed(() => response.value?.available_years.length ? response.value.available_years : [2026, 2025, 2024, 2023, 2022, 2021])
const metricGroups = computed(() => {
  const groups = new Map<string, PitcherMetricDefinition[]>()
  for (const metric of response.value?.metrics || []) groups.set(metric.category, [...(groups.get(metric.category) || []), metric])
  return [...groups.entries()].map(([category, metrics]) => ({ category, metrics }))
})
const xDefinition = computed(() => response.value?.metrics.find(metric => metric.key === xMetric.value))
const yDefinition = computed(() => response.value?.metrics.find(metric => metric.key === yMetric.value))
const activeMetricTables = computed(() => {
  const categories = [xDefinition.value?.category, yDefinition.value?.category].filter((category, index, values): category is string => Boolean(category) && values.indexOf(category) === index)
  return categories.map(category => {
    const selectedKey = yDefinition.value?.category === category ? yMetric.value : xMetric.value
    return {
      category,
      sortKey: selectedKey,
      metrics: (response.value?.metrics || []).filter(metric => metric.category === category && coverageCount(metric.key) > 0),
    }
  })
})
const filteredRows = computed(() => {
  const needle = searchText.value.toLowerCase()
  return (response.value?.rows || []).filter(row =>
    (role.value === 'All' || row.role === role.value)
    && (team.value === 'All' || row.team === team.value)
    && Number(row.metrics.ip || 0) >= Number(minimumIp.value || 0)
    && (!needle || `${row.name} ${row.team}`.toLowerCase().includes(needle))
  )
})
const plotRows = computed(() => filteredRows.value.filter(row => metricValue(row, xMetric.value) != null && metricValue(row, yMetric.value) != null))
const headshotRows = computed(() => plotRows.value.slice().sort((left, right) => Number(right.metrics.ip || 0) - Number(left.metrics.ip || 0)).slice(0, 200))
const headshotIds = computed(() => new Set(headshotRows.value.map(row => row.player_id)))
const xDomain = computed(() => domain(plotRows.value.map(row => metricValue(row, xMetric.value) as number)))
const yDomain = computed(() => domain(plotRows.value.map(row => metricValue(row, yMetric.value) as number)))
const regressionLine = computed(() => {
  if (!regressionResult.value) return null
  const [minX, maxX] = xDomain.value
  return { x1: xPosition(minX), y1: yPosition(regressionResult.value.intercept + regressionResult.value.slope * minX), x2: xPosition(maxX), y2: yPosition(regressionResult.value.intercept + regressionResult.value.slope * maxX) }
})

watch([role, team, minimumIp, searchText, xMetric, yMetric], clearRegression)
watch(year, async () => {
  team.value = 'All'
  clearRegression()
  await router.replace({ query: { ...route.query, year: String(year.value) } })
})
watch(response, selectUsableAxes, { immediate: true })

function selectUsableAxes() {
  if (!response.value) return
  if (coverageCount(xMetric.value) < 3) xMetric.value = bestAvailable(['stuff_plus', 'fip', 'era', 'k_pct'])
  if (coverageCount(yMetric.value) < 3 || yMetric.value === xMetric.value) yMetric.value = bestAvailable(['stamina_plus', 'era', 'whip', 'war'], xMetric.value)
}
function bestAvailable(keys: string[], exclude = '') { return keys.find(key => key !== exclude && coverageCount(key) >= 3) || response.value?.metrics.find(metric => metric.key !== exclude && coverageCount(metric.key) >= 3)?.key || '' }
function coverageCount(key: string) { return filteredRows.value.filter(row => metricValue(row, key) != null).length }
function coverage(key: string) { return coverageCount(key).toLocaleString() }
function metricValue(row: PitcherMetricExplorerRow, key: string) { const value = row.metrics[key]; return typeof value === 'number' && Number.isFinite(value) ? value : null }
function domain(values: number[]): [number, number] { if (!values.length) return [0, 1]; const min = Math.min(...values); const max = Math.max(...values); const span = Math.max(max - min, Math.abs(max) * .05, 1e-6); return [min - span * .08, max + span * .08] }
function xPosition(value: number | null) { const [min, max] = xDomain.value; return 80 + ((Number(value) - min) / Math.max(max - min, 1e-9)) * 780 }
function yPosition(value: number | null) { const [min, max] = yDomain.value; return 440 - ((Number(value) - min) / Math.max(max - min, 1e-9)) * 410 }
function pointRadius(row: PitcherMetricExplorerRow) { return Math.max(10, Math.min(20, 8 + Math.sqrt(Number(row.metrics.ip || 0)) / 2)) }
function tableRows(sortKey: string) { return plotRows.value.slice().sort((left, right) => Number(metricValue(right, sortKey) ?? Number.NEGATIVE_INFINITY) - Number(metricValue(left, sortKey) ?? Number.NEGATIVE_INFINITY)).slice(0, 200) }
function selectedMetric(key: string) { return key === xMetric.value || key === yMetric.value }
function axisBadge(category: string) { const axes = [xDefinition.value?.category === category ? 'X' : '', yDefinition.value?.category === category ? 'Y' : ''].filter(Boolean); return `${axes.join(' + ')} axis` }
function categoryLabel(category: string) { return ({ 'Results & workload': '成績與工作量', 'Standard advanced': '進階數據', 'Petehub Plus': '球質與球路', 'Stamina & stability': '體力與穩定' } as Record<string, string>)[category] || category }
function runRegression() { const points = plotRows.value.map(row => ({ x: metricValue(row, xMetric.value) as number, y: metricValue(row, yMetric.value) as number })); regressionResult.value = linearRegression(points); spearman.value = spearmanCorrelation(points) }
function clearRegression() { regressionResult.value = null; spearman.value = null }
function pValue(value: number) { return value < .001 ? '< 0.001' : value.toFixed(3) }
function headshotUrl(playerId: number) { return `https://img.mlbstatic.com/mlb-photos/image/upload/w_120,q_auto:eco,f_auto/v1/people/${playerId}/headshot/silo/current` }
function pitcherLink(row: PitcherMetricExplorerRow) { return { path: '/pitcher-personal', query: { year: year.value, role: row.role, pitcher_id: row.player_id } } }
function openPitcher(row: PitcherMetricExplorerRow) { navigateTo(pitcherLink(row)) }
function formatMetric(value: number | null | undefined, unit?: string) { if (value == null || !Number.isFinite(Number(value))) return '—'; const numeric = Number(value); if (unit === '%') return `${numeric.toFixed(1)}%`; if (unit === 'pp') return `${numeric.toFixed(1)} pp`; if (unit === 'count') return Math.round(numeric).toLocaleString(); return numeric.toFixed(['rate', 'wins'].includes(unit || '') ? 2 : 1) }
</script>

<style scoped>
.explorer-page { display: grid; gap: 18px; }
.filter-panel { display: grid; grid-template-columns: 130px 150px 150px 150px minmax(220px, 1fr); gap: 12px; align-items: end; border: 1px solid var(--color-border); border-radius: 16px; padding: 16px; background: var(--color-surface); }
label { display: grid; gap: 6px; color: var(--color-muted-text); font-size: 11px; font-weight: 900; letter-spacing: .06em; text-transform: uppercase; }
select, input { width: 100%; min-width: 0; height: 42px; border: 1px solid var(--color-border-strong); border-radius: 10px; padding: 0 11px; color: var(--color-text); background: var(--color-background); font: 700 13px inherit; }
.state-card, .warning-card, .workbench, .sample-table { border: 1px solid var(--color-border); border-radius: 18px; background: var(--color-surface); box-shadow: var(--shadow-sm); }
.state-card { display: grid; gap: 5px; margin: 0; padding: 22px; color: var(--color-muted-text); }
.state-card strong { color: var(--color-text); }.state-card.error { color: #ff8a8a; }
.warning-card { padding: 14px 18px; color: var(--color-muted-text); }.warning-card summary { cursor: pointer; color: var(--color-text); font-weight: 850; }.warning-card p { margin: 9px 0 0; font-size: 12px; }
.source-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }.source-strip article { display: flex; justify-content: space-between; border: 1px solid var(--color-border); border-radius: 12px; padding: 12px 14px; background: var(--color-surface); text-transform: capitalize; }.source-strip span { color: var(--color-muted-text); font-size: 11px; font-weight: 850; }.source-strip strong { color: #ff9d6c; font-size: 11px; text-transform: uppercase; }.source-strip strong.current { color: #6ed7b7; }
.workbench { overflow: hidden; }.workbench > header { display: flex; align-items: end; justify-content: space-between; gap: 18px; padding: 20px; border-bottom: 1px solid var(--color-border); }.workbench header > div:first-child > span, .sample-table header span { color: var(--color-primary); font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }.workbench h2, .sample-table h2 { margin: 4px 0 0; color: var(--color-text); }
.axis-controls { display: grid; grid-template-columns: repeat(2, minmax(190px, 1fr)) auto; gap: 10px; align-items: end; }.axis-controls button { display: inline-flex; align-items: center; justify-content: center; gap: 7px; height: 42px; border: 0; border-radius: 10px; padding: 0 16px; color: var(--color-on-primary); background: var(--color-primary); font-size: 13px; font-weight: 900; white-space: nowrap; cursor: pointer; }.axis-controls button:disabled { opacity: .45; cursor: not-allowed; }
.metric-notes { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--color-border); border-bottom: 1px solid var(--color-border); }.metric-notes p { display: grid; gap: 5px; margin: 0; padding: 14px 20px; color: var(--color-muted-text); background: var(--color-surface); font-size: 12px; }.metric-notes strong { color: var(--color-text); }.metric-notes small { color: var(--color-primary); }
.regression-summary { display: grid; grid-template-columns: repeat(6, minmax(90px, 1fr)) minmax(155px, 1.3fr); gap: 1px; border-bottom: 1px solid var(--color-border); background: var(--color-border); }.regression-summary article { display: grid; gap: 5px; padding: 14px 18px; background: var(--color-surface); }.regression-summary span, .regression-summary small { color: var(--color-muted-text); font-size: 10px; font-weight: 850; text-transform: uppercase; }.regression-summary strong { color: var(--color-text); font: 900 20px "Fira Code", monospace; }.regression-summary .significance.significant strong { color: #6ed7b7; }.regression-summary .significance:not(.significant) strong { color: #ff8a8a; }.regression-summary > p { grid-column: 1 / -1; margin: 0; padding: 9px 18px; color: var(--color-muted-text); background: var(--color-background); font-size: 12px; }
.chart-wrap { overflow-x: auto; padding: 10px 12px 0; }.chart-wrap svg { display: block; width: 100%; min-width: 760px; height: auto; }.plot-background { fill: color-mix(in srgb, var(--color-background) 68%, transparent); stroke: var(--color-border); }.grid-lines line { stroke: color-mix(in srgb, var(--color-border-strong) 52%, transparent); stroke-width: 1; }.regression-line { stroke: var(--color-primary); stroke-width: 3; stroke-dasharray: 10 6; }.pitcher-point { cursor: pointer; outline: none; transform-box: fill-box; transform-origin: center; transition: transform .16s ease; }.pitcher-point circle { fill: var(--color-muted); stroke: var(--color-primary); stroke-width: 2; opacity: .88; }.pitcher-point:hover, .pitcher-point:focus { transform: scale(1.22); }.pitcher-point:hover circle, .pitcher-point:focus circle { opacity: 1; stroke-width: 3; }.axis-label { fill: var(--color-muted-text); font: 800 13px "Fira Code", monospace; }
.workbench footer { display: flex; justify-content: space-between; gap: 20px; padding: 13px 20px; border-top: 1px solid var(--color-border); color: var(--color-muted-text); font-size: 11px; }
.metric-table-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }.metric-table-grid.merged { grid-template-columns: minmax(0, 1fr); }.sample-table { min-width: 0; overflow: hidden; }.sample-table > header { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 17px 20px; border-bottom: 1px solid var(--color-border); }.sample-table > header strong { color: var(--color-muted-text); font-size: 12px; white-space: nowrap; }.sample-table > div { overflow-x: auto; }table { width: 100%; border-collapse: collapse; font-size: 14px; }th, td { padding: 13px 16px; border-bottom: 1px solid var(--color-border); text-align: right; white-space: nowrap; }th { color: var(--color-muted-text); font-size: 12px; text-transform: uppercase; }th.selected { color: var(--color-primary); }td { color: var(--color-muted-text); font: 700 14px "Fira Code", monospace; }td.selected { color: var(--color-text); background: color-mix(in srgb, var(--color-primary) 7%, transparent); }th:first-child, td:first-child { text-align: left; }td a { color: var(--color-text); font-family: inherit; font-weight: 850; text-decoration: none; }td a:hover { color: var(--color-primary); }
@media (max-width: 1100px) { .metric-table-grid { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 1000px) { .filter-panel { grid-template-columns: repeat(2, minmax(0, 1fr)); }.filter-panel .search { grid-column: 1 / -1; }.workbench > header { align-items: stretch; flex-direction: column; }.axis-controls { width: 100%; }.regression-summary { grid-template-columns: repeat(3, 1fr); }.source-strip { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 650px) { .filter-panel, .axis-controls, .metric-notes { grid-template-columns: 1fr; }.filter-panel .search { grid-column: auto; }.regression-summary, .source-strip { grid-template-columns: 1fr 1fr; }.workbench footer { flex-direction: column; } }
</style>
