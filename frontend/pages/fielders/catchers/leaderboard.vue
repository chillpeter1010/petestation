<script setup lang="ts">
import type {
  CatcherDescriptiveDetailResponse,
  CatcherDescriptivePairedDuoResponse,
  CatcherDescriptivePairedDuoRow,
  CatcherDescriptiveRow,
  TablePayload
} from '~/types/api'
import { performanceColorStyle } from '~/utils/performanceColor'

type LeaderboardView = 'catchers' | 'pairs'
type MetricRow = CatcherDescriptiveRow | CatcherDescriptivePairedDuoRow

const api = useApi()
const route = useRoute()
const activeView = ref<LeaderboardView>(route.query.view === 'pairs' ? 'pairs' : 'catchers')
const requestedYear = Number(route.query.year)
const year = ref([2021, 2022, 2023, 2024, 2025, 2026].includes(requestedYear) ? requestedYear : 2021)
const minimumCatcherIp = ref(300)
const minimumPairIp = ref(40)
const team = ref('All')
const search = ref('')
const onlyRankingEligible = ref(true)
const displayMode = ref<'actual' | 'percentile'>('actual')
const heatmapEnabled = ref(true)
const pairData = ref<CatcherDescriptivePairedDuoResponse | null>(null)
const pairDataYear = ref<number | null>(null)
const pairLoading = ref(false)
const pairError = ref('')
let pairRequestId = 0
const expandedDetails = reactive<Record<number, CatcherDescriptiveDetailResponse>>({})
const expandedLoading = reactive<Record<number, boolean>>({})
const expandedErrors = reactive<Record<number, string>>({})
const yearOptions = [2021, 2022, 2023, 2024, 2025, 2026]
const catcherIpOptions = Array.from({ length: 16 }, (_, index) => index * 100)
const pairIpOptions = [0, 40, ...Array.from({ length: 15 }, (_, index) => (index + 1) * 100)]

const { data, pending, error } = await useAsyncData(
  () => `catcher-descriptive-leaderboard-${year.value}`,
  () => api.catcherDescriptiveLeaderboard({ year: year.value }),
  { watch: [year] }
)

async function loadPairData() {
  const requestedYear = year.value
  const requestId = ++pairRequestId
  pairLoading.value = true
  pairError.value = ''
  try {
    const result = await api.catcherDescriptivePairedDuoLeaderboard({ year: requestedYear, minimumOuts: 0 })
    if (requestId === pairRequestId && requestedYear === year.value) {
      pairData.value = result
      pairDataYear.value = requestedYear
    }
  } catch (failure: unknown) {
    if (requestId === pairRequestId) {
      pairError.value = failure instanceof Error ? failure.message : 'Unable to load pitcher-catcher pair metrics.'
    }
  } finally {
    if (requestId === pairRequestId) pairLoading.value = false
  }
}

if (activeView.value === 'pairs') await loadPairData()

function selectView(view: LeaderboardView) {
  activeView.value = view
  team.value = 'All'
  search.value = ''
  if (view === 'pairs' && pairDataYear.value !== year.value) void loadPairData()
}

const pairQualifiedRows = computed(() => {
  const minimumOuts = Math.max(0, Number(minimumPairIp.value || 0) * 3)
  return (pairData.value?.rows || [])
    .filter(row => row.outs >= minimumOuts)
    .map((row, index) => ({ ...row, rank: index + 1 }))
})
const teams = computed(() => {
  const rows = activeView.value === 'catchers' ? (data.value?.rows || []) : pairQualifiedRows.value
  return ['All', ...Array.from(new Set(rows.flatMap(row => row.teams))).sort()]
})
const loadErrorMessage = computed(() => {
  if (activeView.value === 'pairs' && pairError.value) return 'The Paired Duo metrics could not be loaded. Reload the page; if this persists, check the Petehub backend service.'
  const failure = error.value
  if (!failure || typeof failure !== 'object') return ''
  const payload = 'data' in failure && failure.data && typeof failure.data === 'object'
    ? failure.data as Record<string, unknown>
    : null
  const detail = typeof payload?.detail === 'string' ? payload.detail : ''
  if (/artifact|canonical ledger|preview build/i.test(detail)) {
    return 'This season has not completed the canonical ledger and Slice 2–3 preview build yet.'
  }
  const statusCode = 'statusCode' in failure && typeof failure.statusCode === 'number' ? failure.statusCode : null
  if (statusCode === 401) return 'Your session expired. Sign in again, then reload this page.'
  return 'The catcher metrics API could not be reached. Reload the page; if this persists, check the Petehub backend service.'
})
const filteredCatcherRows = computed(() => {
  const query = search.value.trim().toLowerCase()
  const minimumOuts = Math.max(0, Number(minimumCatcherIp.value || 0) * 3)
  return (data.value?.rows || []).filter(row =>
    row.outs >= minimumOuts
    && (!onlyRankingEligible.value || row.ranking_eligible)
    && (team.value === 'All' || row.teams.includes(team.value))
    && (!query || `${row.catcher_name} ${row.team}`.toLowerCase().includes(query))
  )
})
const filteredPairRows = computed(() => {
  const query = search.value.trim().toLowerCase()
  return pairQualifiedRows.value.filter(row =>
    (team.value === 'All' || row.teams.includes(team.value))
    && (!query || `${row.catcher_name} ${row.pitcher_name} ${row.team}`.toLowerCase().includes(query))
  )
})
const activeRows = computed<MetricRow[]>(() => activeView.value === 'catchers' ? filteredCatcherRows.value : filteredPairRows.value)
const activePending = computed(() => activeView.value === 'catchers' ? pending.value : pairLoading.value)
const activeError = computed(() => activeView.value === 'catchers' ? Boolean(error.value) : Boolean(pairError.value))

type PercentileDirection = 'higher' | 'lower'
type PercentileMetric = { field: string; direction: PercentileDirection }
const catcherPercentileMetrics: Record<string, PercentileMetric> = {
  cERA: { field: 'c_era', direction: 'lower' }, cRA9: { field: 'c_ra9', direction: 'lower' },
  cFIP: { field: 'c_fip', direction: 'lower' }, tERA: { field: 't_era', direction: 'lower' },
  tRA9: { field: 't_ra9', direction: 'lower' }, tFIP: { field: 't_fip', direction: 'lower' },
  cxERA: { field: 'cxera', direction: 'lower' }, txERA: { field: 'txera', direction: 'lower' },
  'xR vs Mix': { field: 'x_runs_vs_mix', direction: 'higher' }, cSaveRun: { field: 'c_save_run', direction: 'higher' },
  'cSaveRun/IP': { field: 'c_save_run_per_ip', direction: 'higher' }, FRV: { field: 'frv', direction: 'higher' },
  Throwing: { field: 'throwing', direction: 'higher' }, Blocking: { field: 'blocking', direction: 'higher' },
  Framing: { field: 'framing', direction: 'higher' }
}
const pairPercentileMetrics: Record<string, PercentileMetric> = {
  cERA: { field: 'c_era', direction: 'lower' }, cRA9: { field: 'c_ra9', direction: 'lower' },
  cFIP: { field: 'c_fip', direction: 'lower' }, tERA: { field: 't_era', direction: 'lower' },
  tRA9: { field: 't_ra9', direction: 'lower' }, tFIP: { field: 't_fip', direction: 'lower' },
  xERA: { field: 'xera', direction: 'lower' }, 'Pitcher xERA': { field: 'pitcher_xera', direction: 'lower' },
  'xR vs Mix': { field: 'x_runs_vs_mix', direction: 'higher' }, cSaveRun: { field: 'c_save_run', direction: 'higher' },
  'cSaveRun/IP': { field: 'c_save_run_per_ip', direction: 'higher' }
}

function numericField(row: MetricRow, field: string) {
  const value = (row as unknown as Record<string, unknown>)[field]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}
function buildPercentileMap(rows: MetricRow[], identity: (row: MetricRow) => string, metrics: Record<string, PercentileMetric>) {
  const result = new Map<string, Record<string, number>>()
  for (const [label, metric] of Object.entries(metrics)) {
    const entries = rows
      .map(row => ({ id: identity(row), value: numericField(row, metric.field) }))
      .filter((entry): entry is { id: string; value: number } => entry.value !== null)
      .sort((left, right) => left.value - right.value)
    let index = 0
    while (index < entries.length) {
      let end = index + 1
      while (end < entries.length && entries[end].value === entries[index].value) end += 1
      const rawPercentile = entries.length === 1 ? 50 : (((index + end - 1) / 2) / (entries.length - 1)) * 100
      const percentile = metric.direction === 'lower' ? 100 - rawPercentile : rawPercentile
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
const catcherPercentiles = computed(() => buildPercentileMap(
  (data.value?.rows || []).filter(row => row.ranking_eligible),
  row => String((row as CatcherDescriptiveRow).catcher_id),
  catcherPercentileMetrics
))
const pairPercentiles = computed(() => buildPercentileMap(
  (pairData.value?.rows || []).filter(row => row.outs >= 120),
  row => String((row as CatcherDescriptivePairedDuoRow).pair_key),
  pairPercentileMetrics
))

function weightedAverage(selector: (row: MetricRow) => number | null | undefined) {
  const supported = activeRows.value.filter(row => selector(row) !== null && selector(row) !== undefined && row.outs > 0)
  const outs = supported.reduce((total, row) => total + row.outs, 0)
  return outs ? supported.reduce((total, row) => total + Number(selector(row)) * row.outs, 0) / outs : null
}
function arithmeticAverage(selector: (row: MetricRow) => number | null | undefined) {
  const values = activeRows.value.map(selector).filter((value): value is number => value !== null && value !== undefined)
  return values.length ? values.reduce((total, value) => total + value, 0) / values.length : null
}
const averageCards = computed(() => {
  const totalOuts = activeRows.value.reduce((total, row) => total + row.outs, 0)
  const totalCSaveRun = activeRows.value.reduce((total, row) => total + Number(row.c_save_run || 0), 0)
  return [
    { label: 'cERA', value: number(weightedAverage(row => row.c_era)) },
    { label: 'cRA9', value: number(weightedAverage(row => row.c_ra9)) },
    { label: 'cFIP', value: number(weightedAverage(row => row.c_fip)) },
    { label: 'tERA', value: number(weightedAverage(row => row.t_era)) },
    { label: 'tRA9', value: number(weightedAverage(row => row.t_ra9)) },
    { label: 'tFIP', value: number(weightedAverage(row => row.t_fip)) },
    { label: activeView.value === 'catchers' ? 'cxERA' : 'xERA', value: number(weightedAverage(row => activeView.value === 'catchers' ? (row as CatcherDescriptiveRow).cxera : (row as CatcherDescriptivePairedDuoRow).xera)) },
    { label: activeView.value === 'catchers' ? 'txERA' : 'Pitcher xERA', value: number(weightedAverage(row => activeView.value === 'catchers' ? (row as CatcherDescriptiveRow).txera : (row as CatcherDescriptivePairedDuoRow).pitcher_xera)) },
    { label: 'Avg cSaveRun', value: number(arithmeticAverage(row => row.c_save_run), 2) },
    { label: 'cSaveRun/IP', value: number(totalOuts ? totalCSaveRun / (totalOuts / 3) : null, 3) }
  ]
})

function number(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}
function displayedMetric(percentiles: Record<string, number>, label: string, value: number | null | undefined, digits = 2) {
  if (displayMode.value === 'percentile') {
    const percentile = percentiles[label]
    return Number.isFinite(percentile) ? String(Math.round(percentile)) : '—'
  }
  return number(value, digits)
}
function leaderboardCellStyle(row: Record<string, unknown>, column: { key: string; label: string }) {
  if (!heatmapEnabled.value) return undefined
  const percentiles = row.__percentiles as Record<string, number> | undefined
  const percentile = percentiles?.[column.key]
  return Number.isFinite(percentile) ? performanceColorStyle((Number(percentile) - 50) / 50) : undefined
}
function playerLink(row: Record<string, unknown>) {
  return { path: '/fielders/catchers/lab', query: { year: year.value, catcher_id: Number(row.player_id) } }
}
function catcherLink(catcherId: number) {
  return { path: '/fielders/catchers/lab', query: { year: year.value, catcher_id: catcherId } }
}
function pitcherLink(row: Record<string, unknown>) {
  return { path: '/pitcher-personal', query: { year: year.value, pitcher_id: Number(row.pitcher_id) } }
}
function pitcherPairings(row: Record<string, unknown>) {
  const pitcherId = Number(row.pitcher_id)
  return (pairData.value?.rows || [])
    .filter(pair => pair.pitcher_id === pitcherId)
    .slice()
    .sort((left, right) => right.outs - left.outs)
}
function expandedDetail(row: Record<string, unknown>) {
  return expandedDetails[Number(row.player_id)]
}
async function loadExpandedDetail(row: Record<string, unknown>, expanded: boolean) {
  if (activeView.value !== 'catchers') return
  const id = Number(row.player_id)
  if (!expanded || !id || expandedDetails[id] || expandedLoading[id]) return
  const requestedYear = year.value
  expandedLoading[id] = true
  expandedErrors[id] = ''
  try {
    const result = await api.catcherDescriptiveDetail({ year: requestedYear, catcherId: id })
    if (requestedYear === year.value) expandedDetails[id] = result
  } catch (failure: unknown) {
    expandedErrors[id] = failure instanceof Error ? failure.message : 'Unable to load pitcher pair results.'
  } finally {
    expandedLoading[id] = false
  }
}
watch(year, () => {
  pairRequestId += 1
  pairData.value = null
  pairDataYear.value = null
  pairLoading.value = false
  pairError.value = ''
  team.value = 'All'
  for (const key of Object.keys(expandedDetails)) delete expandedDetails[Number(key)]
  for (const key of Object.keys(expandedLoading)) delete expandedLoading[Number(key)]
  for (const key of Object.keys(expandedErrors)) delete expandedErrors[Number(key)]
  if (activeView.value === 'pairs') void loadPairData()
})
function displayCatcherRow(row: CatcherDescriptiveRow): Record<string, unknown> {
  const percentiles = catcherPercentiles.value.get(String(row.catcher_id)) || {}
  return {
    '#': row.rank ?? '—', Catcher: row.catcher_name, Team: row.team, 'C G': row.games ?? '—', IP: row.display_ip,
    cERA: displayedMetric(percentiles, 'cERA', row.c_era), cRA9: displayedMetric(percentiles, 'cRA9', row.c_ra9),
    cFIP: displayedMetric(percentiles, 'cFIP', row.c_fip), tERA: displayedMetric(percentiles, 'tERA', row.t_era),
    tRA9: displayedMetric(percentiles, 'tRA9', row.t_ra9), tFIP: displayedMetric(percentiles, 'tFIP', row.t_fip),
    cxERA: displayedMetric(percentiles, 'cxERA', row.cxera), txERA: displayedMetric(percentiles, 'txERA', row.txera),
    'xR vs Mix': displayedMetric(percentiles, 'xR vs Mix', row.x_runs_vs_mix, 1),
    cSaveRun: displayedMetric(percentiles, 'cSaveRun', row.c_save_run, 1),
    'cSaveRun/IP': displayedMetric(percentiles, 'cSaveRun/IP', row.c_save_run_per_ip, 3),
    FRV: displayedMetric(percentiles, 'FRV', row.frv, 1), Throwing: displayedMetric(percentiles, 'Throwing', row.throwing, 1),
    Blocking: displayedMetric(percentiles, 'Blocking', row.blocking, 1), Framing: displayedMetric(percentiles, 'Framing', row.framing, 1),
    'FRV Status': row.frv_status ?? '—',
    'No Dom IP': row.non_dominant_ip ?? '—',
    'Dom Δ/IP': number(row.dominant_pair_delta_c_save_run_per_ip, 3), 'Dom Test': row.dominant_pair_sensitivity_status ?? '—',
    'LCO Cov': `${number(row.baseline_coverage_pct, 1)}%`, Pitchers: row.pitchers,
    'Max Pair': `${number(row.max_pitcher_out_share_pct, 1)}%`, 'LCO Status': row.baseline_status,
    player_id: row.catcher_id, __percentiles: percentiles
  }
}
function displayPairRow(row: CatcherDescriptivePairedDuoRow): Record<string, unknown> {
  const percentiles = pairPercentiles.value.get(String(row.pair_key)) || {}
  return {
    '#': row.rank, Catcher: row.catcher_name, Pitcher: row.pitcher_name, Team: row.team, 'P-C G': row.games, IP: row.display_ip,
    cERA: displayedMetric(percentiles, 'cERA', row.c_era), cRA9: displayedMetric(percentiles, 'cRA9', row.c_ra9),
    cFIP: displayedMetric(percentiles, 'cFIP', row.c_fip), tERA: displayedMetric(percentiles, 'tERA', row.t_era),
    tRA9: displayedMetric(percentiles, 'tRA9', row.t_ra9), tFIP: displayedMetric(percentiles, 'tFIP', row.t_fip),
    xERA: displayedMetric(percentiles, 'xERA', row.xera),
    'Pitcher xERA': displayedMetric(percentiles, 'Pitcher xERA', row.pitcher_xera),
    'xR vs Mix': displayedMetric(percentiles, 'xR vs Mix', row.x_runs_vs_mix, 1),
    cSaveRun: displayedMetric(percentiles, 'cSaveRun', row.c_save_run, 1),
    'cSaveRun/IP': displayedMetric(percentiles, 'cSaveRun/IP', row.c_save_run_per_ip, 3),
    'LCO IP': row.lco_display_ip, 'LCO ERA': number(row.lco_era), 'LCO RA9': number(row.lco_ra9),
    'LCO FIP': number(row.lco_fip), 'LCO Status': row.lco_status, player_id: row.catcher_id,
    pitcher_id: row.pitcher_id, pair_key: row.pair_key, __percentiles: percentiles
  }
}
const catcherColumns = ['#', 'Catcher', 'Team', 'C G', 'IP', 'cERA', 'cRA9', 'cFIP', 'tERA', 'tRA9', 'tFIP', 'cxERA', 'txERA', 'xR vs Mix', 'cSaveRun', 'cSaveRun/IP', 'FRV', 'Throwing', 'Blocking', 'Framing', 'FRV Status', 'No Dom IP', 'Dom Δ/IP', 'Dom Test', 'LCO Cov', 'Pitchers', 'Max Pair', 'LCO Status']
const pairColumns = ['#', 'Catcher', 'Pitcher', 'Team', 'P-C G', 'IP', 'cERA', 'cRA9', 'cFIP', 'tERA', 'tRA9', 'tFIP', 'xERA', 'Pitcher xERA', 'xR vs Mix', 'cSaveRun', 'cSaveRun/IP', 'LCO IP', 'LCO ERA', 'LCO RA9', 'LCO FIP', 'LCO Status']
const table = computed<TablePayload>(() => activeView.value === 'catchers'
  ? { columns: catcherColumns.map(key => ({ key, label: key })), rows: filteredCatcherRows.value.map(displayCatcherRow) }
  : { columns: pairColumns.map(key => ({ key, label: key })), rows: filteredPairRows.value.map(displayPairRow) })
</script>

<template>
  <main class="catcher-board-page">
    <ComparisonPageHeader
      eyebrow="Catcher Station · Descriptive metrics"
      title="Catcher Leaderboard"
      description="Raw catcher results and full-season pitcher-mix baselines. Positive cSaveRun means fewer observed runs than the catcher's weighted pitcher mix allowed; it remains an association, not causal catcher value."
      back-to="/fielders/catchers"
      back-label="Catcher Station"
    />

    <aside class="preview-note">
      <strong>{{ year }} preview — observed association, not catcher causal value.</strong>
      <span v-if="data">FIP constant {{ data.fip_constant.toFixed(3) }} · {{ data.summary.ranking_eligible_catchers }} ranking-eligible catchers · generated {{ data.generated_at_utc.slice(0, 10) }}</span>
      <span v-if="activeView === 'catchers' && data?.reliability">Cross-year cSaveRun/IP gate: {{ data.reliability.release_gate_passed ? 'passed' : 'not passed' }} · {{ data.reliability.pooled_cross_year.adjacent_pairs }} adjacent-season pairs · Pearson {{ number(data.reliability.pooled_cross_year.pearson, 3) }}.</span>
      <span v-if="data?.xera">xERA model: Petehub xERA v1 · 2025 final-test MAE {{ number(data.xera.evaluation.final_test_2025?.mae, 3) }} · calibrated against a fingerprinted FanGraphs/Statcast pitcher-season benchmark.</span>
      <span v-if="activeView === 'catchers' && data?.defense">Defense source: {{ data.defense.row_counts.catcher_seasons }} catcher-seasons · {{ data.defense.release_gate_passed ? 'Statcast FRV source gate passed' : 'Statcast FRV source gate not passed' }} · park factor deferred.</span>
      <span v-if="activeView === 'catchers'">Rank eligibility requires 300 catcher innings. Leave-catcher-out (LCO) coverage is shown separately as a diagnostic and does not affect rank eligibility.</span>
      <span v-else>Paired Duo ranks each pitcher-catcher combination using its shared innings; the default display threshold is 40.0 pair innings.</span>
      <span v-if="activeView === 'catchers'">Click a row to inspect every pitcher pairing here, or click the catcher name to open the full Catcher Lab.</span>
      <span v-else>Click either name to open that player's page, or click the row's blank area to inspect that pitcher's results with every catcher. Pair t-metrics are the pitcher's complete official season rates.</span>
    </aside>

    <section class="filters" aria-label="Leaderboard filters">
      <label>Season<select v-model.number="year"><option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option></select></label>
      <label v-if="activeView === 'catchers'">Minimum IP<select v-model.number="minimumCatcherIp"><option v-for="option in catcherIpOptions" :key="option" :value="option">{{ option === 0 ? 'All' : option }}</option></select></label>
      <label v-else>Minimum Pair IP<select v-model.number="minimumPairIp"><option v-for="option in pairIpOptions" :key="option" :value="option">{{ option === 0 ? 'All' : option }}</option></select></label>
      <label>Team<select v-model="team"><option v-for="option in teams" :key="option" :value="option">{{ option }}</option></select></label>
      <label class="search">Search<input v-model.trim="search" type="search" :placeholder="activeView === 'catchers' ? 'Catcher or team' : 'Catcher, pitcher, or team'"></label>
      <label v-if="activeView === 'catchers'" class="check"><input v-model="onlyRankingEligible" type="checkbox">Ranking eligible only</label>
    </section>

    <section v-if="!activePending && !activeError && activeRows.length" class="average-panel" aria-label="Filtered leaderboard averages">
      <header><strong>Filtered averages</strong><span>{{ activeRows.length }} {{ activeView === 'catchers' ? 'catchers' : 'pairs' }} · rate metrics are weighted by outs</span></header>
      <div><article v-for="card in averageCards" :key="card.label"><span>{{ card.label }}</span><strong>{{ card.value }}</strong></article></div>
    </section>

    <DataTable
      :key="`${year}-${activeView}`"
      class="catcher-table"
      :class="{ 'has-error': activeError }"
      :title="`${year} ${activeView === 'catchers' ? 'Catcher Descriptive Leaderboard' : 'Paired Duo'}`"
      :table="table"
      :max-rows="500"
      :empty-text="activePending ? `Loading ${activeView === 'catchers' ? 'catcher' : 'Paired Duo'} metrics…` : activeError ? loadErrorMessage : 'No rows available for the current filters.'"
      link-column="Catcher"
      headshot-column="Catcher"
      :headshot-size="44"
      :link-to="playerLink"
      secondary-link-column="Pitcher"
      secondary-headshot-id-key="pitcher_id"
      :secondary-headshot-size="44"
      :secondary-link-to="pitcherLink"
      :cell-style-for="leaderboardCellStyle"
      expandable
      :row-key="activeView === 'catchers' ? 'player_id' : 'pair_key'"
      @row-toggle="loadExpandedDetail"
    >
      <template #title-extra>
        <div class="table-title-tools">
          <div class="leaderboard-tabs" role="tablist" aria-label="Catcher leaderboard view">
            <button
              type="button"
              role="tab"
              :aria-selected="activeView === 'catchers'"
              :class="{ active: activeView === 'catchers' }"
              @click="selectView('catchers')"
            >Catcher Leaderboard</button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeView === 'pairs'"
              :class="{ active: activeView === 'pairs' }"
              @click="selectView('pairs')"
            >Paired Duo</button>
          </div>
          <div class="display-control">
            <span>Display</span>
            <div class="mode-toggle" role="group" aria-label="Metric display">
              <button type="button" :class="{ active: displayMode === 'actual' }" :aria-pressed="displayMode === 'actual'" @click="displayMode = 'actual'">實際數據</button>
              <button type="button" :class="{ active: displayMode === 'percentile' }" :aria-pressed="displayMode === 'percentile'" @click="displayMode = 'percentile'">PR值</button>
            </div>
          </div>
          <div class="display-control">
            <span>Heat map</span>
            <div class="mode-toggle heat-toggle" role="group" aria-label="Heat map">
              <button type="button" :class="{ active: !heatmapEnabled }" :aria-pressed="!heatmapEnabled" @click="heatmapEnabled = false">Off</button>
              <button type="button" :class="{ active: heatmapEnabled }" :aria-pressed="heatmapEnabled" @click="heatmapEnabled = true">On</button>
            </div>
          </div>
        </div>
      </template>
      <template #expanded="{ row }">
        <div v-if="activeView === 'catchers'" class="pair-preview">
          <p v-if="expandedLoading[Number(row.player_id)]">Loading pitcher pair results…</p>
          <p v-else-if="expandedErrors[Number(row.player_id)]" class="error">{{ expandedErrors[Number(row.player_id)] }}</p>
          <template v-else-if="expandedDetail(row)">
            <header>
              <div><strong>{{ expandedDetail(row)?.catcher.catcher_name }} pitcher pair results</strong><span>{{ expandedDetail(row)?.pitcher_pairs.length }} pitchers</span></div>
              <NuxtLink :to="playerLink(row)">Open full Catcher Lab</NuxtLink>
            </header>
            <div class="pair-scroll">
              <table>
                <thead><tr><th>Pitcher</th><th>Team</th><th>IP</th><th>cERA</th><th>cRA9</th><th>cFIP</th><th>Season ERA</th><th>Season RA9</th><th>Season FIP</th><th>xERA</th><th>Pitcher xERA</th><th>xR vs Mix</th><th>cSaveRun</th><th>cSaveRun/IP</th></tr></thead>
                <tbody><tr v-for="pair in expandedDetail(row)?.pitcher_pairs" :key="pair.pitcher_id">
                  <td><NuxtLink class="pair-person-link" :to="{ path: '/pitcher-personal', query: { year, pitcher_id: pair.pitcher_id } }"><MlbPlayerHeadshot :player-id="pair.pitcher_id" :name="pair.pitcher_name" :size="32" :source-width="160" decorative shape="circle" /><span>{{ pair.pitcher_name }}</span></NuxtLink></td>
                  <td>{{ pair.teams }}</td><td>{{ pair.display_ip }}</td>
                  <td>{{ number(pair.c_era) }}</td><td>{{ number(pair.c_ra9) }}</td><td>{{ number(pair.c_fip) }}</td>
                  <td>{{ number(pair.pitcher_season_era) }}</td><td>{{ number(pair.pitcher_season_ra9) }}</td><td>{{ number(pair.pitcher_season_fip) }}</td>
                  <td>{{ number(pair.xera) }}</td><td>{{ number(pair.pitcher_xera) }}</td><td>{{ number(pair.x_runs_vs_mix, 2) }}</td>
                  <td>{{ number(pair.c_save_run, 2) }}</td><td>{{ number(pair.c_save_run_per_ip, 3) }}</td>
                </tr></tbody>
              </table>
            </div>
          </template>
        </div>
        <div v-else class="pair-preview">
          <header>
            <div><strong>{{ String(row.Pitcher) }} catcher pair results</strong><span>{{ pitcherPairings(row).length }} catchers · all pair samples shown</span></div>
            <NuxtLink :to="pitcherLink(row)">Open Pitcher Personal</NuxtLink>
          </header>
          <div class="pair-scroll">
            <table>
              <thead><tr><th>Catcher</th><th>Team</th><th>P-C G</th><th>IP</th><th>cERA</th><th>cRA9</th><th>cFIP</th><th>tERA</th><th>tRA9</th><th>tFIP</th><th>xERA</th><th>Pitcher xERA</th><th>xR vs Mix</th><th>cSaveRun</th><th>cSaveRun/IP</th></tr></thead>
              <tbody><tr v-for="pair in pitcherPairings(row)" :key="pair.pair_key">
                <td><NuxtLink class="pair-person-link" :to="catcherLink(pair.catcher_id)"><MlbPlayerHeadshot :player-id="pair.catcher_id" :name="pair.catcher_name" :size="32" :source-width="160" decorative shape="circle" /><span>{{ pair.catcher_name }}</span></NuxtLink></td>
                <td>{{ pair.teams.join(', ') }}</td><td>{{ pair.games }}</td><td>{{ pair.display_ip }}</td>
                <td>{{ number(pair.c_era) }}</td><td>{{ number(pair.c_ra9) }}</td><td>{{ number(pair.c_fip) }}</td>
                <td>{{ number(pair.t_era) }}</td><td>{{ number(pair.t_ra9) }}</td><td>{{ number(pair.t_fip) }}</td>
                <td>{{ number(pair.xera) }}</td><td>{{ number(pair.pitcher_xera) }}</td><td>{{ number(pair.x_runs_vs_mix, 2) }}</td>
                <td>{{ number(pair.c_save_run, 2) }}</td><td>{{ number(pair.c_save_run_per_ip, 3) }}</td>
              </tr></tbody>
            </table>
          </div>
        </div>
      </template>
    </DataTable>

    <details class="definitions">
      <summary>Definitions, denominators, and limits</summary>
      <div>
        <p><b>cERA / cRA9:</b> 27 × responsible ER or R ÷ catcher outs. <b>cFIP:</b> standard HR, BB, HBP and K component plus the displayed season constant.</p>
        <p><b>tERA / tRA9 / tFIP:</b> each pitcher's complete official season rate. Catcher Leaderboard weights those rates by catcher-pitcher outs; Paired Duo shows the paired pitcher's rate directly.</p>
        <p><b>cSaveRun:</b> the renamed Runs vs Mix, calculated as (tRA9 − cRA9) × relevant outs ÷ 27 (all catcher outs on the catcher view; shared pair outs on Paired Duo). <b>cSaveRun/IP</b> divides it by the same innings (outs ÷ 3). Neither is annualized or a causal catcher-runs-saved estimate.</p>
        <p><b>xERA:</b> Petehub xERA v1 uses Statcast's per-PA expected-wOBA input and Petehub's frozen 2021–2023 additive calibration to the ERA scale. It is not identical to MLB's published Statcast xERA. <b>cxERA</b> aggregates the PA expected-run numerator caught; <b>txERA</b> weights each handled pitcher's Petehub season xERA by shared outs. <b>xR vs Mix</b> = pitcher-mix expected runs − catcher or pair expected runs over the displayed sample. Positive means fewer expected runs than the full-season pitcher-mix baseline; negative means more. It is an accumulated expected-results association, not actual runs saved or causal catcher value.</p>
        <p><b>FRV:</b> source-provided full-season Statcast Fielding Run Value in runs above the source-defined average. <b>Throwing</b>, <b>Blocking</b>, and <b>Framing</b> are rounded FRV components, so their displayed sum can differ from FRV by one run. FRV is a separate season-catcher defense axis and is not added to cSaveRun or xR vs Mix. Paired Duo allocation and park adjustment are unavailable.</p>
        <p><b>PR / Heat map:</b> PR is an empirical within-season percentile with ties averaged and higher PR always representing the favorable direction for that column. Catcher PR uses only rows with at least 300 innings; Paired Duo PR uses only pairs with at least 40 shared innings. Search, team, and display filters do not change the reference population. Sample-size, coverage, status, and sensitivity fields are not ranked or colored. Red is favorable, blue is unfavorable, and the colors do not turn descriptive associations into causal catcher value.</p>
        <p><b>Reliability:</b> cross-year stability is tested on cSaveRun/IP for catchers with at least 300 innings in both adjacent seasons. <b>No Dom IP</b> removes the most-used pitcher; <b>Dom Δ/IP</b> is the resulting change. A stable dominant-pair test cannot override a failed project-wide cross-year gate.</p>
        <p><b>LCO Cov / LCO Status:</b> the share supported by leave-catcher-out pitcher history, retained only as a sensitivity diagnostic. <b>Max Pair</b> is the largest single pitcher's share. Missing LCO values are not imputed.</p>
      </div>
    </details>
  </main>
</template>

<style scoped>
.catcher-board-page{display:grid;gap:18px;padding:24px}.preview-note,.filters,.average-panel,.definitions{border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface);box-shadow:var(--shadow-sm)}.preview-note{display:grid;gap:7px;border-left:4px solid var(--color-primary);padding:16px 18px}.preview-note strong{font-size:15px}.preview-note span{color:var(--color-text-muted);font-size:13px;line-height:1.45}.filters{display:grid;grid-template-columns:130px 140px 140px minmax(220px,280px) auto;align-items:end;justify-content:start;gap:14px;padding:16px}.filters label{display:grid;min-width:0;gap:7px;color:var(--color-text-muted);font-size:12px;font-weight:800}.filters select,.filters input[type="search"]{box-sizing:border-box;width:100%;min-width:0;min-height:42px;border:1px solid var(--color-border-strong);border-radius:8px;padding:0 11px;color:var(--color-text);background:var(--color-surface)}.filters .check{display:flex;min-height:42px;align-items:center;gap:8px;color:var(--color-text)}.average-panel{overflow:hidden}.average-panel>header{display:flex;justify-content:space-between;gap:12px;padding:13px 16px;border-bottom:1px solid var(--color-border)}.average-panel>header span{color:var(--color-text-muted);font-size:12px}.average-panel>div{display:grid;grid-template-columns:repeat(5,minmax(95px,1fr))}.average-panel article{display:grid;gap:5px;padding:13px 15px;border-right:1px solid var(--color-border);border-bottom:1px solid var(--color-border)}.average-panel article:nth-child(5n){border-right:0}.average-panel article:nth-last-child(-n+5){border-bottom:0}.average-panel article span{color:var(--color-text-muted);font-size:11px;font-weight:800}.average-panel article strong{font-size:18px}.definitions{overflow:hidden}.definitions summary{cursor:pointer;padding:15px 18px;font-weight:850}.definitions>div{display:grid;gap:8px;border-top:1px solid var(--color-border);padding:15px 18px}.definitions p{margin:0;color:var(--color-text-muted);font-size:14px;line-height:1.55}.leaderboard-tabs{display:inline-flex;overflow:hidden;border:1px solid var(--color-border-strong);border-radius:8px;background:var(--color-muted)}.leaderboard-tabs button{min-height:30px;border:0;border-right:1px solid var(--color-border-strong);padding:0 12px;color:var(--color-text-muted);background:transparent;font:inherit;font-size:12px;font-weight:800;cursor:pointer}.leaderboard-tabs button:last-child{border-right:0}.leaderboard-tabs button:hover{color:var(--color-foreground)}.leaderboard-tabs button.active{color:var(--color-surface);background:var(--color-primary)}.leaderboard-tabs button:focus-visible{position:relative;z-index:1;outline:2px solid var(--color-primary);outline-offset:-2px}.catcher-table :deep(table){font-size:14px}.catcher-table :deep(th){font-size:12px}.catcher-table :deep(.table-scroll){max-height:68vh}.catcher-table :deep(td),.catcher-table :deep(th){padding-block:10px}.catcher-table.has-error :deep(.empty){color:#c4473a}.pair-preview{display:grid;gap:12px;padding:16px 18px}.pair-preview>header{display:flex;align-items:center;justify-content:space-between;gap:12px}.pair-preview>header div{display:grid;gap:3px}.pair-preview>header span{color:var(--color-text-muted);font-size:12px}.pair-preview a{color:var(--color-primary);font-weight:800;text-decoration:none}.pair-preview>p{margin:0;color:var(--color-text-muted)}.pair-preview .error{color:#c4473a}.pair-scroll{max-height:360px;overflow:auto;border:1px solid var(--color-border);border-radius:9px}.pair-scroll table{width:100%;border-collapse:collapse;font-size:12px}.pair-scroll th,.pair-scroll td{padding:8px 10px;border-bottom:1px solid var(--color-border);text-align:left;white-space:nowrap}.pair-scroll th{position:sticky;top:0;background:var(--color-muted);z-index:1}@media(max-width:1100px){.average-panel>div{grid-template-columns:repeat(4,minmax(95px,1fr))}.average-panel article{border-right:1px solid var(--color-border);border-bottom:1px solid var(--color-border)}.average-panel article:nth-child(4n){border-right:0}.average-panel article:nth-last-child(-n+2){border-bottom:0}}@media(max-width:900px){.filters{grid-template-columns:repeat(2,minmax(0,1fr))}.filters .search{grid-column:1/-1}}@media(max-width:600px){.catcher-board-page{padding:14px}.filters{grid-template-columns:1fr}.filters .search{grid-column:auto}.average-panel>header{display:grid}.average-panel>div{grid-template-columns:repeat(2,minmax(95px,1fr))}.average-panel article:nth-child(2n){border-right:0}.average-panel article{border-bottom:1px solid var(--color-border)}.leaderboard-tabs{width:100%}.leaderboard-tabs button{flex:1}}
.table-title-tools{display:flex;align-items:end;gap:10px;flex-wrap:wrap}.table-title-tools .leaderboard-tabs button{min-height:36px}.display-control{display:grid;gap:4px}.display-control>span{color:var(--color-text-muted);font-size:9px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.mode-toggle{display:flex;border:1px solid var(--color-border-strong);border-radius:8px;padding:3px;background:var(--color-surface)}.mode-toggle button{min-height:30px;border:0;border-radius:6px;padding:0 10px;color:var(--color-text-muted);background:transparent;font:inherit;font-size:11px;font-weight:850;cursor:pointer}.mode-toggle button.active{color:var(--color-on-primary);background:var(--color-primary)}.mode-toggle button:focus-visible{outline:2px solid var(--color-primary);outline-offset:1px}.heat-toggle{background:linear-gradient(90deg,rgb(45 104 178 / 18%),var(--color-surface) 48%,rgb(211 61 65 / 18%))}.pair-person-link{display:inline-flex;align-items:center;gap:8px}
@media(max-width:760px){.table-title-tools{align-items:stretch;flex-direction:column}.table-title-tools .leaderboard-tabs,.mode-toggle{width:100%}.mode-toggle button{flex:1}}
</style>
