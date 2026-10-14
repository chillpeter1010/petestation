<script setup lang="ts">
import type {
  LeverageLeaderboardRow,
  LeverageOverviewResponse,
  LeverageScenarioInput,
  LeverageScenarioResponse,
  LeverageStateInput,
  TablePayload
} from '~/types/api'

const api = useApi()
const year = ref<2025 | 2026>(2026)
const source = ref<'estimated' | 'reference'>('estimated')
const overview = ref<LeverageOverviewResponse | null>(null)
const result = ref<LeverageScenarioResponse | null>(null)
const loading = ref(true)
const calculating = ref(false)
const errorMessage = ref('')
const search = ref('')
const team = ref('All')
const minimumAppearances = ref(0)
const stateSides = ['entry', 'exit'] as const

function defaultEntry(): LeverageStateInput {
  return { inning: 8, half: 'Top', outs: 1, runner_first: true, runner_second: false, runner_third: false, fielding_score: 2, opponent_score: 2 }
}
function defaultExit(): LeverageStateInput {
  return { inning: 9, half: 'Top', outs: 2, runner_first: false, runner_second: false, runner_third: false, fielding_score: 2, opponent_score: 3 }
}
const input = reactive<LeverageScenarioInput>({ year: 2026, entry: defaultEntry(), exit: defaultExit() })

const currentRows = computed(() => source.value === 'estimated' ? overview.value?.estimated_rows || [] : overview.value?.reference_rows || [])
const teams = computed(() => ['All', ...Array.from(new Set(currentRows.value.map(row => row.team))).sort()])
const filteredRows = computed(() => {
  const query = search.value.trim().toLowerCase()
  return currentRows.value.filter(row =>
    (team.value === 'All' || row.team === team.value)
    && (!query || row.name.toLowerCase().includes(query))
    && (source.value === 'reference' || (row.appearances || 0) >= minimumAppearances.value)
  )
})
const leaderboardTable = computed<TablePayload>(() => ({
  columns: [
    { key: 'rank', label: '#' }, { key: 'name', label: 'Name' }, { key: 'team', label: 'Team' },
    { key: 'appearances', label: 'G' }, { key: 'wpa', label: 'WPA' }, { key: 'negative_wpa', label: '-WPA' },
    { key: 'positive_wpa', label: '+WPA' }, { key: 're24', label: 'RE24' }, { key: 'rew', label: 'REW' },
    { key: 'pli', label: 'pLI' }, { key: 'inli', label: 'inLI' }, { key: 'gmli', label: 'gmLI' },
    { key: 'exli', label: 'exLI' }, { key: 'pulls', label: 'Pulls' }, { key: 'wpa_li', label: 'WPA/LI' },
    { key: 'clutch', label: 'Clutch' }, { key: 'shutdowns', label: 'SD' }, { key: 'meltdowns', label: 'MD' }
  ],
  rows: filteredRows.value as unknown as Record<string, unknown>[]
}))
const validationTable = computed<TablePayload>(() => ({
  columns: [
    { key: 'label', label: 'Metric' }, { key: 'samples', label: 'N' }, { key: 'correlation', label: 'Correlation' },
    { key: 'r_squared', label: 'R²' }, { key: 'mae', label: 'MAE' }, { key: 'rmse', label: 'RMSE' },
    { key: 'bias', label: 'Bias' }, { key: 'slope', label: 'Slope' }, { key: 'intercept', label: 'Intercept' }
  ],
  rows: (overview.value?.validation || []).map(row => ({ ...row, label: metricLabel(row.metric) }))
}))
const validationHighlights = computed(() => ['re24', 'pli', 'gmli', 'shutdowns'].map(metric => {
  const row = overview.value?.validation.find(item => item.metric === metric)
  return { metric, label: metricLabel(metric), value: row?.r_squared }
}))
const outcome = computed(() => result.value?.metrics.find(metric => metric.key === 'result')?.value || '—')
const wpa = computed(() => result.value?.metrics.find(metric => metric.key === 'wpa')?.value)

watch(source, () => { if (!teams.value.includes(team.value)) team.value = 'All' })
watch(year, async value => {
  input.year = value
  team.value = 'All'
  await Promise.all([loadOverview(), calculate()])
})
onMounted(() => Promise.all([loadOverview(), calculate()]))

async function loadOverview() {
  loading.value = true
  errorMessage.value = ''
  try { overview.value = await api.leverageOverview(year.value) }
  catch (error: unknown) { errorMessage.value = error instanceof Error ? error.message : 'Unable to load leverage data.' }
  finally { loading.value = false }
}
async function calculate() {
  calculating.value = true
  errorMessage.value = ''
  try {
    result.value = await api.leverageCalculator({
      year: year.value,
      entry: { ...input.entry },
      exit: { ...input.exit }
    })
  } catch (error: unknown) { errorMessage.value = error instanceof Error ? error.message : 'Unable to calculate this scenario.' }
  finally { calculating.value = false }
}
function resetScenario() {
  input.entry = defaultEntry()
  input.exit = defaultExit()
  calculate()
}
function metricLabel(metric: string) {
  return ({
    wpa: 'WPA', negative_wpa: '-WPA', positive_wpa: '+WPA', re24: 'RE24', pli: 'pLI', inli: 'inLI',
    gmli: 'gmLI', exli: 'exLI', pulls: 'Pulls', wpa_li: 'WPA/LI', clutch: 'Clutch',
    shutdowns: 'SD', meltdowns: 'MD'
  } as Record<string, string>)[metric] || metric
}
function display(value: unknown, digits = 3) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'number') return value.toFixed(digits)
  return String(value)
}
function stateValue(state: Record<string, number | string | null> | undefined, key: string) {
  return state ? display(state[key]) : '—'
}
function playerLink(row: Record<string, unknown>) {
  const playerId = Number(row.player_id)
  if (!Number.isFinite(playerId)) return undefined
  return { path: '/pitcher-personal', query: { year: year.value, role: 'RP', team: String(row.team || ''), pitcher_id: playerId } }
}
</script>

<template>
  <main class="leverage-page">
    <ComparisonPageHeader
      eyebrow="Pitcher Lab · Run & leverage"
      title="RE24 & Leverage Lab"
      description="A 2025–2026 test bench for game-state value, leverage, reference validation, and reliever rankings."
      back-to="/lab"
      back-label="Pitcher Lab"
    />

    <p v-if="errorMessage" class="error-panel">{{ errorMessage }}</p>

    <section class="calculator-shell">
      <form class="scenario-panel" @submit.prevent="calculate">
        <header class="section-header">
          <div><span>Scenario calculator</span><h2>Set entry and exit states</h2></div>
          <label class="year-control">Season<select v-model.number="year"><option :value="2025">2025</option><option :value="2026">2026</option></select></label>
        </header>

        <div class="state-grid">
          <fieldset v-for="side in stateSides" :key="side">
            <legend>{{ side === 'entry' ? 'Entry state' : 'Exit state' }}</legend>
            <div class="input-grid">
              <label>Inning<input v-model.number="input[side].inning" type="number" min="1" max="20"></label>
              <label>Half<select v-model="input[side].half"><option value="Top">Top</option><option value="Bottom">Bottom</option></select></label>
              <label>Outs<select v-model.number="input[side].outs"><option :value="0">0</option><option :value="1">1</option><option :value="2">2</option></select></label>
              <label>Pitching team<input v-model.number="input[side].fielding_score" type="number" min="0" max="99"></label>
              <label>Opponent<input v-model.number="input[side].opponent_score" type="number" min="0" max="99"></label>
            </div>
            <div class="bases" aria-label="Occupied bases">
              <span>Runners</span>
              <label><input v-model="input[side].runner_first" type="checkbox">1B</label>
              <label><input v-model="input[side].runner_second" type="checkbox">2B</label>
              <label><input v-model="input[side].runner_third" type="checkbox">3B</label>
            </div>
          </fieldset>
        </div>
        <div class="form-actions">
          <button type="button" class="secondary" @click="resetScenario">Reset example</button>
          <button type="submit" :disabled="calculating">{{ calculating ? 'Calculating…' : 'Calculate RE24 & LI' }}</button>
        </div>
      </form>

      <aside class="result-panel" aria-live="polite">
        <div class="result-hero">
          <span>Estimated WPA</span><strong>{{ display(wpa) }}</strong><b>{{ outcome }}</b>
          <small>{{ result?.model_version || 'Waiting for model' }} · through {{ result?.data_as_of || '—' }}</small>
        </div>
        <div v-if="result" class="metric-grid">
          <article v-for="metric in result.metrics.filter(item => item.key !== 'result')" :key="metric.key">
            <span>{{ metric.label }}</span><strong>{{ display(metric.value) }}</strong>
            <em v-if="metric.status !== 'estimated'">{{ metric.status.replace('_', ' ') }}</em>
            <small>{{ metric.note }}</small>
          </article>
        </div>
      </aside>
    </section>

    <section v-if="result" class="state-output panel">
      <header class="section-header"><div><span>Matched model states</span><h2>Entry vs exit context</h2></div><small>Nearest state is used when an exact state has no sample.</small></header>
      <div class="state-output-grid">
        <article v-for="side in stateSides" :key="side">
          <h3>{{ side === 'entry' ? 'Entry' : 'Exit' }}</h3>
          <dl><div><dt>Win expectancy</dt><dd>{{ stateValue(result[side], 'win_expectancy') }}</dd></div><div><dt>LI</dt><dd>{{ stateValue(result[side], 'li') }}</dd></div><div><dt>Run expectancy</dt><dd>{{ stateValue(result[side], 'run_expectancy') }}</dd></div><div><dt>Samples</dt><dd>{{ stateValue(result[side], 'state_samples') }}</dd></div></dl>
        </article>
      </div>
      <p>{{ result.warnings.join(' ') }}</p>
    </section>

    <section class="validation-section panel">
      <header class="section-header"><div><span>Regression check</span><h2>Local estimate vs collected league table</h2></div><small>{{ year }} · matched by MLBAM ID</small></header>
      <div class="validation-cards">
        <article v-for="item in validationHighlights" :key="item.metric"><span>{{ item.label }} R²</span><strong>{{ display(item.value) }}</strong></article>
      </div>
      <DataTable title="Validation diagnostics" :table="validationTable" :max-rows="30" />
      <p class="method-note">Linear diagnostics compare the raw local estimate with the collected reference; the regression is not used to force-fit leaderboard values. 2026 counting stats may use different cutoff dates.</p>
    </section>

    <section class="leaderboard-section panel">
      <header class="section-header"><div><span>League leaderboard</span><h2>Reliever run & leverage value</h2></div><small>{{ filteredRows.length }} rows</small></header>
      <div class="filters">
        <label>Source<select v-model="source"><option value="estimated">Local Estimate</option><option value="reference">Collected Reference</option></select></label>
        <label>Team<select v-model="team"><option v-for="item in teams" :key="item" :value="item">{{ item === 'All' ? 'All MLB' : item }}</option></select></label>
        <label>Search<input v-model="search" type="search" placeholder="Reliever name"></label>
        <label :class="{ disabled: source === 'reference' }">Minimum games<input v-model.number="minimumAppearances" type="number" min="0" max="100" :disabled="source === 'reference'"></label>
      </div>
      <div v-if="loading" class="loading-panel">Building season state model…</div>
      <DataTable
        v-else
        :title="source === 'estimated' ? 'Local Estimate' : 'Collected Reference'"
        :table="leaderboardTable"
        :max-rows="1000"
        link-column="name"
        headshot-column="name"
        headshot-id-key="player_id"
        :link-to="playerLink"
      />
      <div v-if="overview" class="freshness-note">
        <span>Local data through {{ overview.data_as_of || '—' }}</span><span>Reference file updated {{ overview.reference_updated_at?.slice(0, 10) || '—' }}</span><span>{{ overview.model_version }}</span><span>{{ overview.runs_per_win }} runs / win</span>
      </div>
      <p v-if="overview?.warnings.length" class="method-note">{{ overview.warnings.join(' ') }}</p>
    </section>
  </main>
</template>

<style scoped>
.leverage-page{display:grid;gap:16px;min-width:0}.calculator-shell{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(360px,.85fr);gap:14px;align-items:start}.scenario-panel,.result-panel,.panel{border:1px solid var(--color-border);border-radius:0;background:var(--color-surface);box-shadow:var(--shadow-sm);min-width:0}.scenario-panel{display:grid;gap:18px;padding:20px}.section-header{display:flex;align-items:center;justify-content:space-between;gap:14px}.section-header span,.result-hero>span,.validation-cards span{color:var(--color-primary);font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.section-header h2{margin:4px 0 0;font-size:22px}.section-header small{color:var(--color-muted-text)}label{display:grid;gap:6px;color:var(--color-muted-text);font-size:11px;font-weight:850;text-transform:uppercase}select,input[type='number'],input[type='search']{min-height:41px;border:1px solid var(--color-border);border-radius:0;padding:0 10px;color:var(--color-foreground);background:var(--color-background);font:inherit}.year-control{min-width:120px}.state-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}fieldset{min-width:0;margin:0;border:1px solid var(--color-border);border-radius:0;padding:14px}legend{padding:0 7px;color:var(--color-foreground);font-weight:900}.input-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.bases{display:flex;align-items:center;gap:12px;margin-top:14px;padding:10px;border:1px solid var(--color-border);background:var(--color-background)}.bases>span{margin-right:auto;color:var(--color-muted-text);font-size:11px;font-weight:900;text-transform:uppercase}.bases label{display:flex;align-items:center;gap:5px;color:var(--color-foreground)}input[type='checkbox']{accent-color:var(--color-primary)}.form-actions{display:flex;justify-content:flex-end;gap:10px}.form-actions button{min-height:44px;border:1px solid var(--color-primary);border-radius:0;padding:0 16px;color:var(--color-on-primary);background:var(--color-primary);font-weight:900;cursor:pointer}.form-actions button.secondary{color:var(--color-foreground);background:transparent;border-color:var(--color-border)}button:disabled{opacity:.55;cursor:wait}.result-panel{overflow:hidden}.result-hero{min-height:230px;display:grid;place-items:center;align-content:center;gap:8px;padding:24px;background:radial-gradient(circle at 50% 15%,color-mix(in srgb,var(--color-primary) 20%,transparent),transparent 52%)}.result-hero>strong{font:800 clamp(56px,7vw,92px)/1 var(--font-mono)}.result-hero>b{padding:6px 11px;border:1px solid var(--color-primary);color:var(--color-primary);font-size:14px;text-transform:uppercase}.result-hero small{color:var(--color-muted-text)}.metric-grid{display:grid;grid-template-columns:1fr 1fr;border-top:1px solid var(--color-border)}.metric-grid article{min-height:132px;display:grid;align-content:start;gap:4px;padding:13px;border-right:1px solid var(--color-border);border-bottom:1px solid var(--color-border)}.metric-grid article:nth-child(even){border-right:0}.metric-grid span{color:var(--color-muted-text);font-size:11px;font-weight:900;text-transform:uppercase}.metric-grid strong{font:800 22px var(--font-mono)}.metric-grid em{width:max-content;padding:2px 5px;color:var(--color-primary);background:color-mix(in srgb,var(--color-primary) 10%,transparent);font-size:9px;font-style:normal;text-transform:uppercase}.metric-grid small{color:var(--color-muted-text);font-size:10px;line-height:1.4}.panel>.section-header{padding:16px 18px;border-bottom:1px solid var(--color-border)}.state-output-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px}.state-output-grid article{border:1px solid var(--color-border);padding:14px}.state-output-grid h3{margin:0 0 10px}.state-output dl{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;margin:0;background:var(--color-border)}.state-output dl div{padding:10px;background:var(--color-background)}dt{color:var(--color-muted-text);font-size:10px;text-transform:uppercase}dd{margin:4px 0 0;font:800 16px var(--font-mono)}.state-output>p,.method-note{margin:0;padding:0 18px 16px;color:var(--color-muted-text);font-size:12px;line-height:1.55}.validation-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;padding:16px;background:var(--color-border)}.validation-cards article{display:grid;gap:7px;padding:14px;background:var(--color-background)}.validation-cards strong{font:800 28px var(--font-mono)}.filters{display:grid;grid-template-columns:180px 160px minmax(220px,1fr) 160px;gap:10px;padding:14px;border-bottom:1px solid var(--color-border)}.disabled{opacity:.45}.freshness-note{display:flex;flex-wrap:wrap;gap:8px 18px;padding:12px 18px;border-top:1px solid var(--color-border);color:var(--color-muted-text);font-size:11px}.loading-panel{padding:28px;color:var(--color-muted-text)}.error-panel{margin:0;padding:15px;border:1px solid #c84b45;border-radius:0;color:#ff9d96;background:rgba(190,55,45,.1)}.validation-section :deep(.data-table-wrap),.leaderboard-section :deep(.data-table-wrap){border-right:0;border-left:0;border-radius:0}.leaderboard-section :deep(.table-scroll){max-height:650px}.leaderboard-section :deep(table){min-width:1700px}.leaderboard-section :deep(th),.leaderboard-section :deep(td){white-space:nowrap}.leaderboard-section :deep(th:nth-child(1)),.leaderboard-section :deep(td:nth-child(1)){position:sticky;left:0;z-index:2;background:var(--color-surface)}.leaderboard-section :deep(th:nth-child(2)),.leaderboard-section :deep(td:nth-child(2)){position:sticky;left:48px;z-index:2;min-width:190px;background:var(--color-surface)}.leaderboard-section :deep(th:nth-child(-n+2)){z-index:4}@media(max-width:1000px){.calculator-shell{grid-template-columns:1fr}.filters{grid-template-columns:1fr 1fr}.validation-cards{grid-template-columns:1fr 1fr}}@media(max-width:680px){.state-grid,.state-output-grid{grid-template-columns:1fr}.input-grid{grid-template-columns:1fr 1fr}.filters{grid-template-columns:1fr}.state-output dl{grid-template-columns:1fr 1fr}.section-header{align-items:flex-start;flex-direction:column}.year-control{width:100%}}
</style>
