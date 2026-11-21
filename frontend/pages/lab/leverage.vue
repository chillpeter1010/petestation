<script setup lang="ts">
import type {
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
const teamMode = ref<'pitching' | 'pinch-hit'>('pitching')
const entryWpaColumns = [
  { key: 'entry_wpa_low', label: 'WPA · gmLI < 1' },
  { key: 'entry_wpa_mid', label: 'WPA · 1 ≤ gmLI ≤ 2' },
  { key: 'entry_wpa_high', label: 'WPA · gmLI > 2' }
]
let overviewRequest = 0

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
    ...entryWpaColumns,
    { key: 'pulls', label: 'Pulls' }, { key: 'wpa_li', label: 'WPA/LI' },
    { key: 'clutch', label: 'Clutch' }, { key: 'shutdowns', label: 'SD' }, { key: 'meltdowns', label: 'MD' }
  ],
  rows: filteredRows.value as unknown as Record<string, unknown>[]
}))
const teamTable = computed<TablePayload>(() => {
  const pitching = teamMode.value === 'pitching'
  const rows = (pitching ? overview.value?.team_pitching_rows : overview.value?.team_pinch_hit_rows) || []
  return {
    columns: [
      { key: 'team', label: 'Team' },
      { key: 'moves', label: pitching ? 'Observed entries' : 'Matched PH' },
      ...(pitching ? [] : [{ key: 'announced_moves', label: 'Announced PH' }]),
      { key: 'wpa', label: 'Total WPA' }, { key: 'wpa_n', label: 'WPA N' },
      { key: 're24', label: 'Total RE24' }, { key: 're24_n', label: 'RE24 N' },
      { key: 'wpa_per_move', label: 'WPA / move' }, { key: 're24_per_move', label: 'RE24 / move' },
      ...(pitching ? entryWpaColumns : [])
    ],
    rows: [...rows].sort((a, b) => (b.wpa ?? -Infinity) - (a.wpa ?? -Infinity)).map(row => ({ ...row }))
  }
})
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
  const request = ++overviewRequest
  loading.value = true
  errorMessage.value = ''
  overview.value = null
  try {
    const payload = await api.leverageOverview(year.value)
    if (request === overviewRequest) overview.value = payload
  } catch (error: unknown) {
    if (request === overviewRequest) errorMessage.value = error instanceof Error ? error.message : 'Unable to load leverage data.'
  } finally {
    if (request === overviewRequest) loading.value = false
  }
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
      description=""
      back-to="/lab"
      back-label="Pitcher Lab"
    />

    <p v-if="errorMessage" class="error-panel">{{ errorMessage }}</p>

    <section class="calculator-shell">
      <div class="scenario-column">
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

      <section v-if="result" class="state-output panel" aria-label="Entry and exit context">
        <div class="state-output-grid">
          <article v-for="side in stateSides" :key="side">
            <h3>{{ side === 'entry' ? 'Entry context' : 'Exit context' }}</h3>
            <dl>
              <div><dt>Win expectancy</dt><dd>{{ stateValue(result[side], 'win_expectancy') }}</dd></div>
              <div><dt>LI</dt><dd>{{ stateValue(result[side], 'li') }}</dd></div>
              <div><dt>Run expectancy</dt><dd>{{ stateValue(result[side], 'run_expectancy') }}</dd></div>
              <div><dt>Samples</dt><dd>{{ display(result[side].state_samples, 0) }}</dd></div>
            </dl>
          </article>
        </div>
      </section>
      </div>

      <aside class="result-panel" aria-live="polite">
        <div class="result-hero">
          <span>Estimated WPA</span><strong>{{ display(wpa) }}</strong><b>{{ outcome }}</b>
        </div>
        <div v-if="result" class="metric-grid">
          <article v-for="metric in result.metrics.filter(item => item.key !== 'result' && item.key !== 'wpa')" :key="metric.key">
            <span>{{ metric.label }}</span><strong>{{ display(metric.value) }}</strong>
            <em v-if="metric.status !== 'estimated'">{{ metric.status.replace('_', ' ') }}</em>
          </article>
        </div>
      </aside>
    </section>

    <section class="validation-section panel">
      <header class="section-header"><div><span>Regression check</span><h2>Local estimate vs collected league table</h2></div><small>{{ year }}</small></header>
      <div class="validation-cards">
        <article v-for="item in validationHighlights" :key="item.metric"><span>{{ item.label }} R²</span><strong>{{ display(item.value) }}</strong></article>
      </div>
      <DataTable title="Validation diagnostics" :table="validationTable" :max-rows="30" />
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
      <p v-if="!loading" class="substitution-note">
        {{ source === 'estimated'
          ? 'Entry gmLI is the local LI at the first observed pitch of a relief stint. Each bin sums complete stint WPA.'
          : 'Collected Reference has season totals. Entry gmLI WPA bins are available in Local Estimate.' }}
      </p>
    </section>

    <section class="leaderboard-section panel">
      <header class="section-header">
        <div><span>Team leaderboard</span><h2>Substitution outcomes</h2></div>
        <small>{{ year }}</small>
      </header>
      <div class="substitution-controls">
        <label>Move type<select v-model="teamMode"><option value="pitching">Pitching changes</option><option value="pinch-hit">Pinch hitters</option></select></label>
        <p>
          {{ teamMode === 'pitching'
            ? 'Local estimate · incoming pitcher’s observed stint, grouped by the team at entry.'
            : 'Official pinch-hit announcements matched to the batter’s completed plate appearance. Offensive perspective.' }}
          Data through {{ (teamMode === 'pitching' ? overview?.data_as_of : overview?.pinch_hit_data_as_of) || '—' }}.
          Per-move values use each metric’s scored N.
        </p>
      </div>
      <div v-if="loading" class="loading-panel">Loading substitution outcomes…</div>
      <DataTable v-else :key="teamMode" :table="teamTable" :max-rows="30" empty-text="No substitution data for this season." />
      <p class="substitution-note">Observed outcomes reflect the situations and players selected. Comparing managerial decisions requires a comparable alternative.</p>
    </section>
    <section v-if="overview?.team_pitching_rows?.length" class="panel" aria-labelledby="entry-leverage-heading">
      <header class="section-header">
        <div><span>Pitching changes</span><h2 id="entry-leverage-heading">Entry gmLI mix &amp; WPA</h2></div>
        <small>{{ year }}</small>
      </header>
      <TeamEntryLeverage :rows="overview.team_pitching_rows" />
    </section>
  </main>
</template>

<style scoped>
.leverage-page{--leverage-number-font:var(--font-mono,ui-monospace,SFMono-Regular,Consolas,monospace);display:grid;gap:20px;min-width:0;font-size:16px}
.leverage-page :deep(.comparison-page-header p){display:none}
.calculator-shell{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(360px,.8fr);gap:18px;align-items:start}
.scenario-column{display:grid;gap:16px;min-width:0}
.scenario-panel,.result-panel,.panel{border:1px solid var(--color-border);border-radius:0;background:var(--color-surface);box-shadow:var(--shadow-sm);min-width:0}
.scenario-panel{display:grid;gap:22px;padding:24px}
.section-header{display:flex;align-items:center;justify-content:space-between;gap:16px}
.section-header span,.result-hero>span,.validation-cards span{color:var(--color-primary);font-size:14px;font-weight:900;letter-spacing:.05em;text-transform:uppercase}
.section-header h2{margin:6px 0 0;font-size:26px;line-height:1.25}
.section-header small{color:var(--color-muted-text);font-size:16px}
label{display:grid;gap:8px;color:var(--color-muted-text);font-size:16px;font-weight:850;text-transform:uppercase}
select,input[type='number'],input[type='search']{min-width:0;width:100%;min-height:50px;border:1px solid var(--color-border);border-radius:0;padding:0 12px;color:var(--color-foreground);background:var(--color-background);font:inherit;font-size:18px;box-sizing:border-box}
.year-control{min-width:150px}
.state-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
fieldset{min-width:0;margin:0;border:1px solid var(--color-border);border-radius:0;padding:18px}
legend{padding:0 8px;color:var(--color-foreground);font-size:20px;font-weight:900}
.input-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.bases{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-top:18px;padding:12px;border:1px solid var(--color-border);background:var(--color-background)}
.bases>span{margin-right:auto;color:var(--color-muted-text);font-size:15px;font-weight:900;text-transform:uppercase}
.bases label{display:flex;align-items:center;gap:6px;color:var(--color-foreground);white-space:nowrap}
input[type='checkbox']{width:18px;height:18px;margin:0;accent-color:var(--color-primary)}
.form-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:12px}
.form-actions button{min-height:50px;border:1px solid var(--color-primary);border-radius:0;padding:0 20px;color:var(--color-on-primary);background:var(--color-primary);font-size:17px;font-weight:900;cursor:pointer}
.form-actions button.secondary{color:var(--color-foreground);background:transparent;border-color:var(--color-border)}
button:disabled{opacity:.55;cursor:wait}
.result-panel{overflow:hidden}
.result-hero{min-height:180px;display:grid;place-items:center;align-content:center;gap:14px;padding:24px;background:#000}
.result-hero>strong{font-family:var(--leverage-number-font);font-size:clamp(54px,4vw,76px);font-weight:800;line-height:1.1;font-variant-numeric:tabular-nums}
.result-hero>b{padding:7px 14px;border:1px solid var(--color-primary);color:var(--color-primary);font-size:17px;text-transform:uppercase}
.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));border-top:1px solid var(--color-border)}
.metric-grid article{min-width:0;min-height:114px;display:grid;align-content:start;gap:10px;padding:18px;border-right:1px solid var(--color-border);border-bottom:1px solid var(--color-border)}
.metric-grid article:nth-child(even){border-right:0}
.metric-grid article:nth-last-child(-n+2){border-bottom:0}
.metric-grid span{color:var(--color-muted-text);font-size:16px;font-weight:900;text-transform:uppercase;overflow-wrap:anywhere}
.metric-grid strong{font-family:var(--leverage-number-font);font-size:32px;font-weight:800;line-height:1.2;font-variant-numeric:tabular-nums}
.metric-grid em{max-width:100%;width:max-content;padding:4px 7px;color:var(--color-primary);background:color-mix(in srgb,var(--color-primary) 10%,transparent);font-size:12px;font-style:normal;text-transform:uppercase}
.panel>.section-header{padding:20px 22px;border-bottom:1px solid var(--color-border)}
.substitution-controls{display:flex;align-items:end;flex-wrap:wrap;gap:12px 22px;padding:14px 22px}
.substitution-controls label{min-width:210px}
.substitution-controls p,.substitution-note{color:var(--color-muted-text);font-size:14px;margin:0}
.substitution-note{padding:12px 22px}
.state-output{border:0;box-shadow:none;background:transparent}
.state-output-grid{display:grid;gap:16px}
.state-output-grid article{min-width:0;border:1px solid var(--color-border);padding:20px;background:var(--color-surface)}
.state-output-grid h3{margin:0 0 18px;font-size:22px}
.state-output dl{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;margin:0;background:var(--color-border)}
.state-output dl div{min-width:0;padding:12px;background:var(--color-background)}
dt{color:var(--color-muted-text);font-size:15px;line-height:1.4;text-transform:uppercase}
dd{margin:10px 0 0;font-family:var(--leverage-number-font);font-size:28px;font-weight:800;line-height:1.2;font-variant-numeric:tabular-nums}
.validation-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;margin:20px;background:var(--color-border)}
.validation-cards article{display:grid;gap:12px;padding:18px;background:var(--color-background)}
.validation-cards strong{font-family:var(--leverage-number-font);font-size:34px;font-weight:800}
.filters{display:grid;grid-template-columns:180px 160px minmax(220px,1fr) 160px;gap:14px;padding:20px;border-bottom:1px solid var(--color-border)}
.disabled{opacity:.45}
.loading-panel{padding:28px;color:var(--color-muted-text);font-size:18px}
.error-panel{margin:0;padding:16px;border:1px solid #c84b45;border-radius:0;color:#ff9d96;background:rgba(190,55,45,.1)}
.validation-section :deep(.data-table-wrap),.leaderboard-section :deep(.data-table-wrap){min-width:0;border-right:0;border-left:0;border-radius:0}
.validation-section :deep(.table-scroll),.leaderboard-section :deep(.table-scroll){max-width:100%;overflow-x:auto;scrollbar-width:auto;scrollbar-color:var(--color-border-strong) var(--color-background)}
.validation-section :deep(.table-scroll::-webkit-scrollbar),.leaderboard-section :deep(.table-scroll::-webkit-scrollbar){height:12px;width:12px}
.validation-section :deep(.table-scroll::-webkit-scrollbar-thumb),.leaderboard-section :deep(.table-scroll::-webkit-scrollbar-thumb){background:var(--color-border-strong);border:2px solid var(--color-background);border-radius:6px}
.validation-section :deep(th),.leaderboard-section :deep(th){font-size:15px}
.validation-section :deep(td),.leaderboard-section :deep(td){font-size:16px}
.validation-section :deep(th),.validation-section :deep(td),.leaderboard-section :deep(th),.leaderboard-section :deep(td){padding:14px 16px;white-space:nowrap}
.validation-section :deep(.sort-button),.leaderboard-section :deep(.sort-button){font-size:inherit}
.validation-section :deep(.table-header h2),.leaderboard-section :deep(.table-header h2){font-size:22px}
.validation-section :deep(.table-header>span),.leaderboard-section :deep(.table-header>span){font-size:15px}
.leaderboard-section :deep(.table-scroll){max-height:650px}
.leaderboard-section :deep(table){min-width:2000px}
.leaderboard-section :deep(th:nth-child(1)),.leaderboard-section :deep(td:nth-child(1)){position:sticky;left:0;z-index:2;width:64px;min-width:64px;box-sizing:border-box;background:var(--color-surface)}
.leaderboard-section :deep(th:nth-child(2)),.leaderboard-section :deep(td:nth-child(2)){position:sticky;left:64px;z-index:2;min-width:220px;background:var(--color-surface)}
.leaderboard-section :deep(th:nth-child(-n+2)){z-index:4}
@media(max-width:1500px) and (min-width:1101px){.input-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:1100px){.calculator-shell{grid-template-columns:1fr}.filters{grid-template-columns:repeat(2,minmax(0,1fr))}.validation-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:680px){.scenario-panel{padding:18px}.state-grid{grid-template-columns:1fr}.input-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.filters{grid-template-columns:1fr}.state-output dl{grid-template-columns:repeat(2,minmax(0,1fr))}.section-header{align-items:flex-start;flex-direction:column}.year-control{width:100%}.form-actions button{flex:1}.metric-grid article{padding:16px}.metric-grid strong{font-size:28px}.state-output-grid article{padding:16px}}
</style>
