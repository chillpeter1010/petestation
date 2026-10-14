<script setup lang="ts">
import type { PitchingLeaderboardRow, PitchingOverviewResponse, PitchingPitcherResponse } from '~/types/api'

const api = useApi()
const year = ref(2026)
const minimumInnings = ref(20)
const search = ref('')
const team = ref('All')
const sortKey = ref('pitching_plus')
const sortDirection = ref<'asc' | 'desc'>('desc')
const overview = ref<PitchingOverviewResponse | null>(null)
const detail = ref<PitchingPitcherResponse | null>(null)
const loading = ref(true)
const detailLoading = ref(false)
const errorMessage = ref('')
const pitchColumns = [
  { key: 'FF', label: 'P+ FF' }, { key: 'SI', label: 'P+ SI' }, { key: 'FC', label: 'P+ FC' },
  { key: 'FS', label: 'P+ FS' }, { key: 'SL', label: 'P+ SL' }, { key: 'ST', label: 'P+ ST' },
  { key: 'CU', label: 'P+ CU' }, { key: 'CH', label: 'P+ CH' }, { key: 'KC', label: 'P+ KC' }, { key: 'FO', label: 'P+ FO' }
]

const teams = computed(() => ['All', ...Array.from(new Set((overview.value?.rows || []).map(row => row.team))).sort()])
const filteredRows = computed(() => {
  const query = search.value.trim().toLowerCase()
  return (overview.value?.rows || []).filter(row => (team.value === 'All' || row.team === team.value) && (!query || row.pitcher_name.toLowerCase().includes(query)))
    .slice().sort((a, b) => {
      const left = sortValue(a, sortKey.value); const right = sortValue(b, sortKey.value)
      const result = typeof left === 'string' ? left.localeCompare(String(right)) : Number(left) - Number(right)
      return sortDirection.value === 'asc' ? result : -result
    })
})
const maxBin = computed(() => Math.max(1, ...(overview.value?.distribution || []).map(bin => bin.count)))
const trendChart = computed(() => {
  const rows = (detail.value?.outings || []).filter(row => Number.isFinite(row.pitching_plus))
  if (!rows.length) return { points: '', dots: [] as Array<{ x: number; y: number; label: string; value: number }>, yTicks: [] as Array<{ value: number; y: number }>, xTicks: [] as Array<{ label: string; x: number }> }
  const left = 58; const right = 700; const top = 18; const bottom = 190
  const rawMin = Math.min(100, ...rows.map(row => row.pitching_plus)); const rawMax = Math.max(100, ...rows.map(row => row.pitching_plus))
  const min = Math.floor((rawMin - 5) / 10) * 10; const max = Math.ceil((rawMax + 5) / 10) * 10
  const xFor = (index: number) => rows.length === 1 ? (left + right) / 2 : left + index * (right - left) / (rows.length - 1)
  const yFor = (value: number) => bottom - (value - min) / Math.max(1, max - min) * (bottom - top)
  const selectedIndexes = Array.from(new Set([0, Math.floor((rows.length - 1) / 2), rows.length - 1]))
  return {
    points: rows.map((row, index) => `${xFor(index)},${yFor(row.pitching_plus)}`).join(' '),
    dots: rows.map((row, index) => ({ x: xFor(index), y: yFor(row.pitching_plus), label: row.game_date, value: row.pitching_plus })),
    yTicks: Array.from({ length: 5 }, (_, index) => { const value = min + index * (max - min) / 4; return { value: Math.round(value), y: yFor(value) } }),
    xTicks: selectedIndexes.map(index => ({ label: rows[index]?.game_date.slice(5, 10) || '', x: xFor(index) }))
  }
})

function plusClass(value: number) { return value >= 110 ? 'plus-high' : value < 90 ? 'plus-low' : 'plus-average' }
function pitchScores(row: PitchingLeaderboardRow): Record<string, number> { return row.pitch_type_scores || {} }
function formatInnings(value: number | null | undefined): string { return Number(value || 0).toFixed(1) }
function sortValue(row: PitchingLeaderboardRow, key: string): string | number {
  if (key.startsWith('pitch:')) return pitchScores(row)[key.slice(6)] ?? Number.NEGATIVE_INFINITY
  const value = row[key as keyof PitchingLeaderboardRow]
  return typeof value === 'string' || typeof value === 'number' ? value : Number.NEGATIVE_INFINITY
}
function sortBy(key: string) { if (sortKey.value === key) sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'; else { sortKey.value = key; sortDirection.value = 'desc' } }
async function selectPitcher(row: PitchingLeaderboardRow) {
  detailLoading.value = true
  try {
    detail.value = await api.pitchingPitcher({ year: year.value, pitcherId: row.pitcher_id })
  } catch (error) {
    detail.value = null
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load pitcher detail.'
  } finally {
    detailLoading.value = false
  }
}
async function loadOverview() {
  loading.value = true; errorMessage.value = ''
  try {
    overview.value = await api.pitchingOverview({ year: year.value, minimumInnings: minimumInnings.value })
    if (!teams.value.includes(team.value)) team.value = 'All'
    const first = overview.value.rows[0]
    if (first) await selectPitcher(first); else detail.value = null
  } catch (error) { errorMessage.value = error instanceof Error ? error.message : 'Unable to load Pitching+ data.' } finally { loading.value = false }
}
watch(year, loadOverview)
onMounted(loadOverview)
</script>

<template>
  <main class="pitching-page">
    <ComparisonPageHeader eyebrow="Pitcher Lab · Complete pitch" title="Pitching+ Lab" description="Combine pitch shape, actual location, and pre-pitch context into one complete-pitch value. League average is 100." back-to="/lab" back-label="Pitcher Lab" />
    <div v-if="errorMessage" class="error-panel">{{ errorMessage }}</div>
    <div v-if="loading" class="loading-panel">Loading current Pitching+ exports…</div>
    <template v-else-if="!errorMessage">
      <section class="control-bar">
        <label class="season-control">Season<select v-model.number="year"><option v-for="item in overview?.available_years || [year]" :key="item" :value="item">{{ item }}</option></select></label>
        <label class="team-control">League / team<select v-model="team"><option v-for="item in teams" :key="item" :value="item">{{ item === 'All' ? 'All MLB' : item }}</option></select></label>
        <label class="innings-control"><span>Minimum innings <b>{{ minimumInnings }} IP</b></span><input v-model.number="minimumInnings" type="range" min="0" max="200" step="5" @change="loadOverview" /></label>
        <label class="search">Pitcher<input v-model="search" placeholder="Search pitcher" /></label>
        <span class="model-badge">Public model · {{ overview?.public_candidate || 'base' }}</span>
      </section>

      <p v-if="overview" :class="['freshness-note', overview.cache_status]">
        Pitching+ data through {{ overview.data_as_of || 'unknown' }} · {{ overview.cache_status }}
        <span v-if="overview.warnings.length">· {{ overview.warnings.join(' ') }}</span>
      </p>

      <section class="summary-grid">
        <article><span>Qualified pitchers</span><strong>{{ overview?.total_pitchers ?? '—' }}</strong></article>
        <article><span>Pitch sample</span><strong>{{ overview?.total_pitches.toLocaleString() ?? '—' }}</strong></article>
        <article><span>League median</span><strong>{{ overview?.median ?? '—' }}</strong></article>
        <article><span>Middle 80%</span><strong>{{ overview ? `${overview.p10}–${overview.p90}` : '—' }}</strong></article>
      </section>

      <section class="top-grid">
        <article class="panel distribution-panel">
          <header><div><span class="eyebrow">League surface</span><h2>Pitching+ distribution</h2></div><small>Click a bar to focus the scale</small></header>
          <div class="histogram" aria-label="Pitching plus distribution">
            <div v-for="bin in overview?.distribution || []" :key="bin.low" class="bin" :title="`${bin.low}–${bin.high}: ${bin.count}`">
              <div class="bar" :class="plusClass((bin.low + bin.high) / 2)" :style="{ height: `${Math.max(3, bin.count / maxBin * 100)}%` }" />
              <span>{{ bin.low % 10 === 0 ? bin.low : '' }}</span>
            </div>
          </div>
          <div class="scale-note"><span>Hitter advantage</span><b>100 = MLB average</b><span>Pitcher advantage</span></div>
        </article>

        <article class="panel pitcher-panel">
          <header><div><span class="eyebrow">Selected pitcher</span><h2>{{ detail?.pitcher.pitcher_name || 'Select a row' }}</h2></div><strong :class="plusClass(detail?.pitcher.pitching_plus || 100)">{{ detail?.pitcher.pitching_plus ?? '—' }}</strong></header>
          <p v-if="detailLoading">Loading pitcher detail…</p>
          <template v-else-if="detail">
            <div class="pitcher-meta"><span>{{ detail.pitcher.team }}</span><span>{{ detail.pitcher.pitches }} pitches</span><span>{{ detail.pitcher.xrv_per_100 }} xRV/100</span></div>
            <h3>Pitch-type contribution</h3>
            <div class="pitch-bars"><div v-for="pitch in detail.pitch_types" :key="pitch.pitch_type" class="pitch-row"><b>{{ pitch.pitch_type }}</b><span>{{ pitch.pitches }}</span><div><i :class="plusClass(pitch.pitching_plus)" :style="{ width: `${Math.max(4, Math.min(100, (pitch.pitching_plus - 60) / .8))}%` }" /></div><strong>{{ pitch.pitching_plus }}</strong></div></div>
          </template>
        </article>
      </section>

      <section class="panel trend-panel">
        <header><div><span class="eyebrow">Game progression</span><h2>{{ detail?.pitcher.pitcher_name || 'Pitcher' }} · outing trend</h2></div><small>Older → newer</small></header>
        <svg viewBox="0 0 720 240" role="img" aria-label="Pitching plus by outing">
          <g v-for="tick in trendChart.yTicks" :key="tick.value"><line x1="58" :y1="tick.y" x2="700" :y2="tick.y" class="grid-line"/><text x="48" :y="tick.y + 4" text-anchor="end">{{ tick.value }}</text></g>
          <line x1="58" y1="18" x2="58" y2="190" class="axis-line"/><line x1="58" y1="190" x2="700" y2="190" class="axis-line"/>
          <g v-for="tick in trendChart.xTicks" :key="`${tick.label}-${tick.x}`"><text :x="tick.x" y="212" text-anchor="middle">{{ tick.label }}</text></g>
          <text x="18" y="105" text-anchor="middle" transform="rotate(-90 18 105)" class="axis-title">Pitching+</text><text x="379" y="234" text-anchor="middle" class="axis-title">Game date</text>
          <polyline v-if="trendChart.points" :points="trendChart.points" class="trend-line" />
          <g v-for="dot in trendChart.dots" :key="`${dot.label}-${dot.x}`">
            <circle :cx="dot.x" :cy="dot.y" r="4" class="trend-dot"><title>{{ dot.label }} · {{ dot.value }}</title></circle>
          </g>
        </svg>
        <p v-if="!trendChart.dots.length" class="empty-chart">No outing-level Pitching+ records for this pitcher.</p>
      </section>

      <section class="panel leaderboard-panel">
        <header><div><span class="eyebrow">Ranked results</span><h2>Pitcher leaderboard</h2></div><small>{{ filteredRows.length }} pitchers · click a row to inspect</small></header>
        <div class="table-scroll"><table><thead><tr><th @click="sortBy('rank')">#</th><th @click="sortBy('pitcher_name')">Pitcher</th><th @click="sortBy('team')">Team</th><th @click="sortBy('innings_pitched')">IP</th><th @click="sortBy('pitches')">Pitches</th><th v-for="pitch in pitchColumns" :key="pitch.key" @click="sortBy(`pitch:${pitch.key}`)">{{ pitch.label }}</th><th @click="sortBy('xrv_per_100')">xRV/100</th><th @click="sortBy('pitching_plus')">Pitching+</th></tr></thead><tbody><tr v-for="row in filteredRows" :key="row.pitcher_id" :class="{ selected: row.pitcher_id === detail?.pitcher.pitcher_id }" @click="selectPitcher(row)"><td>{{ row.rank }}</td><td>{{ row.pitcher_name }}</td><td>{{ row.team }}</td><td>{{ formatInnings(row.innings_pitched) }}</td><td>{{ row.pitches }}</td><td v-for="pitch in pitchColumns" :key="pitch.key" class="pitch-score">{{ pitchScores(row)[pitch.key] ?? '—' }}</td><td>{{ row.xrv_per_100 }}</td><td><strong :class="plusClass(row.pitching_plus)">{{ row.pitching_plus }}</strong></td></tr></tbody></table></div>
      </section>

      <section class="panel validation-panel">
        <header><div><span class="eyebrow">Model validation</span><h2>Base model vs sequence challenger</h2></div><small>2026 untouched test set</small></header>
        <div class="candidate-grid"><article v-for="(candidate, key) in overview?.candidates" :key="key" :class="{ public: key === overview?.public_candidate }"><h3>{{ key }} <span v-if="key === overview?.public_candidate">Public</span></h3><dl><div><dt>Log loss ↓</dt><dd>{{ candidate.test_metrics.log_loss?.toFixed(4) }}</dd></div><div><dt>RV RMSE ↓</dt><dd>{{ candidate.test_metrics.run_value_rmse?.toFixed(4) }}</dd></div><div><dt>Pitch corr ↑</dt><dd>{{ candidate.test_metrics.run_value_correlation?.toFixed(3) }}</dd></div><div><dt>Grouped corr ↑</dt><dd>{{ candidate.test_metrics.grouped_correlation?.toFixed(3) }}</dd></div></dl></article></div>
        <p class="validation-note">Sequence features are kept as a research challenger. The base model remains public because it is simpler and wins the primary probability and run-value error metrics.</p>
      </section>
    </template>
  </main>
</template>

<style scoped>
.pitching-page{display:grid;gap:16px}.control-bar,.summary-grid,.top-grid{display:grid;gap:12px}.control-bar{grid-template-columns:180px 160px minmax(240px,1fr) auto;align-items:end;padding:14px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface)}label{display:grid;gap:7px;color:var(--color-muted-text);font-size:12px;font-weight:800;text-transform:uppercase}select,input{min-height:42px;border:1px solid var(--color-border);border-radius:8px;padding:0 12px;color:var(--color-foreground);background:var(--color-background)}.model-badge{align-self:center;border:1px solid var(--color-primary);border-radius:999px;padding:8px 12px;color:var(--color-primary);font-weight:800}.summary-grid{grid-template-columns:repeat(4,1fr)}.summary-grid article,.panel{border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface);box-shadow:var(--shadow-sm)}.summary-grid article{display:grid;gap:8px;padding:16px}.summary-grid span,.eyebrow{color:var(--color-primary);font-size:11px;font-weight:900;text-transform:uppercase}.summary-grid strong{font-size:29px}.top-grid{grid-template-columns:minmax(0,1.05fr) minmax(0,.95fr)}.panel header{display:flex;justify-content:space-between;gap:16px;align-items:center;padding:16px 18px;border-bottom:1px solid var(--color-border)}h2,h3,p{margin:0}header h2{margin-top:4px;font-size:22px}header small{color:var(--color-muted-text)}.histogram{height:260px;display:flex;align-items:stretch;gap:5px;padding:28px 22px 18px}.bin{height:100%;flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:7px}.bar{width:100%;min-width:8px;border-radius:5px 5px 1px 1px;opacity:.9}.bin span{height:14px;color:var(--color-muted-text);font-size:10px;line-height:14px}.plus-high{color:#f0a238!important;background:#f0a238}.plus-average{color:#e9edf5!important;background:#77839a}.plus-low{color:#6f87ff!important;background:#526dcf}.scale-note{display:flex;justify-content:space-between;padding:0 22px 18px;color:var(--color-muted-text);font-size:12px}.scale-note b{color:var(--color-foreground)}.pitcher-panel>header>strong{font-size:48px;background:none}.pitcher-meta{display:flex;gap:8px;padding:16px 18px}.pitcher-meta span{border-radius:999px;padding:6px 10px;background:var(--color-background);color:var(--color-muted-text)}.pitcher-panel h3{padding:0 18px}.pitch-bars{display:grid;gap:10px;padding:14px 18px 20px}.pitch-row{display:grid;grid-template-columns:120px 50px 1fr 52px;gap:10px;align-items:center}.pitch-row>span{color:var(--color-muted-text);font-size:12px}.pitch-row>div{height:9px;border-radius:99px;background:var(--color-background);overflow:hidden}.pitch-row i{display:block;height:100%;border-radius:inherit}.pitch-row>strong{text-align:right;background:none}.trend-panel svg{width:100%;height:300px;padding:14px 22px 8px;overflow:visible}.trend-panel text{fill:var(--color-muted-text);font-size:11px}.axis-title{font-size:12px;font-weight:800}.axis-line{stroke:#8792a6;stroke-width:1.2}.grid-line{stroke:var(--color-border);stroke-width:1}.trend-line{fill:none;stroke:var(--color-primary);stroke-width:3;stroke-linejoin:round;stroke-linecap:round}.table-scroll{max-height:620px;overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:13px 16px;border-bottom:1px solid var(--color-border);text-align:left}th{position:sticky;top:0;background:var(--color-surface);color:var(--color-muted-text);font-size:11px;text-transform:uppercase;cursor:pointer}tbody tr{cursor:pointer}tbody tr:hover,tbody tr.selected{background:color-mix(in srgb,var(--color-primary) 10%,transparent)}.leaderboard-panel td strong.plus-high,.leaderboard-panel td strong.plus-average,.leaderboard-panel td strong.plus-low{display:inline;color:inherit;background:transparent!important}.leaderboard-panel td strong.plus-high{color:#f0a238!important}.leaderboard-panel td strong.plus-average{color:var(--color-foreground)!important}.leaderboard-panel td strong.plus-low{color:#8196ff!important}.candidate-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;padding:18px}.candidate-grid article{border:1px solid var(--color-border);border-radius:10px;padding:16px}.candidate-grid article.public{border-color:var(--color-primary)}.candidate-grid h3{display:flex;justify-content:space-between;text-transform:capitalize}.candidate-grid h3 span{border-radius:999px;padding:4px 8px;background:var(--color-primary);color:var(--color-on-primary);font-size:11px}.candidate-grid dl{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.candidate-grid dl div{padding:10px;background:var(--color-background)}dt{color:var(--color-muted-text);font-size:11px}dd{margin:4px 0 0;font-weight:900}.validation-note{padding:0 18px 18px;color:var(--color-muted-text);line-height:1.55}.error-panel{padding:18px;border:1px solid #d44;border-radius:10px;color:#ff9e9e}.pitching-page :deep(.comparison-page-header){margin-bottom:0}@media(max-width:900px){.control-bar{grid-template-columns:1fr 1fr}.search,.model-badge{grid-column:1/-1}.summary-grid{grid-template-columns:repeat(2,1fr)}.top-grid{grid-template-columns:1fr}}@media(max-width:600px){.summary-grid,.candidate-grid{grid-template-columns:1fr}.pitch-row{grid-template-columns:90px 40px 1fr 44px}}
.pitching-page{width:100%;max-width:100%;min-width:0;gap:14px;overflow:hidden}.pitching-page>*{min-width:0}.control-bar,.summary-grid,.top-grid{min-width:0;gap:10px}.control-bar{grid-template-columns:120px 160px minmax(260px,1fr) auto;grid-template-areas:"season team innings badge" "search search search search";padding:12px 14px}.season-control{grid-area:season}.team-control{grid-area:team}.innings-control{grid-area:innings;min-width:0}.search{grid-area:search}.model-badge{grid-area:badge;max-width:220px;justify-self:end;align-self:end;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.innings-control span{display:flex;justify-content:space-between;gap:12px}.innings-control b{color:var(--color-foreground)}.panel{min-width:0;overflow:hidden}.loading-panel{padding:28px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface);color:var(--color-muted-text)}.trend-dot{fill:var(--color-primary);stroke:var(--color-surface);stroke-width:2}.empty-chart{padding:0 18px 18px;color:var(--color-muted-text)}.table-scroll{width:100%;max-width:100%;overflow:auto}.leaderboard-panel table{min-width:1480px}.leaderboard-panel th,.leaderboard-panel td{padding:11px 12px;white-space:nowrap}.leaderboard-panel th:nth-child(1),.leaderboard-panel td:nth-child(1){position:sticky;left:0;z-index:2;width:48px;background:var(--color-surface)}.leaderboard-panel th:nth-child(2),.leaderboard-panel td:nth-child(2){position:sticky;left:48px;z-index:2;min-width:190px;background:var(--color-surface)}.leaderboard-panel th:nth-child(-n+2){z-index:4}.leaderboard-panel tbody tr:hover td:nth-child(-n+2),.leaderboard-panel tbody tr.selected td:nth-child(-n+2){background:color-mix(in srgb,var(--color-primary) 10%,var(--color-surface))}.pitch-score{text-align:center;font-variant-numeric:tabular-nums}@media(max-width:1100px){.control-bar{grid-template-columns:1fr 1fr;grid-template-areas:"season team" "innings innings" "search search" "badge badge"}.model-badge{justify-self:start}.top-grid{grid-template-columns:1fr}}@media(max-width:700px){.control-bar{grid-template-columns:1fr;grid-template-areas:"season" "team" "innings" "search" "badge"}.summary-grid{grid-template-columns:1fr 1fr}}
.freshness-note{padding:10px 14px;border:1px solid var(--color-border);border-radius:0;color:var(--color-muted-text);font-size:12px}.freshness-note.stale{border-color:var(--color-warning,#d89b3c);color:var(--color-warning,#d89b3c)}
</style>
