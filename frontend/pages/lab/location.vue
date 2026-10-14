<template>
  <main class="location-lab">
    <ComparisonPageHeader
      eyebrow="Location Lab"
      title="Location+ Field"
      description="Explore how pitch location, count and handedness change modeled run value — without pitcher identity or pitch-shape inputs."
      back-to="/lab"
      back-label="Pitcher Lab"
    />

    <section class="control-deck" aria-label="Location heatmap filters">
      <label>
        Data sample
        <select v-model="sample">
          <option value="training">Training baseline · 2021–25</option>
          <option v-for="option in [2026, 2025, 2024, 2023, 2022, 2021]" :key="option" :value="String(option)">{{ option }}</option>
        </select>
      </label>
      <label>
        Pitcher
        <select v-model="pitcherHand">
          <option value="R">Right-handed</option>
          <option value="L">Left-handed</option>
        </select>
      </label>
      <label>
        Batter
        <select v-model="batterSide">
          <option value="R">Right-handed</option>
          <option value="L">Left-handed</option>
        </select>
      </label>
      <label>
        Pitch type
        <select v-model="pitchType">
          <option v-for="option in pitchTypes" :key="option" :value="option">{{ displayPitch(option) }}</option>
        </select>
      </label>
      <label>
        Count
        <select v-model="count">
          <option v-for="option in countOptions" :key="option" :value="option">{{ option === 'All' ? 'All · league mix' : option }}</option>
        </select>
      </label>
    </section>

    <p v-if="errorMessage" class="state-panel state-panel--error">{{ errorMessage }}</p>
    <p v-else-if="pending && !response" class="state-panel">Building the model field…</p>

    <template v-if="response">
      <section class="metric-strip">
        <article><span>Historical sample</span><strong>{{ formatInteger(response.sample_pitches) }}</strong><small>pitches inside the map</small></article>
        <article><span>Context mix</span><strong>{{ response.context_rows }}</strong><small>{{ count === 'All' ? 'weighted game states' : `${count} game states` }}</small></article>
        <article><span>Matchup</span><strong>{{ pitcherHand }}HP → {{ batterSide }}HH</strong><small>{{ displayPitch(pitchType) }}</small></article>
        <article><span>Model</span><strong>v1</strong><small>{{ response.model_version }}</small></article>
      </section>

      <div class="analysis-row">
      <section class="workbench" :class="{ 'is-loading': pending }">
        <header class="mode-bar">
          <div>
            <span>Model surface</span>
            <h2>{{ activeMode.label }}</h2>
          </div>
          <div class="mode-actions">
            <div class="view-toggle" role="group" aria-label="Chart viewpoint">
              <button type="button" :class="{ active: viewMode === 'catcher' }" @click="viewMode = 'catcher'">Catcher view</button>
              <button type="button" :class="{ active: viewMode === 'pitcher' }" @click="viewMode = 'pitcher'">Pitcher view</button>
            </div>
            <div class="mode-tabs" role="tablist" aria-label="Heatmap metric">
              <button
                v-for="option in modes"
                :key="option.key"
                type="button"
                role="tab"
                :aria-selected="mode === option.key"
                :class="{ active: mode === option.key }"
                @click="mode = option.key"
              >{{ option.short }}</button>
            </div>
          </div>
        </header>

        <div class="map-layout">
          <section class="heatmap-panel">
            <div class="map-heading">
              <div><b>{{ leftFieldSide }}</b><span>← {{ viewMode }} view →</span><b>{{ rightFieldSide }}</b></div>
              <small>{{ activeMode.note }}</small>
            </div>
            <svg viewBox="0 0 620 620" role="img" :aria-label="`${activeMode.label} heatmap`" @mouseleave="hoveredCell = null">
              <g class="heat-cells">
                <polygon
                  v-for="cell in response.cells"
                  :key="`${cell.x}-${cell.z}`"
                  :points="hexPoints(cell)"
                  :fill="cellColor(cell)"
                  :stroke="cellColor(cell)"
                  stroke-width="7"
                  stroke-linejoin="round"
                  tabindex="0"
                  @mouseenter="hoveredCell = cell"
                  @focus="hoveredCell = cell"
                  @click="selectedCell = cell"
                />
              </g>
              <rect
                class="strike-zone"
                :x="scaleX(response.strike_zone[0])"
                :y="scaleZ(response.strike_zone[3])"
                :width="scaleX(response.strike_zone[2]) - scaleX(response.strike_zone[0])"
                :height="scaleZ(response.strike_zone[1]) - scaleZ(response.strike_zone[3])"
              />
              <path class="plate" d="M252 574 L285 558 L335 558 L368 574 L310 596 Z" />
              <text x="28" y="310" class="axis-label" transform="rotate(-90 28 310)">PLATE HEIGHT</text>
              <text x="310" y="614" class="axis-label">HORIZONTAL LOCATION</text>
            </svg>
            <div class="legend">
              <span>{{ activeMode.low }}</span>
              <i :style="{ background: legendGradient }" />
              <span>{{ activeMode.high }}</span>
            </div>
          </section>

          <aside class="cell-inspector">
            <header><span>Selected location</span><strong>{{ selectedOrHovered ? formatCellLocation(selectedOrHovered) : 'Hover map' }}</strong></header>
            <div v-if="selectedOrHovered" class="inspector-score">
              <span>{{ activeMode.label }}</span>
              <strong>{{ formatActiveValue(selectedOrHovered) }}</strong>
              <small>{{ activeMode.unit }}</small>
            </div>
            <div v-if="selectedOrHovered" class="outcome-grid">
              <div><span>Location+</span><strong>{{ selectedOrHovered.location_plus.toFixed(1) }}</strong></div>
              <div><span>xRV / pitch</span><strong>{{ signed(selectedOrHovered.xrv, 3) }}</strong></div>
              <div><span>Called strike</span><strong>{{ selectedOrHovered.called_strike_pct.toFixed(1) }}%</strong></div>
              <div><span>Whiff</span><strong>{{ selectedOrHovered.whiff_pct.toFixed(1) }}%</strong></div>
              <div><span>Barrel</span><strong>{{ selectedOrHovered.barrel_pct.toFixed(1) }}%</strong></div>
              <div><span>Ball</span><strong>{{ selectedOrHovered.ball_pct.toFixed(1) }}%</strong></div>
              <div class="wide"><span>Observed pitches</span><strong>{{ formatInteger(selectedOrHovered.density_count) }}</strong></div>
            </div>
            <p v-else>Move across the field to inspect the model probabilities for one exact location. Click a cell to keep it selected.</p>
            <footer>
              <b>{{ count === 'All' ? 'League mix' : `${count} count` }}</b>
              <span>{{ count === 'All' ? 'Count, outs and base states are weighted by the selected historical sample.' : 'Outs and base states remain historically weighted.' }}</span>
            </footer>
          </aside>
        </div>
      </section>

      <section class="pitcher-detail compact-detail">
        <p v-if="detailPending" class="detail-state">Loading pitcher detail…</p>
        <template v-else-if="pitcherDetail">
          <header class="pitcher-detail__hero">
            <div><span>{{ pitcherDetail.pitcher.team }} · {{ pitcherDetail.pitcher.pitches }} pitches</span><h2>{{ pitcherDetail.pitcher.pitcher_name }}</h2></div>
            <strong>{{ pitcherDetail.pitcher.location_plus.toFixed(1) }}<small>Location+</small></strong>
          </header>
          <div class="detail-metrics">
            <div><span>xRV / 100</span><strong>{{ signed(pitcherDetail.pitcher.xrv_per_100, 3) }}</strong></div>
            <div><span>vs LHH</span><strong>{{ formatNullable(pitcherDetail.pitcher.location_plus_vs_l) }}</strong></div>
            <div><span>vs RHH</span><strong>{{ formatNullable(pitcherDetail.pitcher.location_plus_vs_r) }}</strong></div>
            <div><span>Uncertainty</span><strong>± {{ pitcherDetail.pitcher.location_plus_se.toFixed(1) }}</strong></div>
          </div>
          <div class="detail-table-block">
            <header><h3>Pitch-type matrix</h3><span>50 pitches to qualify</span></header>
            <div class="table-scroll"><table><thead><tr><th>Pitch</th><th>Pitches</th><th>Location+</th><th>xRV/100</th><th>Called%</th><th>Whiff%</th><th>Barrel%</th></tr></thead><tbody>
              <tr v-for="row in pitcherDetail.pitch_types" :key="row.pitch_name"><td><strong>{{ displayPitch(row.pitch_name) }}</strong><small>{{ row.sample_status }}</small></td><td>{{ row.pitches }}</td><td class="plus">{{ row.location_plus.toFixed(1) }}</td><td>{{ signed(row.xrv_per_100, 3) }}</td><td>{{ row.called_strike_pct.toFixed(1) }}</td><td>{{ row.whiff_pct.toFixed(1) }}</td><td>{{ row.barrel_pct.toFixed(1) }}</td></tr>
            </tbody></table></div>
          </div>
          <div class="detail-table-block">
            <header><h3>Recent outings</h3><span>Latest 20 appearances</span></header>
            <div class="table-scroll outing-scroll"><table><thead><tr><th>Date</th><th>Pitches</th><th>Location+</th><th>xRV/100</th><th>Called%</th><th>Whiff%</th><th>± SE</th></tr></thead><tbody>
              <tr v-for="row in pitcherDetail.outings" :key="row.game_pk"><td>{{ row.game_date }}</td><td>{{ row.pitches }}</td><td class="plus">{{ row.location_plus.toFixed(1) }}</td><td>{{ signed(row.xrv_per_100, 3) }}</td><td>{{ row.called_strike_pct.toFixed(1) }}</td><td>{{ row.whiff_pct.toFixed(1) }}</td><td>{{ row.location_plus_se.toFixed(1) }}</td></tr>
            </tbody></table></div>
          </div>
        </template>
        <p v-else class="detail-state">Select a pitcher from the league board.</p>
      </section>
      </div>

      <section v-if="response.warnings.length" class="method-note">
        <strong>Model note</strong>
        <p v-for="warning in response.warnings" :key="warning">{{ warning }}</p>
      </section>

      <section class="league-lab">
        <header class="league-header">
          <div><span>Batch inference · 2026</span><h2>League Location+ board</h2><p>Every pitcher with Statcast location data. Select a row to inspect pitch types and recent outings.</p></div>
          <div class="league-controls">
            <label>Search<input v-model="leaderboardSearch" type="search" placeholder="Pitcher or team"></label>
            <label>Minimum pitches<select v-model.number="minimumPitches"><option :value="100">100 · Matched sample</option><option :value="300">300 · Qualified</option><option :value="500">500 · Stable</option><option :value="0">All · Provisional</option></select></label>
          </div>
        </header>

        <p v-if="leaderboardError" class="state-panel state-panel--error">{{ leaderboardError }}</p>
        <div v-else>
          <section class="leaderboard-panel">
            <header><strong>{{ sortedLeaderboard.length }} pitchers</strong><span>{{ leaderboardPending ? 'Loading…' : 'Click a row to inspect · click any heading to sort' }}</span></header>
            <div class="table-scroll leaderboard-scroll">
              <table class="fangraphs-table">
                <thead><tr>
                  <th v-for="column in leaderboardColumns" :key="column.key" :class="{ 'metric-divider': column.key === 'location_plus' }">
                    <button type="button" @click="toggleSort(column.key)">{{ column.label }} <span>{{ sortMark(column.key) }}</span></button>
                  </th>
                </tr></thead>
                <tbody>
                  <tr v-for="(row, index) in sortedLeaderboard" :key="`${row.pitcher_id}-${row.pitcher_name}`" :class="{ selected: selectedPitcherId === row.pitcher_id }" @click="selectedPitcherId = row.pitcher_id">
                    <td>{{ index + 1 }}</td><td><strong>{{ row.pitcher_name }}</strong><small>{{ row.sample_status }}</small></td><td>{{ row.team }}</td><td>{{ formatInteger(row.pitches) }}</td>
                    <td v-for="key in pitchColumnKeys" :key="key">{{ formatNullable(row[key]) }}</td>
                    <td class="plus metric-divider">{{ row.location_plus.toFixed(1) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </section>

      <section v-if="comparison && activeComparison" class="comparison-panel">
        <header class="comparison-header">
          <div><span>External benchmark · FanGraphs 2026</span><h2>{{ activeComparison.label }} regression</h2><p>Matched by MLBAMID. OLS predicts FanGraphs Location+ from this model's Location+.</p></div>
          <strong>{{ activeComparison.statistics.matched_pitchers }}<small>matched pitchers</small></strong>
        </header>
        <div class="regression-tabs" role="tablist" aria-label="Regression pitch type">
          <button v-for="item in comparison.series" :key="item.key" type="button" role="tab" :aria-selected="activeComparisonKey === item.key" :class="{ active: activeComparisonKey === item.key }" @click="activeComparisonKey = item.key">{{ item.label }}</button>
        </div>
        <div class="comparison-body">
          <div class="comparison-stats">
            <article><span>Pearson r</span><strong>{{ activeComparison.statistics.pearson_r.toFixed(3) }}</strong><small>linear agreement</small></article>
            <article><span>Spearman ρ</span><strong>{{ activeComparison.statistics.spearman_rho.toFixed(3) }}</strong><small>ranking agreement</small></article>
            <article><span>R²</span><strong>{{ activeComparison.statistics.r_squared.toFixed(3) }}</strong><small>OLS explained variance</small></article>
            <article><span>MAE</span><strong>{{ activeComparison.statistics.mae.toFixed(2) }}</strong><small>Location+ points</small></article>
            <article><span>RMSE</span><strong>{{ activeComparison.statistics.rmse.toFixed(2) }}</strong><small>penalizes large gaps</small></article>
            <article><span>OLS</span><strong>{{ activeComparison.statistics.slope.toFixed(2) }}x {{ signed(activeComparison.statistics.intercept, 1) }}</strong><small>FanGraphs = slope × ours + intercept</small></article>
          </div>
          <div class="scatter-card">
            <svg viewBox="0 0 520 360" role="img" aria-label="Our Location plus compared with FanGraphs Location plus">
              <line x1="52" y1="310" x2="492" y2="40" class="identity-line" />
              <line :x1="comparisonX(comparisonDomain[0])" :y1="regressionY(comparisonDomain[0])" :x2="comparisonX(comparisonDomain[1])" :y2="regressionY(comparisonDomain[1])" class="regression-line" />
              <circle v-for="point in activeComparison.points" :key="point.pitcher_id" :cx="comparisonX(point.ours)" :cy="comparisonY(point.fangraphs)" r="3.2"><title>{{ point.pitcher_name }}: ours {{ point.ours.toFixed(1) }}, FanGraphs {{ point.fangraphs.toFixed(1) }}</title></circle>
              <text x="270" y="350">Our Location+</text><text x="16" y="180" transform="rotate(-90 16 180)">FanGraphs Location+</text>
            </svg>
          </div>
        </div>
        <div class="table-scroll sensitivity-scroll"><table><thead><tr><th>Metric</th><th>Minimum pitches</th><th>Matched</th><th>Pearson r</th><th>Spearman ρ</th><th>R²</th><th>MAE</th><th>RMSE</th><th>Slope</th><th>Intercept</th></tr></thead><tbody>
          <tr v-for="item in comparison.series" :key="item.key" :class="{ selected: activeComparisonKey === item.key }" @click="activeComparisonKey = item.key"><td><strong>{{ item.label }}</strong></td><td>{{ item.statistics.minimum_pitches }}</td><td>{{ item.statistics.matched_pitchers }}</td><td>{{ item.statistics.pearson_r.toFixed(3) }}</td><td>{{ item.statistics.spearman_rho.toFixed(3) }}</td><td>{{ item.statistics.r_squared.toFixed(3) }}</td><td>{{ item.statistics.mae.toFixed(2) }}</td><td>{{ item.statistics.rmse.toFixed(2) }}</td><td>{{ item.statistics.slope.toFixed(3) }}</td><td>{{ item.statistics.intercept.toFixed(2) }}</td></tr>
        </tbody></table></div>
        <footer><strong>Sample alignment</strong><span>Overall uses the active leaderboard minimum; pitch types use at least 50 pitches after Slider and Sweeper are combined. A regression requires at least 20 matched pitchers, so Forkball is omitted with only two. The dashed line is perfect agreement and the orange line is OLS.</span></footer>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import type { LocationComparisonResponse, LocationHeatmapCell, LocationHeatmapResponse, LocationLeaderboardResponse, LocationLeaderboardRow, LocationPitcherResponse } from '~/types/api'

type ModeKey = 'location_plus' | 'called_strike_pct' | 'whiff_pct' | 'barrel_pct' | 'ball_pct' | 'density_pct'
type SortKey = 'rank' | 'pitcher_name' | 'team' | 'pitches' | 'loc_fa' | 'loc_si' | 'loc_fc' | 'loc_fs' | 'loc_sl' | 'loc_cu' | 'loc_ch' | 'loc_kc' | 'loc_fo' | 'location_plus'

const api = useApi()
const sample = ref('training')
const pitcherHand = ref('R')
const batterSide = ref('R')
const pitchType = ref('4-Seam Fastball')
const count = ref('All')
const mode = ref<ModeKey>('location_plus')
const viewMode = ref<'catcher' | 'pitcher'>('catcher')
const response = ref<LocationHeatmapResponse | null>(null)
const pending = ref(false)
const errorMessage = ref('')
const hoveredCell = ref<LocationHeatmapCell | null>(null)
const selectedCell = ref<LocationHeatmapCell | null>(null)
const leaderboard = ref<LocationLeaderboardResponse | null>(null)
const pitcherDetail = ref<LocationPitcherResponse | null>(null)
const comparison = ref<LocationComparisonResponse | null>(null)
const minimumPitches = ref(100)
const leaderboardSearch = ref('')
const selectedPitcherId = ref(0)
const activeComparisonKey = ref('overall')
const sortKey = ref<SortKey>('location_plus')
const sortDirection = ref<'asc' | 'desc'>('desc')
const leaderboardPending = ref(false)
const detailPending = ref(false)
const leaderboardError = ref('')
let requestToken = 0
let refreshTimer: ReturnType<typeof setTimeout> | null = null

const fallbackPitchTypes = ['4-Seam Fastball', 'Sinker', 'Cutter', 'Slider', 'Sweeper', 'Curveball', 'Knuckle Curve', 'Changeup', 'Split-Finger']
const pitchTypes = computed(() => response.value?.pitch_types || fallbackPitchTypes)
const countOptions = computed(() => response.value?.counts || ['All', '0-0', '0-1', '0-2', '1-0', '1-1', '1-2', '2-0', '2-1', '2-2', '3-0', '3-1', '3-2'])
const selectedOrHovered = computed(() => hoveredCell.value || selectedCell.value)
const leftFieldSide = computed(() => viewMode.value === 'catcher' ? '3B side' : '1B side')
const rightFieldSide = computed(() => viewMode.value === 'catcher' ? '1B side' : '3B side')
const filteredLeaderboard = computed(() => {
  const query = leaderboardSearch.value.trim().toLowerCase()
  const uniqueRows = [...new Map((leaderboard.value?.rows || []).map(row => [row.pitcher_id, row])).values()]
  if (!query) return uniqueRows
  return uniqueRows.filter((row) => row.pitcher_name.toLowerCase().includes(query) || row.team.toLowerCase().includes(query))
})
const pitchColumnKeys = ['loc_fa', 'loc_si', 'loc_fc', 'loc_fs', 'loc_sl', 'loc_cu', 'loc_ch', 'loc_kc', 'loc_fo'] as const
const leaderboardColumns: { key: SortKey; label: string }[] = [
  { key: 'rank', label: '#' }, { key: 'pitcher_name', label: 'Pitcher' }, { key: 'team', label: 'Team' }, { key: 'pitches', label: 'Pitches' },
  { key: 'loc_fa', label: 'Loc+ FA' }, { key: 'loc_si', label: 'Loc+ SI' }, { key: 'loc_fc', label: 'Loc+ FC' },
  { key: 'loc_fs', label: 'Loc+ FS' }, { key: 'loc_sl', label: 'Loc+ SL' }, { key: 'loc_cu', label: 'Loc+ CU' },
  { key: 'loc_ch', label: 'Loc+ CH' }, { key: 'loc_kc', label: 'Loc+ KC' }, { key: 'loc_fo', label: 'Loc+ FO' },
  { key: 'location_plus', label: 'Location+' }
]
const sortedLeaderboard = computed(() => [...filteredLeaderboard.value].sort((left, right) => compareRows(left, right, sortKey.value, sortDirection.value)))
const activeComparison = computed(() => comparison.value?.series.find(item => item.key === activeComparisonKey.value) || comparison.value?.series[0] || null)
const comparisonDomain = computed(() => {
  const values = activeComparison.value?.points.flatMap(point => [point.ours, point.fangraphs]) || [60, 140]
  return [Math.floor(Math.min(...values) / 10) * 10, Math.ceil(Math.max(...values) / 10) * 10] as const
})
const modes: { key: ModeKey; short: string; label: string; note: string; low: string; high: string; unit: string }[] = [
  { key: 'location_plus', short: 'Location+', label: 'Location+ field', note: 'Higher is better for the pitcher.', low: 'Hitter advantage', high: 'Pitcher advantage', unit: 'index' },
  { key: 'called_strike_pct', short: 'Called strike', label: 'Called-strike probability', note: 'Model probability before the pitch result is known.', low: '0%', high: '100%', unit: '%' },
  { key: 'whiff_pct', short: 'Whiff', label: 'Swinging-strike probability', note: 'Unconditional probability per pitch.', low: '0%', high: '50%+', unit: '%' },
  { key: 'barrel_pct', short: 'Barrel', label: 'Barrel probability', note: 'Lower is better for the pitcher.', low: 'Low risk', high: 'High risk', unit: '%' },
  { key: 'ball_pct', short: 'Ball', label: 'Ball probability', note: 'Includes blocked balls and pitchouts in training.', low: '0%', high: '100%', unit: '%' },
  { key: 'density_pct', short: 'Pitch density', label: 'Observed pitch density', note: 'Historical usage, not a model prediction.', low: 'Rare', high: 'Frequent', unit: '% of peak cell' }
]
const activeMode = computed(() => modes.find((option) => option.key === mode.value) || modes[0])
const legendGradient = computed(() => mode.value === 'location_plus' ? 'linear-gradient(90deg, rgb(15, 23, 96), rgb(37, 99, 235) 30%, rgb(248, 248, 245) 50%, rgb(239, 68, 68) 70%, rgb(127, 29, 29))' : mode.value === 'barrel_pct' ? 'linear-gradient(90deg, #2929f4, #fbfaf7 55%, #db7657)' : 'linear-gradient(90deg, #fbfaf7, #efc3ad 55%, #db7657)')
const cellWidth = computed(() => 520 / (response.value?.grid_size || 25))
const cellHeight = computed(() => 520 / (response.value?.grid_size || 25))
const locationColorSpan = computed(() => {
  const values = (response.value?.cells || [])
    .map(cell => Number(cell.location_plus))
    .filter(Number.isFinite)
    .sort((left, right) => left - right)
  if (!values.length) return 10
  const quantile = (fraction: number) => values[Math.min(values.length - 1, Math.max(0, Math.round((values.length - 1) * fraction)))]
  const robustDistance = Math.max(Math.abs(quantile(0.1) - 100), Math.abs(quantile(0.9) - 100))
  return Math.min(20, Math.max(4, robustDistance))
})

watch([sample, pitcherHand, batterSide, pitchType, count], scheduleLoad)
watch(minimumPitches, () => { loadLeaderboard(); loadComparison() })
watch(selectedPitcherId, loadPitcherDetail)
onMounted(() => { loadHeatmap(); loadLeaderboard(); loadComparison() })

function scheduleLoad() {
  if (refreshTimer) clearTimeout(refreshTimer)
  refreshTimer = setTimeout(loadHeatmap, 120)
}

async function loadHeatmap() {
  const token = ++requestToken
  pending.value = true
  errorMessage.value = ''
  try {
    const payload = await api.locationHeatmap({ sample: sample.value, pitcherHand: pitcherHand.value, batterSide: batterSide.value, pitchType: pitchType.value, count: count.value })
    if (token !== requestToken) return
    response.value = payload
    selectedCell.value = payload.cells[Math.floor(payload.cells.length / 2)] || null
  } catch (error) {
    if (token === requestToken) errorMessage.value = error instanceof Error ? error.message : 'Location heatmap failed.'
  } finally {
    if (token === requestToken) pending.value = false
  }
}

async function loadLeaderboard() {
  leaderboardPending.value = true
  leaderboardError.value = ''
  try {
    leaderboard.value = await api.locationLeaderboard({ year: 2026, minimumPitches: minimumPitches.value })
    if (!leaderboard.value.rows.some((row) => row.pitcher_id === selectedPitcherId.value)) selectedPitcherId.value = leaderboard.value.rows[0]?.pitcher_id || 0
    else await loadPitcherDetail()
  } catch (error) {
    leaderboardError.value = error instanceof Error ? error.message : 'Location+ leaderboard failed.'
  } finally {
    leaderboardPending.value = false
  }
}

async function loadPitcherDetail() {
  if (!selectedPitcherId.value) return
  const pitcherId = selectedPitcherId.value
  detailPending.value = true
  try {
    const payload = await api.locationPitcher({ year: 2026, pitcherId })
    if (pitcherId === selectedPitcherId.value) pitcherDetail.value = payload
  } catch (error) {
    if (pitcherId === selectedPitcherId.value) leaderboardError.value = error instanceof Error ? error.message : 'Pitcher Location+ detail failed.'
  } finally {
    if (pitcherId === selectedPitcherId.value) detailPending.value = false
  }
}

async function loadComparison() {
  try {
    comparison.value = await api.locationComparison({ year: 2026, minimumPitches: minimumPitches.value })
  } catch {
    comparison.value = null
  }
}

function compareRows(left: LocationLeaderboardRow, right: LocationLeaderboardRow, key: SortKey, direction: 'asc' | 'desc') {
  const leftValue = left[key]
  const rightValue = right[key]
  if (leftValue == null) return rightValue == null ? 0 : 1
  if (rightValue == null) return -1
  const result = typeof leftValue === 'string'
    ? leftValue.localeCompare(String(rightValue))
    : Number(leftValue) - Number(rightValue)
  return direction === 'asc' ? result : -result
}
function toggleSort(key: SortKey) {
  if (sortKey.value === key) sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  else {
    sortKey.value = key
    sortDirection.value = key === 'pitcher_name' || key === 'team' || key === 'rank' ? 'asc' : 'desc'
  }
}
function sortMark(key: SortKey) { return sortKey.value === key ? (sortDirection.value === 'asc' ? '↑' : '↓') : '↕' }
function comparisonX(value: number) {
  const [low, high] = comparisonDomain.value
  return 52 + ((value - low) / Math.max(1, high - low)) * 440
}
function comparisonY(value: number) {
  const [low, high] = comparisonDomain.value
  return 310 - ((value - low) / Math.max(1, high - low)) * 270
}
function regressionY(value: number) {
  const statistics = activeComparison.value?.statistics
  return comparisonY(statistics ? statistics.slope * value + statistics.intercept : value)
}

function scaleX(value: number) {
  const domain = response.value?.x_domain || [-2, 2]
  return 50 + ((value - domain[0]) / (domain[1] - domain[0])) * 520
}
function scaleZ(value: number) {
  const domain = response.value?.z_domain || [0.5, 4.5]
  return 570 - ((value - domain[0]) / (domain[1] - domain[0])) * 520
}
function displayX(value: number) { return viewMode.value === 'catcher' ? value : -value }
function hexPoints(cell: LocationHeatmapCell) {
  const centerX = scaleX(displayX(cell.x))
  const centerY = scaleZ(cell.z)
  const radiusX = cellWidth.value * 0.58
  const radiusY = cellHeight.value * 0.56
  return [
    [centerX, centerY - radiusY],
    [centerX + radiusX, centerY - radiusY / 2],
    [centerX + radiusX, centerY + radiusY / 2],
    [centerX, centerY + radiusY],
    [centerX - radiusX, centerY + radiusY / 2],
    [centerX - radiusX, centerY - radiusY / 2]
  ].map((point) => point.join(',')).join(' ')
}
function valueFor(cell: LocationHeatmapCell) { return Number(cell[mode.value]) }
function clamp(value: number, low = 0, high = 1) { return Math.min(high, Math.max(low, value)) }
function mixColor(from: [number, number, number], to: [number, number, number], amount: number) {
  return `rgb(${from.map((value, index) => Math.round(value + (to[index] - value) * amount)).join(',')})`
}
function locationHeatColor(value: number) {
  const position = clamp(0.5 + (value - 100) / (2 * locationColorSpan.value))
  if (position < 0.3) return mixColor([15, 23, 96], [37, 99, 235], position / 0.3)
  if (position < 0.5) return mixColor([37, 99, 235], [248, 248, 245], (position - 0.3) / 0.2)
  if (position < 0.7) return mixColor([248, 248, 245], [239, 68, 68], (position - 0.5) / 0.2)
  return mixColor([239, 68, 68], [127, 29, 29], (position - 0.7) / 0.3)
}
function cellColor(cell: LocationHeatmapCell) {
  const value = valueFor(cell)
  if (mode.value === 'location_plus') return locationHeatColor(value)
  if (mode.value === 'barrel_pct') {
    const position = clamp(value / 12)
    return position < 0.45 ? mixColor([41, 41, 244], [251, 250, 247], position / 0.45) : mixColor([251, 250, 247], [219, 118, 87], (position - 0.45) / 0.55)
  }
  const maximum = mode.value === 'whiff_pct' ? 50 : 100
  return mixColor([251, 250, 247], [219, 118, 87], clamp(value / maximum))
}
function displayPitch(value: string) { return value === '4-Seam Fastball' ? '4-Seam' : value === 'Split-Finger' ? 'Splitter' : value }
function formatInteger(value: number) { return new Intl.NumberFormat('en-US').format(value) }
function formatNullable(value: number | null) { return value == null ? '—' : value.toFixed(1) }
function signed(value: number, digits: number) { return `${value > 0 ? '+' : ''}${value.toFixed(digits)}` }
function formatCellLocation(cell: LocationHeatmapCell) { return `${signed(displayX(cell.x), 2)} x · ${cell.z.toFixed(2)} z` }
function formatActiveValue(cell: LocationHeatmapCell) { return mode.value === 'location_plus' ? cell.location_plus.toFixed(1) : valueFor(cell).toFixed(1) }
</script>

<style scoped>
.location-lab { display: grid; gap: 18px; }
.control-deck { display: grid; grid-template-columns: 1.35fr repeat(4, 1fr); gap: 12px; border: 1px solid var(--color-border); border-radius: 18px; padding: 16px; background: var(--color-surface); box-shadow: var(--shadow-sm); }
.control-deck label { display: grid; gap: 7px; color: var(--color-muted-text); font-size: 11px; font-weight: 900; letter-spacing: .06em; text-transform: uppercase; }
.control-deck select { width: 100%; min-width: 0; height: 44px; border: 1px solid var(--color-border-strong); border-radius: 10px; padding: 0 12px; color: var(--color-text); background: var(--color-background); font: 750 13px inherit; }
.state-panel { margin: 0; border: 1px solid var(--color-border); border-radius: 14px; padding: 18px; color: var(--color-muted-text); background: var(--color-surface); }
.state-panel--error { color: #ff8a8a; }
.metric-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.metric-strip article { display: grid; gap: 5px; min-height: 112px; border: 1px solid var(--color-border); border-radius: 16px; padding: 17px 19px; background: linear-gradient(145deg, color-mix(in srgb, var(--color-accent) 8%, var(--color-surface)), var(--color-surface) 62%); }
.metric-strip span, .mode-bar span, .cell-inspector header span { color: var(--color-accent); font-size: 11px; font-weight: 900; letter-spacing: .09em; text-transform: uppercase; }
.metric-strip strong { color: var(--color-text); font: 900 29px "Fira Code", monospace; }
.metric-strip small { color: var(--color-muted-text); font-size: 11px; }
.analysis-row { display: grid; grid-template-columns: minmax(0, 1.04fr) minmax(0, .96fr); align-items: stretch; gap: 14px; }
.workbench { overflow: hidden; border: 1px solid var(--color-border); border-radius: 20px; background: var(--color-surface); box-shadow: var(--shadow-sm); transition: opacity .15s ease; }
.workbench.is-loading { opacity: .72; }
.mode-bar { display: flex; align-items: center; justify-content: space-between; gap: 18px; border-bottom: 1px solid var(--color-border); padding: 16px 18px; }
.mode-bar h2 { margin: 4px 0 0; color: var(--color-text); font-size: 23px; }
.mode-actions { display: grid; justify-items: end; gap: 7px; }
.mode-tabs, .view-toggle { display: flex; flex-wrap: wrap; gap: 5px; padding: 4px; border-radius: 11px; background: var(--color-background); }
.mode-tabs button, .view-toggle button { border: 0; border-radius: 8px; padding: 9px 12px; color: var(--color-muted-text); background: transparent; font: 850 11px inherit; cursor: pointer; }
.mode-tabs button:hover, .view-toggle button:hover { color: var(--color-text); }
.mode-tabs button.active { color: #101217; background: var(--color-accent); }
.view-toggle button.active { color: #eef1ff; background: #3838dc; box-shadow: inset 0 0 0 1px #6868ff; }
.map-layout { display: grid; grid-template-columns: minmax(580px, 1.25fr) minmax(310px, .65fr); min-height: 700px; }
.analysis-row .map-layout { grid-template-columns: minmax(360px, 1fr) minmax(220px, .48fr); min-height: 620px; }
.heatmap-panel { display: grid; grid-template-rows: auto 1fr auto; border-right: 1px solid var(--color-border); padding: 18px; background: #f7f7f4; }
.map-heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.map-heading div { display: flex; gap: 12px; color: #696969; font-size: 11px; }
.map-heading b { color: #202020; }
.map-heading small { color: #696969; }
.heatmap-panel svg { width: min(100%, 690px); height: auto; margin: 0 auto; display: block; background: #f7f7f4; }
.analysis-row .heatmap-panel svg { width: min(100%, 500px); }
.analysis-row .mode-bar { align-items: flex-start; padding: 13px 15px; }
.analysis-row .mode-bar h2 { font-size: 21px; }
.analysis-row .mode-tabs button, .analysis-row .view-toggle button { padding: 8px 10px; font-size: 11px; }
.analysis-row .cell-inspector header { padding: 16px; }
.analysis-row .inspector-score { padding: 18px 16px; }
.analysis-row .inspector-score strong { font-size: 34px; }
.analysis-row .outcome-grid div { min-height: 70px; padding: 11px 13px; }
.analysis-row .outcome-grid strong { font-size: 17px; }
.analysis-row .cell-inspector footer { padding: 14px 16px; }
.heat-cells polygon { cursor: crosshair; paint-order: stroke fill; transition: opacity .1s ease; }
.heat-cells polygon:hover, .heat-cells polygon:focus { opacity: .78; outline: none; stroke: #161616; stroke-width: 2; }
.strike-zone { fill: none; stroke: #242424; stroke-width: 2.5; pointer-events: none; }
.plate { fill: none; stroke: #242424; stroke-width: 2.5; pointer-events: none; }
.axis-label { fill: #484848; font: 800 10px "Fira Code", monospace; text-anchor: middle; letter-spacing: .12em; }
.legend { display: grid; grid-template-columns: auto minmax(180px, 1fr) auto; align-items: center; gap: 12px; color: #5d5d5d; font-size: 11px; }
.legend i { height: 8px; border-radius: 99px; }
.cell-inspector { display: flex; flex-direction: column; min-width: 0; }
.cell-inspector header { display: grid; gap: 6px; border-bottom: 1px solid var(--color-border); padding: 22px; }
.cell-inspector header strong { color: var(--color-text); font: 900 20px "Fira Code", monospace; }
.inspector-score { display: grid; grid-template-columns: 1fr auto; align-items: end; gap: 5px 12px; padding: 28px 22px; background: linear-gradient(135deg, color-mix(in srgb, var(--color-accent) 12%, transparent), transparent); }
.inspector-score span { color: var(--color-muted-text); font-size: 12px; font-weight: 800; }
.inspector-score strong { grid-row: span 2; color: var(--color-accent); font: 900 50px "Fira Code", monospace; }
.inspector-score small { color: var(--color-muted-text); font-size: 11px; }
.outcome-grid { display: grid; grid-template-columns: repeat(2, 1fr); border-top: 1px solid var(--color-border); }
.outcome-grid div { display: grid; gap: 7px; min-height: 90px; border-right: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); padding: 15px 18px; }
.outcome-grid div:nth-child(even) { border-right: 0; }
.outcome-grid div.wide { grid-column: 1 / -1; border-right: 0; }
.outcome-grid span { color: var(--color-muted-text); font-size: 11px; font-weight: 800; text-transform: uppercase; }
.outcome-grid strong { color: var(--color-text); font: 900 22px "Fira Code", monospace; }
.cell-inspector > p { margin: 0; padding: 24px 22px; color: var(--color-muted-text); line-height: 1.55; }
.cell-inspector footer { display: grid; gap: 7px; margin-top: auto; border-top: 1px solid var(--color-border); padding: 18px 22px; color: var(--color-muted-text); font-size: 12px; line-height: 1.45; }
.cell-inspector footer b { color: var(--color-accent); }
.method-note { border: 1px solid color-mix(in srgb, var(--color-accent) 25%, var(--color-border)); border-radius: 14px; padding: 15px 17px; background: color-mix(in srgb, var(--color-accent) 5%, var(--color-surface)); }
.method-note strong { color: var(--color-accent); }
.method-note p { margin: 6px 0 0; color: var(--color-muted-text); font-size: 12px; }
.league-lab { overflow: hidden; border: 1px solid var(--color-border); border-radius: 20px; background: var(--color-surface); }
.league-header { display: flex; align-items: end; justify-content: space-between; gap: 20px; border-bottom: 1px solid var(--color-border); padding: 19px 21px; }
.league-header > div:first-child { display: grid; gap: 5px; }
.league-header span, .detail-table-block header span { color: var(--color-accent); font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.league-header h2, .detail-table-block h3 { margin: 0; color: var(--color-text); }
.league-header p { margin: 0; color: var(--color-muted-text); font-size: 14px; }
.league-controls { display: flex; gap: 10px; }
.league-controls label { display: grid; gap: 5px; color: var(--color-muted-text); font-size: 11px; font-weight: 850; text-transform: uppercase; }
.league-controls input, .league-controls select { min-width: 170px; height: 42px; border: 1px solid var(--color-border-strong); border-radius: 9px; padding: 0 11px; color: var(--color-text); background: var(--color-background); font: 700 13px inherit; }
.league-layout { display: grid; grid-template-columns: minmax(560px, 1fr) minmax(560px, 1fr); }
.leaderboard-panel { min-width: 0; }
.leaderboard-panel > header { display: flex; justify-content: space-between; padding: 13px 16px; color: var(--color-muted-text); font-size: 13px; }
.leaderboard-scroll { max-height: 760px; overflow: auto; }
.table-scroll { width: 100%; overflow: auto; }
table { width: 100%; min-width: 680px; border-collapse: collapse; }
.fangraphs-table { min-width: 1420px; }
.fangraphs-table th button { width: 100%; border: 0; padding: 0; color: inherit; background: transparent; font: inherit; letter-spacing: inherit; text-align: inherit; text-transform: inherit; cursor: pointer; }
.fangraphs-table th button:hover { color: var(--color-accent); }
.fangraphs-table th button span { margin-left: 3px; opacity: .55; }
.fangraphs-table .metric-divider { border-left: 3px solid var(--color-border-strong); }
th, td { border-bottom: 1px solid var(--color-border); padding: 13px 16px; text-align: right; white-space: nowrap; }
th { position: sticky; top: 0; z-index: 1; color: var(--color-muted-text); background: var(--color-surface); font-size: 10px; letter-spacing: .04em; text-transform: uppercase; }
td { color: var(--color-muted-text); font: 700 12px "Fira Code", monospace; }
th:nth-child(2), td:nth-child(2), .detail-table-block th:first-child, .detail-table-block td:first-child { text-align: left; }
tbody tr { cursor: pointer; transition: background .12s ease; }
tbody tr:hover, tbody tr.selected { background: color-mix(in srgb, var(--color-accent) 8%, transparent); }
tbody tr.selected { box-shadow: inset 3px 0 var(--color-accent); }
td strong { display: block; color: var(--color-text); font-family: inherit; }
td small { display: block; margin-top: 3px; color: var(--color-muted-text); font-size: 10px; text-transform: uppercase; }
td.plus { color: var(--color-accent); font-size: 14px; font-weight: 900; }
.pitcher-detail { min-width: 0; }
.compact-detail { overflow: auto; max-height: 760px; border: 1px solid var(--color-border); border-radius: 20px; background: var(--color-surface); box-shadow: var(--shadow-sm); }
.pitcher-detail__hero { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 112px; padding: 20px; background: linear-gradient(135deg, color-mix(in srgb, var(--color-accent) 13%, transparent), transparent 62%); }
.pitcher-detail__hero span { color: var(--color-muted-text); font-size: 11px; font-weight: 850; text-transform: uppercase; }
.pitcher-detail__hero h2 { margin: 5px 0 0; color: var(--color-text); font-size: 25px; }
.pitcher-detail__hero > strong { color: var(--color-accent); font: 900 42px "Fira Code", monospace; text-align: right; }
.pitcher-detail__hero > strong small { display: block; color: var(--color-muted-text); font: 800 9px inherit; text-transform: uppercase; }
.detail-metrics { display: grid; grid-template-columns: repeat(4, 1fr); border-top: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); }
.detail-metrics div { display: grid; gap: 7px; padding: 14px 16px; border-right: 1px solid var(--color-border); }
.detail-metrics div:last-child { border-right: 0; }
.detail-metrics span { color: var(--color-muted-text); font-size: 11px; font-weight: 850; text-transform: uppercase; }
.detail-metrics strong { color: var(--color-text); font: 900 17px "Fira Code", monospace; }
.detail-table-block header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 16px; }
.detail-table-block h3 { font-size: 17px; }
.detail-table-block table { min-width: 720px; }
.outing-scroll { max-height: 300px; }
.detail-state { margin: 0; padding: 28px; color: var(--color-muted-text); }
.comparison-panel { overflow: hidden; border: 1px solid var(--color-border); border-radius: 20px; background: var(--color-surface); box-shadow: var(--shadow-sm); }
.comparison-header { display: flex; align-items: center; justify-content: space-between; gap: 18px; border-bottom: 1px solid var(--color-border); padding: 20px 22px; }
.comparison-header div { display: grid; gap: 5px; }
.comparison-header span { color: var(--color-accent); font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.comparison-header h2 { margin: 0; color: var(--color-text); font-size: 23px; }
.comparison-header p { margin: 0; color: var(--color-muted-text); font-size: 14px; }
.comparison-header > strong { color: var(--color-accent); font: 900 34px "Fira Code", monospace; text-align: right; }
.comparison-header > strong small { display: block; color: var(--color-muted-text); font: 800 9px inherit; text-transform: uppercase; }
.regression-tabs { display: flex; gap: 6px; overflow-x: auto; border-bottom: 1px solid var(--color-border); padding: 10px 14px; }
.regression-tabs button { flex: 0 0 auto; border: 1px solid var(--color-border); border-radius: 9px; padding: 8px 12px; color: var(--color-muted-text); background: var(--color-background); font: 850 10px inherit; cursor: pointer; }
.regression-tabs button:hover { color: var(--color-text); border-color: var(--color-border-strong); }
.regression-tabs button.active { color: #111318; border-color: var(--color-accent); background: var(--color-accent); }
.comparison-body { display: grid; grid-template-columns: minmax(0, 1fr) minmax(420px, .72fr); border-bottom: 1px solid var(--color-border); }
.comparison-stats { display: grid; grid-template-columns: repeat(3, 1fr); }
.comparison-stats article { display: grid; align-content: center; gap: 7px; min-height: 130px; border-right: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); padding: 18px; }
.comparison-stats span, .comparison-stats small { color: var(--color-muted-text); font-size: 11px; font-weight: 800; text-transform: uppercase; }
.comparison-stats strong { color: var(--color-text); font: 900 23px "Fira Code", monospace; }
.scatter-card { display: grid; place-items: center; padding: 16px; background: color-mix(in srgb, var(--color-background) 72%, var(--color-surface)); }
.scatter-card svg { width: min(100%, 520px); }
.scatter-card circle { fill: color-mix(in srgb, var(--color-accent) 65%, transparent); stroke: var(--color-accent); stroke-width: .5; }
.scatter-card text { fill: var(--color-muted-text); font: 800 11px "Fira Code", monospace; text-anchor: middle; }
.identity-line { stroke: var(--color-border-strong); stroke-width: 1.5; stroke-dasharray: 7 7; }
.regression-line { stroke: var(--color-accent); stroke-width: 2.5; }
.sensitivity-scroll table { min-width: 760px; }
.comparison-panel > footer { display: flex; gap: 12px; padding: 15px 20px; color: var(--color-muted-text); font-size: 13px; line-height: 1.5; }
.comparison-panel > footer strong { flex: 0 0 auto; color: var(--color-accent); }
@media (max-width: 1050px) { .analysis-row { grid-template-columns: 1fr; } .compact-detail { max-height: none; } }
@media (max-width: 1250px) { .leaderboard-scroll { max-height: 520px; } .comparison-body { grid-template-columns: 1fr; } }
@media (max-width: 1100px) { .control-deck { grid-template-columns: repeat(3, 1fr); } .map-layout { grid-template-columns: 1fr; } .heatmap-panel { border-right: 0; border-bottom: 1px solid var(--color-border); } }
@media (max-width: 760px) { .control-deck, .metric-strip { grid-template-columns: 1fr; } .mode-bar, .league-header { align-items: flex-start; flex-direction: column; } .league-controls { width: 100%; flex-direction: column; } .league-controls input, .league-controls select { width: 100%; } .mode-actions { justify-items: start; } .map-layout { min-height: 0; } .heatmap-panel { padding: 12px; } .map-heading { align-items: flex-start; flex-direction: column; gap: 6px; } .inspector-score strong { font-size: 38px; } .detail-metrics { grid-template-columns: repeat(2, 1fr); } }
</style>
