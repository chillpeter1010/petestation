<script setup lang="ts">
import type {
  PerformanceStateLeaderboardResponse,
  PerformanceStateLeaderboardRow,
  PerformanceStatePlayerResponse,
  PerformanceStatePlayerRow,
  PerformanceStateShadowResponse,
  PerformanceStateTarget,
  PerformanceStateV2LabResponse
} from '~/types/api'

const api = useApi()
const year = ref(2026)
const role = ref<'SP' | 'RP'>('SP')
const target = ref<PerformanceStateTarget>('process_collapse')
const minimumForecasts = ref(5)
const search = ref('')
const response = ref<PerformanceStateLeaderboardResponse | null>(null)
const v2Response = ref<PerformanceStateV2LabResponse | null>(null)
const player = ref<PerformanceStatePlayerResponse | null>(null)
const shadow = ref<PerformanceStateShadowResponse | null>(null)
const selectedPitcherId = ref<number | null>(null)
const loading = ref(true)
const playerLoading = ref(false)
const errorMessage = ref('')
type SortDirection = 'asc' | 'desc'
type LeaderboardSortKey = 'rank' | 'pitcher_name' | 'team' | 'latest_probability' | 'season_mean_probability' | 'actual_events' | 'actual_rate' | 'latest_game_date'
type AppearanceSortKey = 'game_date' | 'probability' | 'actual' | 'alerted' | 'forecast' | 'wpa' | 're24' | 'process_score' | 'result_score' | 'regime_filtered_label' | 'gas_har_variance_forecast' | 'evt_extreme_probability'
const leaderboardSort = ref<{ key: LeaderboardSortKey; direction: SortDirection }>({ key: 'latest_probability', direction: 'desc' })
const appearanceSort = ref<{ key: AppearanceSortKey; direction: SortDirection }>({ key: 'game_date', direction: 'desc' })

const targetOptions: Array<{ value: PerformanceStateTarget; label: string; short: string; description: string }> = [
  { value: 'process_collapse', label: 'Process Collapse', short: 'Process', description: 'Stuff+ and Location+ fall into the frozen role-specific collapse tail.' },
  { value: 'result_collapse', label: 'Result Collapse', short: 'Result', description: 'RE24/PA and WPA/LI/PA fall into the frozen role-specific result tail.' },
  { value: 'return_to_baseline', label: 'Return to Baseline', short: 'Return', description: 'After a process collapse, the next same-role appearance returns to at least -0.50.' },
  { value: 'strong_rebound', label: 'Strong Rebound', short: 'Rebound', description: 'After a process collapse, the next same-role appearance reaches at least +0.50.' }
]

const selectedTarget = computed(() => targetOptions.find(item => item.value === target.value) || targetOptions[0])
const filteredRows = computed(() => {
  const query = search.value.trim().toLowerCase()
  const rows = (response.value?.rows || []).filter(row => !query || `${row.pitcher_name} ${row.team || ''}`.toLowerCase().includes(query))
  return sortRecords(rows, row => row[leaderboardSort.value.key], leaderboardSort.value.direction)
})
const validation = computed(() => response.value?.validation)
const gatePassed = computed(() => Boolean(validation.value?.release_gate.passed))
const playerRows = computed(() => (player.value?.rows || []).filter(row => row.role === role.value))
const timelineRows = computed(() => playerRows.value.filter(row => probability(row) !== null))
const appearanceRows = computed(() => sortRecords(timelineRows.value, row => appearanceSortValue(row, appearanceSort.value.key), appearanceSort.value.direction))
const latestPlayerRow = computed(() => timelineRows.value.at(-1) || null)
const performanceMetric = computed(() => target.value === 'result_collapse' ? 'Result Score' : 'Process Score')
const featureImportance = computed(() => response.value?.model.primary_feature_importance || [])
const maxImportance = computed(() => Math.max(...featureImportance.value.map(item => item.importance), 0.0001))
const ablations = computed(() => Object.entries(response.value?.model.validation_ablations || {}).map(([layer, metrics]) => ({ layer, ...metrics })))
const calibrationBins = computed(() => validation.value?.primary.calibration?.bins || [])
const bootstrapApInterval = computed(() => validation.value?.pitcher_cluster_bootstrap.average_precision_delta_95_interval || [])
const shadowMonitor = computed(() => shadow.value?.monitoring?.[role.value]?.[target.value] || null)
const selectedResearchRow = computed(() => v2Response.value?.rows.find(row => row.pitcher_id === selectedPitcherId.value) || null)

watch([year, role, target, minimumForecasts], loadLeaderboard)
onMounted(() => { loadLeaderboard(); loadShadow() })

async function loadShadow() {
  try { shadow.value = await api.performanceStateShadow() }
  catch { shadow.value = null }
}

async function loadLeaderboard() {
  loading.value = true
  errorMessage.value = ''
  player.value = null
  selectedPitcherId.value = null
  try {
    try {
      v2Response.value = await api.performanceStateV2Lab({
        year: year.value,
        role: role.value,
        target: target.value,
        minimumForecasts: minimumForecasts.value
      })
      response.value = toLegacyResponse(v2Response.value)
    } catch {
      v2Response.value = null
      response.value = await api.performanceStateLeaderboard({
        year: year.value,
        role: role.value,
        target: target.value,
        minimumForecasts: minimumForecasts.value
      })
    }
    const first = response.value.rows[0]
    if (first) await selectPitcher(first)
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load Performance State research.'
  } finally {
    loading.value = false
  }
}

function toLegacyResponse(v2: PerformanceStateV2LabResponse): PerformanceStateLeaderboardResponse {
  const selection = (v2.primary_source.selection || {}) as Record<string, any>
  const metric = (value: unknown) => value && typeof value === 'object' ? value : {}
  const primary = metric(selection.external)
  const baseline = metric(selection.baseline)
  const challenger = metric(selection.xgboost_challenger)
  const gate = metric(selection.release_gate)
  const fixed = metric(selection.fixed_false_alert_metrics)
  const bootstrap = metric(selection.pitcher_cluster_bootstrap)
  return {
    year: v2.year,
    role: v2.role,
    target: v2.target as PerformanceStateTarget,
    target_label: v2.target_label,
    model_version: v2.model_version,
    status: v2.status,
    data_as_of: v2.data_as_of,
    evaluation_status: v2.evaluation_status,
    selected_primary_layer: v2.selected_primary_layer,
    model: {
      eligible_development_rows: Number(selection.development_rows || 0),
      split_rows: {},
      selected_primary_layer: v2.selected_primary_layer,
      selected_features: Array.isArray(selection.selected_features) ? selection.selected_features : [],
      validation_ablations: (selection.validation_ablations || {}) as any,
      validation_xgboost_challenger: challenger as any,
      primary_feature_importance: [],
      xgboost_feature_importance: [],
      fixed_false_alert_threshold: Number(selection.fixed_false_alert_threshold || 0)
    },
    validation: {
      external_rows: Number((primary as any).rows || 0),
      primary: primary as any,
      development_prevalence_baseline: baseline as any,
      xgboost_challenger: challenger as any,
      fixed_false_alert_metrics: {
        threshold: Number((fixed as any).threshold || 0),
        alert_rate: Number((fixed as any).alert_rate || 0),
        recall: Number((fixed as any).recall || 0),
        false_alert_rate: Number((fixed as any).false_alert_rate || 0)
      },
      pitcher_cluster_bootstrap: {
        requested_samples: Number((bootstrap as any).requested_samples || 0),
        successful_samples: Number((bootstrap as any).successful_samples || 0),
        average_precision_delta_95_interval: ((bootstrap as any).average_precision_delta_95_interval || []) as Array<number | null>,
        brier_delta_95_interval: ((bootstrap as any).brier_delta_95_interval || []) as Array<number | null>
      },
      release_gate: {
        average_precision_gain: Number((gate as any).average_precision_gain || 0),
        minimum_average_precision_gain: Number((gate as any).minimum_average_precision_gain || 0),
        brier_not_worse: Boolean((gate as any).brier_not_worse),
        log_loss_not_worse: Boolean((gate as any).log_loss_not_worse),
        passed: Boolean((gate as any).passed)
      }
    },
    rows: v2.rows,
    warnings: v2.warnings
  }
}

async function selectPitcher(row: PerformanceStateLeaderboardRow) {
  selectedPitcherId.value = row.pitcher_id
  playerLoading.value = true
  try {
    player.value = await api.performanceStatePlayer({ year: year.value, pitcherId: row.pitcher_id, role: role.value })
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load this pitcher timeline.'
  } finally {
    playerLoading.value = false
  }
}

function probability(row: PerformanceStatePlayerRow): number | null {
  const value = row[`${target.value}_probability` as keyof PerformanceStatePlayerRow]
  return typeof value === 'number' ? value : null
}

function actual(row: PerformanceStatePlayerRow): boolean {
  return Boolean(row[target.value as keyof PerformanceStatePlayerRow])
}

function predicted(row: PerformanceStatePlayerRow): boolean {
  return Boolean(row[`${target.value}_alert` as keyof PerformanceStatePlayerRow])
}

function forecastPerformance(row: PerformanceStatePlayerRow): number | null {
  if (target.value === 'result_collapse') return finite(row.result_state_forecast)
  const values = [finite(row.stuff_state_forecast), finite(row.command_state_forecast)].filter((value): value is number => value !== null)
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
}

function finite(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function sortRecords<T>(rows: T[], value: (row: T) => unknown, direction: SortDirection) {
  const multiplier = direction === 'asc' ? 1 : -1
  return [...rows].sort((left, right) => {
    const a = value(left)
    const b = value(right)
    if (a === null || a === undefined || a === '') return b === null || b === undefined || b === '' ? 0 : 1
    if (b === null || b === undefined || b === '') return -1
    if (typeof a === 'number' && typeof b === 'number') return (a - b) * multiplier
    if (typeof a === 'boolean' && typeof b === 'boolean') return (Number(a) - Number(b)) * multiplier
    return String(a).localeCompare(String(b), undefined, { numeric: true }) * multiplier
  })
}

function appearanceSortValue(row: PerformanceStatePlayerRow, key: AppearanceSortKey) {
  if (key === 'probability') return probability(row)
  if (key === 'actual') return actual(row)
  if (key === 'alerted') return predicted(row)
  if (key === 'forecast') return forecastPerformance(row)
  return row[key as keyof PerformanceStatePlayerRow]
}

function toggleLeaderboardSort(key: LeaderboardSortKey) {
  leaderboardSort.value = { key, direction: leaderboardSort.value.key === key && leaderboardSort.value.direction === 'desc' ? 'asc' : 'desc' }
}

function toggleAppearanceSort(key: AppearanceSortKey) {
  appearanceSort.value = { key, direction: appearanceSort.value.key === key && appearanceSort.value.direction === 'desc' ? 'asc' : 'desc' }
}

function sortMark(current: { key: string; direction: SortDirection }, key: string) {
  return current.key === key ? (current.direction === 'asc' ? '↑' : '↓') : '↕'
}

function pct(value: number | null | undefined, digits = 1) {
  return typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : '—'
}

function decimal(value: number | null | undefined, digits = 3) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—'
}

function integer(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? Math.round(value).toLocaleString() : '—'
}

function numberValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function stringValue(value: unknown): string {
  return typeof value === 'string' && value.length ? value.replaceAll('_', ' ') : '—'
}

function layerLabel(value: string) {
  return value.replace(/^[A-F]_/, '').replaceAll('_', ' ')
}

function featureLabel(value: string) {
  return value.replaceAll('_', ' ')
}

function playerLink(row: PerformanceStateLeaderboardRow) {
  return { path: '/pitcher-personal', query: { year: year.value, role: row.role, team: row.team || '', pitcher_id: row.pitcher_id } }
}
</script>

<template>
  <main class="state-lab">
    <ComparisonPageHeader
      eyebrow="Pitcher Lab · Performance state"
      title="Performance State Lab"
      description="Research-only collapse and rebound forecasts, validation gates, and completed-appearance timelines."
      back-to="/lab"
      back-label="Pitcher Lab"
    />

    <section class="research-banner" :class="gatePassed ? 'is-pass' : 'is-fail'">
      <div>
        <span>Slice 10 · Research status</span>
        <h2>{{ gatePassed ? 'This role-target pair passed the amended 2026 diagnostic' : 'This role-target pair did not pass the release gate' }}</h2>
        <p>Research display only · no composite score · no injury interpretation · no next-game forecast</p>
      </div>
      <strong>{{ gatePassed ? 'PASSED' : 'NOT RELEASED' }}</strong>
    </section>

    <section class="controls" aria-label="Performance State filters">
      <label>Season<select v-model.number="year"><option :value="2026">2026</option><option :value="2025">2025</option></select></label>
      <fieldset><legend>Role</legend><button v-for="item in ['SP', 'RP'] as const" :key="item" type="button" :class="{ active: role === item }" @click="role = item">{{ item }}</button></fieldset>
      <label>Target<select v-model="target"><option v-for="item in targetOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
      <label>Minimum forecasts<input v-model.number="minimumForecasts" type="number" min="1" max="100"></label>
      <label class="search-control">Search<input v-model.trim="search" type="search" placeholder="Pitcher or team"></label>
    </section>

    <p v-if="errorMessage" class="state-message is-error">{{ errorMessage }}</p>
    <p v-if="loading" class="state-message">Loading frozen forecast artifacts…</p>

    <template v-if="response && !loading">
      <section class="context-panel">
        <div><span>{{ response.role }} · {{ response.target_label }}</span><h2>{{ selectedTarget.description }}</h2></div>
        <dl>
          <div><dt>Data through</dt><dd>{{ response.data_as_of || '—' }}</dd></div>
          <div><dt>Selected layer</dt><dd>{{ layerLabel(response.selected_primary_layer) }}</dd></div>
          <div><dt>Evaluation</dt><dd>{{ response.evaluation_status.replaceAll('_', ' ') }}</dd></div>
          <div><dt>Model</dt><dd>{{ response.model_version }}</dd></div>
        </dl>
      </section>

      <section v-if="v2Response" class="v2-lab-panel">
        <div class="v2-lab-heading">
          <div><span>Slice 14 primary · Slice 18/19 shadow</span><h2>Research model is synchronized in Lab</h2></div>
          <strong>LAB ONLY</strong>
        </div>
        <div class="v2-lab-grid">
          <article><span>Primary</span><strong>{{ layerLabel(v2Response.selected_primary_layer) }}</strong><small>{{ v2Response.primary_source.artifact }}</small></article>
          <article><span>Slice 18 shadow</span><strong>{{ integer(numberValue(v2Response.shadow.slice18?.prediction_rows)) }}</strong><small>partial-pooling challenger rows</small></article>
          <article><span>Slice 19 shadow</span><strong>{{ integer(numberValue(v2Response.shadow.slice19?.prediction_rows)) }}</strong><small>workload-bias challenger rows</small></article>
          <article><span>Selected pitcher latest Δ</span><strong>{{ decimal(selectedResearchRow?.shadow_slice18_delta) }}</strong><small>Slice 18 − Slice 14; Slice 19 {{ decimal(selectedResearchRow?.shadow_slice19_delta) }}</small></article>
          <article><span>Slice 22 freeze</span><strong>{{ stringValue(v2Response.freeze_decision.decision) }}</strong><small>Research decision only; production gate remains closed</small></article>
        </div>
        <p class="v2-lab-note">The board below uses Slice 14 probabilities. Shadow deltas are diagnostic only; formal leaderboards and production player pages are unchanged.</p>
      </section>

      <section class="metric-grid" aria-label="External validation metrics">
        <article><span>Primary AP</span><strong>{{ decimal(validation?.primary.average_precision) }}</strong><small>baseline {{ decimal(validation?.development_prevalence_baseline.average_precision) }}</small></article>
        <article><span>AP gain</span><strong>{{ decimal(validation?.release_gate.average_precision_gain) }}</strong><small>gate ≥ {{ decimal(validation?.release_gate.minimum_average_precision_gain) }}</small></article>
        <article><span>Brier score</span><strong>{{ decimal(validation?.primary.brier) }}</strong><small>{{ validation?.release_gate.brier_not_worse ? 'not worse than baseline' : 'failed baseline comparison' }}</small></article>
        <article><span>Log loss</span><strong>{{ decimal(validation?.primary.log_loss) }}</strong><small>{{ validation?.release_gate.log_loss_not_worse ? 'not worse than baseline' : 'failed baseline comparison' }}</small></article>
        <article><span>Alert recall</span><strong>{{ pct(validation?.fixed_false_alert_metrics.recall) }}</strong><small>FPR {{ pct(validation?.fixed_false_alert_metrics.false_alert_rate) }}</small></article>
        <article><span>XGBoost AP</span><strong>{{ decimal(validation?.xgboost_challenger.average_precision) }}</strong><small>challenger only</small></article>
      </section>

      <section class="analysis-grid">
        <article class="panel">
          <header><div><span>2025 validation</span><h2>Feature-layer ablation</h2></div><small>Chronological validation only</small></header>
          <div class="table-scroll"><table><thead><tr><th>Layer</th><th>Rows</th><th>AP</th><th>Brier</th><th>Log loss</th></tr></thead><tbody>
            <tr v-for="row in ablations" :key="row.layer" :class="{ selected: row.layer === response.selected_primary_layer }"><td><strong>{{ layerLabel(row.layer) }}</strong></td><td>{{ integer(row.rows) }}</td><td>{{ decimal(row.average_precision) }}</td><td>{{ decimal(row.brier) }}</td><td>{{ decimal(row.log_loss) }}</td></tr>
          </tbody></table></div>
        </article>
        <article class="panel importance-panel">
          <header><div><span>Selected primary</span><h2>Standardized influence</h2></div><small>Absolute logistic coefficient</small></header>
          <div class="importance-list">
            <div v-for="item in featureImportance" :key="item.feature"><span>{{ featureLabel(item.feature) }}</span><i><b :style="{ width: `${(item.importance / maxImportance) * 100}%` }" /></i><strong>{{ decimal(item.importance) }}</strong></div>
          </div>
        </article>
      </section>

      <section class="panel calibration-panel">
        <header><div><span>Probability audit</span><h2>External calibration &amp; uncertainty</h2></div><small>2026 amended diagnostic · pitcher-cluster bootstrap</small></header>
        <div class="calibration-summary">
          <article><span>ECE</span><strong>{{ decimal(validation?.primary.calibration?.ece) }}</strong><small>lower is better</small></article>
          <article><span>Calibration slope</span><strong>{{ decimal(validation?.primary.calibration?.slope) }}</strong><small>ideal = 1.000</small></article>
          <article><span>AP gain 95% interval</span><strong>{{ decimal(bootstrapApInterval[0]) }} to {{ decimal(bootstrapApInterval[1]) }}</strong><small>{{ validation?.pitcher_cluster_bootstrap.successful_samples || 0 }} successful pitcher bootstraps</small></article>
        </div>
        <div class="calibration-bars" aria-label="Predicted probability versus observed event rate by probability bin">
          <div v-for="(bin, index) in calibrationBins" :key="index">
            <span>Bin {{ index + 1 }} <small>n={{ bin.rows }}</small></span>
            <div><i class="predicted" :style="{ width: `${Math.min(bin.mean_probability * 100, 100)}%` }" /><i class="observed" :style="{ width: `${Math.min(bin.observed_rate * 100, 100)}%` }" /></div>
            <strong>{{ pct(bin.mean_probability) }} / {{ pct(bin.observed_rate) }}</strong>
          </div>
        </div>
        <p class="calibration-legend"><span><i class="predicted" />Predicted</span><span><i class="observed" />Observed</span></p>
      </section>

      <section class="panel leaderboard-panel">
        <header><div><span>Completed-appearance research board</span><h2>{{ response.year }} {{ response.role }} · {{ response.target_label }}</h2></div><small>{{ filteredRows.length }} pitchers</small></header>
        <p class="board-note">Sorted by each pitcher's latest evaluated pre-appearance probability. It is not a forecast for their next scheduled game.</p>
        <div class="table-scroll leaderboard-scroll"><table><thead><tr>
          <th><button type="button" @click="toggleLeaderboardSort('rank')"># {{ sortMark(leaderboardSort, 'rank') }}</button></th>
          <th><button type="button" @click="toggleLeaderboardSort('pitcher_name')">Pitcher {{ sortMark(leaderboardSort, 'pitcher_name') }}</button></th>
          <th><button type="button" @click="toggleLeaderboardSort('team')">Team {{ sortMark(leaderboardSort, 'team') }}</button></th>
          <th><button type="button" @click="toggleLeaderboardSort('latest_probability')">Latest forecast {{ sortMark(leaderboardSort, 'latest_probability') }}</button></th>
          <th><button type="button" @click="toggleLeaderboardSort('season_mean_probability')">Season mean {{ sortMark(leaderboardSort, 'season_mean_probability') }}</button></th>
          <th><button type="button" @click="toggleLeaderboardSort('actual_events')">Events {{ sortMark(leaderboardSort, 'actual_events') }}</button></th>
          <th><button type="button" @click="toggleLeaderboardSort('actual_rate')">Actual rate {{ sortMark(leaderboardSort, 'actual_rate') }}</button></th>
          <th><button type="button" @click="toggleLeaderboardSort('latest_game_date')">Last evaluated {{ sortMark(leaderboardSort, 'latest_game_date') }}</button></th>
        </tr></thead><tbody>
          <tr v-for="row in filteredRows" :key="`${row.role}-${row.pitcher_id}`" :class="{ selected: selectedPitcherId === row.pitcher_id }" tabindex="0" @click="selectPitcher(row)" @keydown.enter="selectPitcher(row)" @keydown.space.prevent="selectPitcher(row)">
            <td>{{ row.rank }}</td>
            <td><div class="pitcher-cell"><MlbPlayerHeadshot :player-id="row.pitcher_id" :name="row.pitcher_name" :size="42" :source-width="160" decorative shape="circle" /><span><strong>{{ row.pitcher_name }}</strong><NuxtLink :to="playerLink(row)" @click.stop>Open personal page ↗</NuxtLink></span></div></td>
            <td>{{ row.team || '—' }}</td><td><strong>{{ pct(row.latest_probability) }}</strong><small :class="row.latest_actual ? 'event-hit' : ''">{{ row.latest_actual ? 'event occurred' : 'no event' }}</small></td><td>{{ pct(row.season_mean_probability) }}</td><td>{{ row.actual_events }} / {{ row.eligible_forecasts }}</td><td>{{ pct(row.actual_rate) }}</td><td>{{ row.latest_game_date }}</td>
          </tr>
        </tbody></table></div>
        <p v-if="!filteredRows.length" class="empty-state">No pitchers match these filters.</p>
      </section>

      <section v-if="selectedPitcherId" class="panel player-panel">
        <header>
          <div><span>Player timeline</span><h2>{{ player?.pitcher_name || 'Loading pitcher…' }}</h2></div>
          <small>{{ role }} · {{ performanceMetric }} · {{ timelineRows.length }} eligible appearances · v1 fallback timeline</small>
        </header>
        <p v-if="playerLoading" class="state-message">Loading player states…</p>
        <template v-else-if="player && latestPlayerRow">
          <div class="latest-strip">
            <article><span>Latest probability</span><strong>{{ pct(probability(latestPlayerRow)) }}</strong></article>
            <article><span>Observed event</span><strong>{{ actual(latestPlayerRow) ? 'Yes' : 'No' }}</strong></article>
            <article><span>Filtered regime</span><strong>{{ latestPlayerRow.regime_filtered_label || '—' }}</strong></article>
            <article><span>GAS+HAR variance</span><strong>{{ decimal(latestPlayerRow.gas_har_variance_forecast) }}</strong></article>
            <article><span>EVT extreme risk</span><strong>{{ pct(latestPlayerRow.evt_extreme_probability) }}</strong><small>{{ latestPlayerRow.evt_tail_supported ? 'GPD tail supported' : 'empirical support' }}</small></article>
          </div>
          <PerformanceStateTimelineChart :rows="timelineRows" :target="target" :metric-label="performanceMetric" />
          <div class="table-scroll appearance-scroll"><table><thead><tr>
            <th><button type="button" @click="toggleAppearanceSort('game_date')">Date {{ sortMark(appearanceSort, 'game_date') }}</button></th>
            <th><button type="button" @click="toggleAppearanceSort('probability')">Probability {{ sortMark(appearanceSort, 'probability') }}</button></th>
            <th><button type="button" @click="toggleAppearanceSort('actual')">Actual {{ sortMark(appearanceSort, 'actual') }}</button></th>
            <th><button type="button" @click="toggleAppearanceSort('alerted')">Alert {{ sortMark(appearanceSort, 'alerted') }}</button></th>
            <th><button type="button" @click="toggleAppearanceSort('forecast')">Forecast {{ sortMark(appearanceSort, 'forecast') }}</button></th>
            <th><button type="button" @click="toggleAppearanceSort('wpa')">WPA {{ sortMark(appearanceSort, 'wpa') }}</button></th>
            <th><button type="button" @click="toggleAppearanceSort('re24')">RE24 {{ sortMark(appearanceSort, 're24') }}</button></th>
            <th><button type="button" @click="toggleAppearanceSort('process_score')">Process {{ sortMark(appearanceSort, 'process_score') }}</button></th>
            <th><button type="button" @click="toggleAppearanceSort('result_score')">Result {{ sortMark(appearanceSort, 'result_score') }}</button></th>
            <th><button type="button" @click="toggleAppearanceSort('regime_filtered_label')">Regime {{ sortMark(appearanceSort, 'regime_filtered_label') }}</button></th>
            <th><button type="button" @click="toggleAppearanceSort('gas_har_variance_forecast')">GAS+HAR {{ sortMark(appearanceSort, 'gas_har_variance_forecast') }}</button></th>
            <th><button type="button" @click="toggleAppearanceSort('evt_extreme_probability')">EVT {{ sortMark(appearanceSort, 'evt_extreme_probability') }}</button></th>
          </tr></thead><tbody>
            <tr v-for="row in appearanceRows" :key="row.game_pk"><td>{{ row.game_date }}</td><td><strong>{{ pct(probability(row)) }}</strong></td><td><span class="event-chip" :class="{ active: actual(row) }">{{ actual(row) ? 'Event' : 'No' }}</span></td><td>{{ predicted(row) ? 'Yes' : 'No' }}</td><td>{{ decimal(forecastPerformance(row)) }}</td><td>{{ decimal(row.wpa) }}</td><td>{{ decimal(row.re24) }}</td><td>{{ decimal(row.process_score) }}</td><td>{{ decimal(row.result_score) }}</td><td>{{ row.regime_filtered_label || '—' }}</td><td>{{ decimal(row.gas_har_variance_forecast) }}</td><td>{{ pct(row.evt_extreme_probability) }}</td></tr>
          </tbody></table></div>
        </template>
      </section>

      <section v-if="shadow && year === shadow.evaluation_year" class="panel shadow-panel">
        <header><div><span>Slice 11 · Shadow monitoring</span><h2>{{ shadow.evaluation_year }} frozen prediction ledger</h2></div><small>{{ shadow.dataset_status }} · {{ shadow.observation_mode.replaceAll('_', ' ') }}</small></header>
        <div class="shadow-grid">
          <article><span>Immutable records</span><strong>{{ integer(shadow.ledger_rows) }}</strong><small>{{ integer(shadow.prospective_rows) }} truly prospective rows</small></article>
          <article><span>{{ role }} {{ selectedTarget.short }} hits</span><strong>{{ integer(shadowMonitor?.confusion.hits) }}</strong><small>{{ integer(shadowMonitor?.confusion.misses) }} misses</small></article>
          <article><span>False alerts</span><strong>{{ integer(shadowMonitor?.confusion.false_alerts) }}</strong><small>{{ integer(shadowMonitor?.confusion.correct_negatives) }} correct negatives</small></article>
          <article><span>Integration gate</span><strong>{{ shadow.integration_gate.eligible ? 'OPEN' : 'CLOSED' }}</strong><small>requires untouched {{ shadow.integration_gate.required_untouched_year }}</small></article>
        </div>
        <p class="shadow-note">{{ shadow.integration_gate.reason }}</p>
      </section>
      <section v-else-if="shadow" class="panel shadow-panel">
        <header><div><span>Slice 11 · Shadow monitoring</span><h2>No {{ year }} shadow ledger</h2></div><small>available for {{ shadow.evaluation_year }} only</small></header>
        <p class="shadow-note">The immutable monitoring ledger is deliberately scoped to its evaluation season; historical development rows are not presented as prospective monitoring.</p>
      </section>

      <section class="warnings-panel"><h2>Interpretation limits</h2><p v-for="warning in response.warnings" :key="warning">{{ warning }}</p><p v-if="year === 2025">2025 is the development season; its board includes model-development observations and is not an external validation ranking.</p></section>
    </template>
  </main>
</template>

<style scoped>
.state-lab { display: grid; gap: 18px; }
.research-banner, .controls, .context-panel, .panel, .warnings-panel { border: 1px solid var(--color-border); border-radius: 0; background: var(--color-surface); }
.research-banner { display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 18px 20px; border-left: 5px solid #c85d4b; }
.research-banner.is-pass { border-left-color: #5fa77b; }
.v2-lab-panel { border: 1px solid var(--color-border); border-left: 5px solid var(--color-primary); padding: 18px 20px; background: var(--color-surface); }
.v2-lab-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
.v2-lab-heading span { color: var(--color-primary); font-size: 13px; font-weight: 900; text-transform: uppercase; }
.v2-lab-heading h2 { margin: 5px 0 0; font-size: 22px; }
.v2-lab-heading > strong { color: var(--color-primary); font-size: 13px; letter-spacing: .08em; }
.v2-lab-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-top: 16px; }
.v2-lab-grid article { border: 1px solid var(--color-border); padding: 13px; background: var(--color-background); }
.v2-lab-grid span { display: block; color: var(--color-muted-text); font-size: 12px; font-weight: 850; text-transform: uppercase; }
.v2-lab-grid strong { display: block; margin-top: 7px; font-size: 18px; overflow-wrap: anywhere; }
.v2-lab-grid small, .v2-lab-note { color: var(--color-muted-text); line-height: 1.4; }
.v2-lab-grid small { display: block; margin-top: 5px; }
.v2-lab-note { margin: 14px 0 0; }
.research-banner span, .panel header span, .context-panel > div > span { color: var(--color-primary); font-size: 13px; font-weight: 900; text-transform: uppercase; }
.research-banner h2, .context-panel h2, .panel h2 { margin: 5px 0 0; font-size: 22px; }
.research-banner p { margin: 7px 0 0; color: var(--color-muted-text); font-size: 15px; }
.research-banner > strong { border: 1px solid currentColor; padding: 8px 12px; color: #e39a8c; font-size: 14px; white-space: nowrap; }
.research-banner.is-pass > strong { color: #82c79d; }
.controls { display: grid; grid-template-columns: 130px 150px minmax(220px, 1fr) 170px minmax(220px, 1fr); gap: 14px; padding: 16px; }
.controls label, .controls fieldset { display: grid; gap: 7px; margin: 0; border: 0; padding: 0; color: var(--color-muted-text); font-size: 13px; font-weight: 850; text-transform: uppercase; }
.controls legend { margin-bottom: 7px; }
.controls select, .controls input { min-height: 44px; width: 100%; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 12px; color: var(--color-foreground); background: var(--color-background); font: inherit; text-transform: none; }
.controls fieldset { grid-template-columns: 1fr 1fr; }
.controls fieldset legend { grid-column: 1 / -1; }
.controls button { min-height: 44px; border: 1px solid var(--color-border-strong); border-radius: 0; color: var(--color-muted-text); background: var(--color-background); font-weight: 900; }
.controls button.active { border-color: var(--color-primary); color: var(--color-on-primary); background: var(--color-primary); }
.state-message { margin: 0; border: 1px solid var(--color-border); padding: 18px; color: var(--color-muted-text); background: var(--color-surface); font-size: 16px; }
.state-message.is-error { color: #ffad9f; }
.context-panel { display: grid; grid-template-columns: minmax(280px, 1.2fr) minmax(520px, 2fr); gap: 20px; padding: 20px; }
.context-panel dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin: 0; background: var(--color-border); }
.context-panel dl div { padding: 12px; background: var(--color-background); }
.context-panel dt { color: var(--color-muted-text); font-size: 12px; font-weight: 800; text-transform: uppercase; }
.context-panel dd { margin: 6px 0 0; overflow-wrap: anywhere; font-size: 14px; font-weight: 800; }
.metric-grid, .latest-strip { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
.metric-grid article, .latest-strip article { border: 1px solid var(--color-border); padding: 15px; background: var(--color-surface); }
.metric-grid span, .latest-strip span { color: var(--color-muted-text); font-size: 12px; font-weight: 850; text-transform: uppercase; }
.metric-grid strong, .latest-strip strong { display: block; margin-top: 8px; font-size: 25px; }
.metric-grid small, .latest-strip small { display: block; margin-top: 5px; color: var(--color-muted-text); line-height: 1.35; }
.analysis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.panel { min-width: 0; }
.panel > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 17px 18px; border-bottom: 1px solid var(--color-border); }
.panel > header small { color: var(--color-muted-text); font-size: 13px; }
.table-scroll { overflow: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 12px 14px; border-bottom: 1px solid var(--color-border); text-align: left; white-space: nowrap; }
th { color: var(--color-muted-text); font-size: 12px; text-transform: uppercase; }
th button { display: inline-flex; align-items: center; gap: 5px; border: 0; padding: 0; color: inherit; background: transparent; font: inherit; font-weight: 850; text-transform: inherit; cursor: pointer; }
th button:hover, th button:focus-visible { color: var(--color-foreground); outline: none; text-decoration: underline; text-underline-offset: 4px; }
tr.selected { background: color-mix(in srgb, var(--color-primary) 10%, transparent); }
.importance-list { display: grid; gap: 11px; padding: 18px; }
.importance-list > div { display: grid; grid-template-columns: minmax(170px, 1fr) 2fr 64px; align-items: center; gap: 12px; font-size: 14px; }
.importance-list span { overflow: hidden; text-overflow: ellipsis; text-transform: capitalize; }
.importance-list i { height: 10px; background: var(--color-background); }
.importance-list b { display: block; height: 100%; background: var(--color-primary); }
.importance-list strong { text-align: right; }
.calibration-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; padding: 16px 18px 8px; }
.calibration-summary article { border: 1px solid var(--color-border); padding: 14px; background: var(--color-background); }
.calibration-summary span { color: var(--color-muted-text); font-size: 12px; font-weight: 850; text-transform: uppercase; }
.calibration-summary strong { display: block; margin-top: 7px; font-size: 21px; }
.calibration-summary small { display: block; margin-top: 4px; color: var(--color-muted-text); }
.calibration-bars { display: grid; gap: 9px; padding: 14px 18px 6px; }
.calibration-bars > div { display: grid; grid-template-columns: 110px minmax(160px, 1fr) 150px; align-items: center; gap: 12px; font-size: 13px; }
.calibration-bars > div > span { font-weight: 800; }
.calibration-bars > div > span small { color: var(--color-muted-text); font-weight: 500; }
.calibration-bars > div > div { position: relative; height: 14px; background: var(--color-background); }
.calibration-bars i { position: absolute; left: 0; display: block; height: 6px; }
.calibration-bars i.predicted { top: 0; background: var(--color-primary); }
.calibration-bars i.observed { bottom: 0; background: #7ba2c7; }
.calibration-bars strong { text-align: right; }
.calibration-legend { display: flex; gap: 18px; margin: 4px 18px 16px; color: var(--color-muted-text); font-size: 12px; }
.calibration-legend span { display: inline-flex; align-items: center; gap: 6px; }
.calibration-legend i { display: inline-block; width: 18px; height: 5px; }
.calibration-legend i.predicted { background: var(--color-primary); }
.calibration-legend i.observed { background: #7ba2c7; }
.board-note { margin: 0; padding: 13px 18px; border-bottom: 1px solid var(--color-border); color: var(--color-muted-text); font-size: 14px; }
.leaderboard-scroll { max-height: 700px; }
.leaderboard-panel tbody tr { cursor: pointer; }
.leaderboard-panel tbody tr:hover, .leaderboard-panel tbody tr:focus { outline: none; background: color-mix(in srgb, var(--color-primary) 9%, var(--color-surface)); }
.pitcher-cell { display: flex; align-items: center; gap: 10px; }
.pitcher-cell span { display: grid; gap: 3px; }
.pitcher-cell a { color: var(--color-primary); font-size: 11px; text-decoration: none; }
td small { display: block; margin-top: 3px; color: var(--color-muted-text); }
td small.event-hit { color: #e29a8c; }
.empty-state { padding: 20px; color: var(--color-muted-text); }
.player-panel { scroll-margin-top: 12px; }
.latest-strip { grid-template-columns: repeat(5, minmax(0, 1fr)); padding: 16px; }
.latest-strip article { background: var(--color-background); }
.appearance-scroll { max-height: 520px; border-top: 1px solid var(--color-border); }
.event-chip { display: inline-flex; border: 1px solid var(--color-border); padding: 3px 7px; color: var(--color-muted-text); font-size: 11px; font-weight: 850; text-transform: uppercase; }
.event-chip.active { border-color: #c85d4b; color: #f2b0a3; }
.shadow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 16px 18px; }
.shadow-grid article { border: 1px solid var(--color-border); padding: 14px; background: var(--color-background); }
.shadow-grid span { color: var(--color-muted-text); font-size: 12px; font-weight: 850; text-transform: uppercase; }
.shadow-grid strong { display: block; margin-top: 7px; font-size: 23px; }
.shadow-grid small { display: block; margin-top: 4px; color: var(--color-muted-text); }
.shadow-note { margin: 0; padding: 0 18px 17px; color: var(--color-muted-text); font-size: 14px; }
.warnings-panel { padding: 18px 20px; }
.warnings-panel h2 { margin: 0 0 10px; font-size: 19px; }
.warnings-panel p { margin: 7px 0; color: var(--color-muted-text); font-size: 14px; line-height: 1.45; }

@media (max-width: 1180px) {
  .controls { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .search-control { grid-column: 1 / -1; }
  .context-panel, .analysis-grid { grid-template-columns: 1fr; }
  .metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .v2-lab-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 720px) {
  .research-banner { align-items: flex-start; flex-direction: column; }
  .controls, .metric-grid, .latest-strip { grid-template-columns: 1fr; }
  .v2-lab-grid { grid-template-columns: 1fr; }
  .search-control { grid-column: auto; }
  .context-panel dl { grid-template-columns: 1fr 1fr; }
  .calibration-summary { grid-template-columns: 1fr; }
  .calibration-bars > div { grid-template-columns: 82px minmax(110px, 1fr) 112px; }
  .importance-list > div { grid-template-columns: minmax(120px, 1fr) 1fr 58px; }
  .shadow-grid { grid-template-columns: 1fr; }
}
</style>
