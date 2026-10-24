<script setup lang="ts">
import type { CatcherDescriptiveDetailResponse, CatcherDescriptiveLeaderboardResponse, CatcherStrategyBridgeResponse, TablePayload } from '~/types/api'

const api = useApi()
const route = useRoute()
const router = useRouter()
const year = ref(Number(route.query.year) || 2021)
const catcherId = ref(Number(route.query.catcher_id) || 0)
const leaderboard = ref<CatcherDescriptiveLeaderboardResponse | null>(null)
const detail = ref<CatcherDescriptiveDetailResponse | null>(null)
const strategyBridge = ref<CatcherStrategyBridgeResponse | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const strategyError = ref('')
const search = ref('')

const catcherOptions = computed(() => (leaderboard.value?.rows || []).slice().sort((a, b) => a.catcher_name.localeCompare(b.catcher_name)))
const filteredPairs = computed(() => {
  const query = search.value.trim().toLowerCase()
  return (detail.value?.pitcher_pairs || []).filter(row => !query || `${row.pitcher_name} ${row.teams}`.toLowerCase().includes(query))
})
function number(value: number | null | undefined, digits = 2) { return value === null || value === undefined ? '—' : value.toFixed(digits) }
function reliabilityLabel(value: 'supported' | 'limited' | 'unavailable' | undefined) {
  return value ? value[0].toUpperCase() + value.slice(1) : '—'
}
function reliabilityReason(row: CatcherDescriptiveLeaderboardResponse['rows'][number]) {
  return (row.reliability_reasons || []).map(reason => reason.replaceAll('_', ' ')).join(' · ') || 'All reliability gates passed'
}
const pairTable = computed<TablePayload>(() => ({
  columns: ['Pitcher', 'Team', 'IP', 'BF', 'R', 'ER', 'cERA', 'cRA9', 'cFIP', 'Season ERA', 'Season RA9', 'Season FIP', 'xERA', 'Pitcher xERA', 'xR vs Mix', 'xERA Cov', 'xERA Status', 'cSaveRun', 'cSaveRun/IP', 'LCO IP', 'LCO ERA', 'LCO RA9', 'LCO FIP', 'LCO cSaveRun', 'LCO Status'].map(key => ({ key, label: key })),
  rows: filteredPairs.value.map(row => ({
    Pitcher: row.pitcher_name, Team: row.teams, IP: row.display_ip, BF: row.bf, R: row.pitcher_charged_runs, ER: row.earned_runs,
    cERA: number(row.c_era), cRA9: number(row.c_ra9), cFIP: number(row.c_fip),
    'Season ERA': number(row.pitcher_season_era), 'Season RA9': number(row.pitcher_season_ra9), 'Season FIP': number(row.pitcher_season_fip),
    xERA: number(row.xera), 'Pitcher xERA': number(row.pitcher_xera), 'xR vs Mix': number(row.x_runs_vs_mix, 2),
    'xERA Cov': `${number(row.xera_source_coverage_pct, 1)}%`, 'xERA Status': row.xera_status ?? '—',
    cSaveRun: number(row.c_save_run, 2), 'cSaveRun/IP': number(row.c_save_run_per_ip, 3), 'LCO IP': row.lco_display_ip,
    'LCO ERA': number(row.lco_era), 'LCO RA9': number(row.lco_ra9), 'LCO FIP': number(row.lco_fip),
    'LCO cSaveRun': number(row.lco_c_save_run, 2), 'LCO Status': row.lco_status, player_id: row.pitcher_id
  }))
}))
const metricCards = computed(() => {
  const row = detail.value?.catcher
  if (!row) return []
  return [
    ['cERA', number(row.c_era), `${row.earned_runs} ER / ${row.outs} outs`],
    ['cRA9', number(row.c_ra9), `${row.pitcher_charged_runs} R / ${row.outs} outs`],
    ['cFIP', number(row.c_fip), `${row.home_runs} HR · ${row.walks_total} BB · ${row.hit_by_pitch} HBP · ${row.strikeouts} K`],
    ['tERA', number(row.t_era), `${row.display_ip} IP · full-season pitcher mix`],
    ['tRA9', number(row.t_ra9), 'All catcher outs included'],
    ['tFIP', number(row.t_fip), `FIP constant ${detail.value?.fip_constant.toFixed(3)}`],
    ['cxERA', number(row.cxera), `${number(row.xera_source_coverage_pct, 1)}% source coverage · Petehub xERA v1`],
    ['txERA', number(row.txera), 'Handled pitchers weighted by shared outs'],
    ['xR vs Mix', number(row.x_runs_vs_mix, 2), 'txERA expected runs minus catcher-PA expected runs'],
    ['xR vs Mix/IP', number(row.x_runs_vs_mix_per_ip, 3), 'Observed expected-results association; not annualized'],
    ['FRV', number(row.frv, 1), `${row.frv_status ?? 'unavailable'} · Statcast fielding runs above source-defined average`],
    ['Throwing', number(row.throwing, 1), 'Statcast catcher throwing component'],
    ['Blocking', number(row.blocking, 1), 'Statcast catcher blocking component'],
    ['Framing', number(row.framing, 1), 'Statcast catcher framing component'],
    ['cSaveRun', number(row.c_save_run, 2), '(tRA9 − cRA9) over all catcher outs'],
    ['cSaveRun/IP', number(row.c_save_run_per_ip, 3), 'cSaveRun divided by catcher innings; not annualized'],
    ['Reliability', reliabilityLabel(row.reliability_tier), `${row.adjacent_eligible_season_count ?? 0} adjacent eligible seasons · ${reliabilityReason(row)}`],
    ['Dominant Pair Δ/IP', number(row.dominant_pair_delta_c_save_run_per_ip, 3), `${row.dominant_pitcher_name || 'Unavailable'} · ${number(row.dominant_pair_out_share_pct, 1)}% of outs`],
    ['No-Dominant cSaveRun/IP', number(row.without_dominant_c_save_run_per_ip, 3), `${row.non_dominant_ip || '—'} IP after removing the largest pair`],
    ['Max Pair', `${number(row.max_pitcher_out_share_pct, 1)}%`, `${row.pitchers} pitchers handled`]
  ]
})
const strategyCards = computed(() => {
  const row = strategyBridge.value?.row
  if (!row) return []
  return [
    ['Supported set', row.supported_set_decisions.toLocaleString(), `${number(row.supported_set_coverage_pct, 1)}% of ${row.total_decisions.toLocaleString()} observed pitch decisions`],
    ['Normalized entropy', number(row.mean_normalized_entropy, 3), '0 = concentrated mix · 1 = even supported mix'],
    ['Effective choices', number(row.mean_effective_supported_choices, 2), 'Average effective number of supported pitch choices'],
    ['Top-choice probability', `${number(row.mean_top_supported_probability_pct, 1)}%`, 'Frozen model probability of the most likely supported choice'],
    ['Supported deviation', number(row.mean_supported_deviation_gain, 4), 'Runs per pitch; one-sided model comparison, lower is better'],
    ['Model-minimum choice', `${number(row.observed_choice_model_minimum_rate_pct, 1)}%`, 'Observed choice matched the model minimum within supported choices'],
    ['Chosen support', `${number(row.chosen_supported_coverage_pct, 1)}%`, `${row.chosen_supported_decisions.toLocaleString()} of all observed decisions`],
    ['Noise separation', String(row.deviations_exceeding_noise_floor), 'No single-pitch best-choice label is released']
  ]
})
const strategyTierTable = computed<TablePayload>(() => ({
  columns: ['Count state', 'Decisions', 'Entropy', 'Effective choices', 'Supported deviation', 'Model-minimum choice'].map(key => ({ key, label: key })),
  rows: (strategyBridge.value?.row?.count_tiers || []).map(row => ({
    'Count state': row.count_tier,
    Decisions: row.decisions.toLocaleString(),
    Entropy: number(row.mean_normalized_entropy, 3),
    'Effective choices': number(row.mean_effective_supported_choices, 2),
    'Supported deviation': number(row.mean_supported_deviation_gain, 4),
    'Model-minimum choice': `${number(row.observed_choice_model_minimum_rate_pct, 1)}%`
  }))
}))
function pitcherLink(row: Record<string, unknown>) {
  return { path: '/pitcher-personal', query: { year: year.value, pitcher_id: Number(row.player_id) } }
}
async function load() {
  loading.value = true
  errorMessage.value = ''
  strategyError.value = ''
  try {
    leaderboard.value = await api.catcherDescriptiveLeaderboard({ year: year.value })
    if (!leaderboard.value.rows.some(row => row.catcher_id === catcherId.value) && leaderboard.value.rows.length) catcherId.value = leaderboard.value.rows[0].catcher_id
    if (!catcherId.value) throw new Error('No catcher rows are available.')
    detail.value = await api.catcherDescriptiveDetail({ year: year.value, catcherId: catcherId.value })
    try {
      strategyBridge.value = await api.catcherDescriptiveStrategyBridge({ year: year.value, catcherId: catcherId.value })
    } catch (error: unknown) {
      strategyBridge.value = null
      strategyError.value = error instanceof Error ? error.message : 'Unable to load the strategy bridge.'
    }
    await router.replace({ query: { year: year.value, catcher_id: catcherId.value } })
  } catch (error: unknown) {
    detail.value = null
    strategyBridge.value = null
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load catcher metrics.'
  } finally { loading.value = false }
}
watch(year, async () => { catcherId.value = 0; await load() })
watch(catcherId, (value, previous) => { if (value && previous) load() })
onMounted(load)
</script>

<template>
  <main class="catcher-lab-page">
    <ComparisonPageHeader eyebrow="Catcher Station · Research" title="Catcher Metrics Lab" description="Audit raw numerators, full-season pitcher-mix weights, and leave-catcher-out sensitivity diagnostics for every pitcher pairing." back-to="/fielders/catchers" back-label="Catcher Station" />
    <section class="controls">
      <label>Season<select v-model.number="year"><option v-for="option in [2021,2022,2023,2024,2025,2026]" :key="option" :value="option">{{ option }}</option></select></label>
      <label>Catcher<select v-model.number="catcherId"><option v-for="option in catcherOptions" :key="option.catcher_id" :value="option.catcher_id">{{ option.catcher_name }} · {{ option.team }}</option></select></label>
      <label>Find pitcher<input v-model.trim="search" type="search" placeholder="Pitcher or team"></label>
    </section>
    <p v-if="loading" class="state-panel">Loading catcher detail…</p>
    <p v-else-if="errorMessage" class="state-panel error">{{ errorMessage }}</p>
    <template v-else-if="detail">
      <section class="identity-panel">
        <MlbPlayerHeadshot :player-id="detail.catcher.catcher_id" :name="detail.catcher.catcher_name" :size="76" :source-width="160" shape="circle" />
        <div><span>{{ year }} single-season preview</span><h2>{{ detail.catcher.catcher_name }}</h2><p>{{ detail.catcher.team }} · {{ detail.catcher.display_ip }} IP · {{ detail.catcher.games }} games caught · {{ number(detail.catcher.baseline_coverage_pct, 1) }}% LCO diagnostic coverage</p></div>
        <NuxtLink to="/fielders/catchers/leaderboard">Back to leaderboard</NuxtLink>
      </section>
      <section class="metric-grid"><article v-for="card in metricCards" :key="card[0]"><span>{{ card[0] }}</span><strong>{{ card[1] }}</strong><small>{{ card[2] }}</small></article></section>
      <aside class="method-note"><b>Reading rule:</b> main t metrics weight each pitcher's complete official season rates by all outs caught. Petehub xERA v1 uses Statcast per-PA expected-wOBA as an upstream input and a frozen 2021–2023 additive ERA-scale calibration; it is not identical to MLB's published xERA. Statcast FRV, Throwing, Blocking and Framing are runs above the source-defined average, not absolute runs prevented. They form a separate full-season defense axis, are not added to cSaveRun or xR vs Mix, cannot be allocated to Paired Duo, and have no park adjustment. cxERA, txERA and xR vs Mix remain descriptive expected-results associations. LCO and dominant-pair fields are sensitivity diagnostics, and none is a causal catcher-value estimate.</aside>
      <section class="strategy-panel" aria-labelledby="strategy-bridge-title">
        <header>
          <div><span>Slice 8 · Research only</span><h2 id="strategy-bridge-title">Model-consistent strategy bridge</h2></div>
          <strong v-if="strategyBridge">{{ strategyBridge.status }}</strong>
        </header>
        <p class="strategy-warning">This panel places frozen 2026 pitch-choice predictability and supported-deviation diagnostics beside the descriptive catcher record. The catcher ID means the catcher was on the field; it does not identify who selected the pitch. There is no catcher strategy leaderboard, composite score, causal calling value, or individual best-pitch advice.</p>
        <p v-if="strategyError" class="strategy-state error" role="alert">{{ strategyError }}</p>
        <p v-else-if="strategyBridge?.status === 'unavailable'" class="strategy-state">{{ strategyBridge.reason }}</p>
        <template v-else-if="strategyBridge?.row">
          <div class="strategy-grid">
            <article v-for="card in strategyCards" :key="card[0]"><span>{{ card[0] }}</span><strong>{{ card[1] }}</strong><small>{{ card[2] }}</small></article>
          </div>
          <DataTable class="strategy-table" title="2026 count-state diagnostics" :table="strategyTierTable" :max-rows="10" />
        </template>
      </section>
      <DataTable class="pair-table" title="Pitcher-pair accounting, xERA, full-season mix, and LCO diagnostics" :table="pairTable" :max-rows="500" link-column="Pitcher" headshot-column="Pitcher" :headshot-size="44" :link-to="pitcherLink" />
    </template>
  </main>
</template>

<style scoped>
.catcher-lab-page{display:grid;gap:18px;padding:24px}.controls,.identity-panel,.method-note,.state-panel,.strategy-panel{border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface);box-shadow:var(--shadow-sm)}.controls{display:grid;grid-template-columns:140px minmax(260px,1fr) minmax(220px,1fr);gap:14px;padding:16px}.controls label{display:grid;gap:7px;color:var(--color-text-muted);font-size:12px;font-weight:800}.controls select,.controls input{min-height:42px;border:1px solid var(--color-border-strong);border-radius:8px;padding:0 11px;color:var(--color-text);background:var(--color-surface)}.identity-panel{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:16px;padding:18px}.identity-panel span,.strategy-panel header span{color:var(--color-primary);font-size:11px;font-weight:900;text-transform:uppercase}.identity-panel h2{margin:4px 0;font-size:28px}.identity-panel p{margin:0;color:var(--color-text-muted)}.identity-panel>a{color:var(--color-primary);font-weight:850;text-decoration:none}.metric-grid,.strategy-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.metric-grid article,.strategy-grid article{display:grid;gap:7px;min-height:126px;border:1px solid var(--color-border);border-radius:12px;padding:16px;background:var(--color-surface)}.metric-grid span,.strategy-grid span{color:var(--color-text-muted);font-size:12px;font-weight:850}.metric-grid strong,.strategy-grid strong{font-size:28px}.metric-grid small,.strategy-grid small{color:var(--color-text-muted);line-height:1.4}.method-note{border-left:4px solid var(--color-primary);padding:14px 17px;color:var(--color-text-muted);font-size:14px;line-height:1.5}.strategy-panel{display:grid;gap:16px;padding:18px}.strategy-panel>header{display:flex;align-items:start;justify-content:space-between;gap:14px}.strategy-panel h2{margin:4px 0 0}.strategy-panel>header>strong{border:1px solid var(--color-border-strong);border-radius:999px;padding:6px 10px;color:var(--color-primary);font-size:11px;text-transform:uppercase}.strategy-warning,.strategy-state{margin:0;color:var(--color-text-muted);font-size:14px;line-height:1.55}.strategy-warning{border-left:4px solid var(--color-primary);padding:12px 14px;background:var(--color-muted)}.strategy-state{padding:18px;border:1px dashed var(--color-border-strong);border-radius:9px}.state-panel{margin:0;padding:28px}.state-panel.error,.strategy-state.error{color:#c4473a}.pair-table :deep(table),.strategy-table :deep(table){font-size:14px}.pair-table :deep(th),.strategy-table :deep(th){font-size:12px}.pair-table :deep(td),.pair-table :deep(th),.strategy-table :deep(td),.strategy-table :deep(th){padding-block:10px}@media(max-width:900px){.controls{grid-template-columns:1fr 1fr}.controls label:last-child{grid-column:1/-1}.metric-grid,.strategy-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.catcher-lab-page{padding:14px}.controls,.metric-grid,.strategy-grid{grid-template-columns:1fr}.controls label:last-child{grid-column:auto}.identity-panel{grid-template-columns:auto 1fr}.identity-panel>a{grid-column:1/-1}.strategy-panel>header{display:grid}}
</style>
