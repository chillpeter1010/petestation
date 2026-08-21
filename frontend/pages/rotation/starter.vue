<template>
  <main class="starter-page">
    <ComparisonPageHeader
      eyebrow="Rotation"
      title="Starter Rotation"
      description="Starter table, workload profile, and per-game WPA trend migrated from legacy pitcher rotation."
      back-to="/rotation"
      back-label="Rotation Hub"
      secondary-to="/rotation/fatigue-lab"
      secondary-label="Fatigue Lab"
    />

    <section class="filter-panel">
      <label>
        Year
        <select v-model.number="year" @change="resetSelected">
          <option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <label>
        Team
        <select v-model="team" @change="resetSelected">
          <option value="All">All</option>
          <option v-for="option in teamOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <label>
        Min GS
        <input v-model.number="minGs" type="number" min="0" @change="resetSelected">
      </label>
      <label>
        Min IP/GS
        <input v-model.number="minIpPerGs" type="number" min="0" step="0.1" @change="resetSelected">
      </label>
      <label class="starter-select">
        Starter
        <select v-model.number="selectedPitcherId">
          <option v-for="pitcher in starterOptions" :key="pitcher.value" :value="pitcher.value">
            {{ pitcher.label }}
          </option>
        </select>
      </label>
    </section>

    <p v-if="pending" class="state-text">Loading starter rotation...</p>
    <p v-else-if="error" class="state-text error">Starter rotation API failed.</p>

    <template v-else-if="response">
      <SummaryCards :metrics="response.summary" />

      <section class="detail-grid">
        <div class="main-stack">
          <DataTable
            title="Starter Rotation"
            :table="response.tables.rotation"
            :max-rows="80"
            link-column="Name"
            :link-to="starterPersonalLink"
          />
          <section class="fatigue-game-panel">
            <div class="fatigue-control">
              <label>
                Rotation / Fatigue Game
                <select v-model.number="selectedFatigueGamePk">
                  <option v-for="row in gameLog" :key="String(row.game_pk)" :value="Number(row.game_pk)">
                    {{ gameOptionLabel(row) }}
                  </option>
                </select>
              </label>
            </div>
            <div class="fatigue-detail-row">
              <div class="fatigue-metric-grid">
                <article v-for="metric in fatigueMetrics" :key="metric.label">
                  <span>{{ metric.label }}</span>
                  <strong>{{ metric.value }}</strong>
                </article>
              </div>
              <FatigueBarChart :rows="fatigueRows" />
            </div>
          </section>
          <DataTable title="Game Fatigue Score" :table="fatigueGameTable" :max-rows="40" />
        </div>

        <aside class="side-stack">
          <section class="selected-card">
            <span>Selected Starter</span>
            <h2>{{ selectedName }}</h2>
            <p>{{ selectedTeamRole }}</p>
          </section>
          <details class="collapsible-table" open>
            <summary>Workload Profile</summary>
            <DataTable title="Workload Profile" :table="response.tables.workload" :max-rows="20" />
          </details>
          <section class="chart-card wpa-card">
            <header>
              <h2>Game WPA Trend</h2>
              <span>{{ gameLog.length.toLocaleString() }} games</span>
            </header>
            <svg v-if="gameLog.length" viewBox="0 0 720 260" role="img" aria-label="Starter game WPA trend">
              <g class="y-axis">
                <line x1="54" x2="54" y1="36" y2="226" class="axis" />
                <g v-for="tick in yTicks" :key="tick.label">
                  <line x1="54" x2="690" :y1="tick.y" :y2="tick.y" class="grid-line" />
                  <text x="44" :y="tick.y + 4" text-anchor="end">{{ tick.label }}</text>
                </g>
              </g>
              <line x1="54" x2="690" :y1="zeroY" :y2="zeroY" class="axis zero-axis" />
              <polyline :points="cumLinePoints" class="cum-line" />
              <g v-for="(point, index) in gamePoints" :key="index">
                <line
                  :x1="point.x"
                  :x2="point.x"
                  :y1="zeroY"
                  :y2="point.gameY"
                  :class="point.gameWpa >= 0 ? 'bar positive' : 'bar negative'"
                />
                <circle
                  :cx="point.x"
                  :cy="point.cumY"
                  r="4"
                  class="dot"
                  @mouseenter="hoveredGame = point"
                  @mouseleave="hoveredGame = null"
                />
                <rect
                  :x="point.x - 7"
                  y="32"
                  width="14"
                  height="202"
                  class="hover-zone"
                  @mouseenter="hoveredGame = point"
                  @mouseleave="hoveredGame = null"
                />
              </g>
            </svg>
            <div v-if="hoveredGame" class="wpa-tooltip" :style="wpaTooltipStyle">
              <strong>{{ formatDate(hoveredGame.date) }}</strong>
              <span>{{ hoveredGame.pitches.toLocaleString() }} pitches</span>
              <span>Game WPA {{ formatSigned(hoveredGame.gameWpa) }}</span>
              <span>Cum WPA {{ formatSigned(hoveredGame.cumWpa) }}</span>
            </div>
            <p v-if="!gameLog.length" class="empty-chart">No per-game WPA rows for the selected starter.</p>
          </section>
          <DataTable title="Pitch Profile" :table="response.tables.pitch_profile" :max-rows="12" />
          <DataTable title="Game Log" :table="response.tables.game_log" :max-rows="12" />
        </aside>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import type { AnalysisResponse, TablePayload } from '~/types/api'

const api = useApi()

const year = ref(2025)
const team = ref('All')
const minGs = ref(3)
const minIpPerGs = ref(3)
const selectedPitcherId = ref<number | undefined>()
const selectedFatigueGamePk = ref<number | null>(null)
const hoveredGame = ref<GamePoint | null>(null)

interface GamePoint {
  x: number
  gameWpa: number
  cumWpa: number
  gameY: number
  cumY: number
  date: string
  pitches: number
}

const { data, pending, error } = await useAsyncData(
  'rotation-starter',
  () => api.rotationStarter({
    year: year.value,
    team: team.value,
    minGs: minGs.value,
    minIpPerGs: minIpPerGs.value,
    playerId: selectedPitcherId.value,
    fatigueGamePk: selectedFatigueGamePk.value
  }),
  { watch: [year, team, minGs, minIpPerGs, selectedPitcherId, selectedFatigueGamePk] }
)

const response = computed<AnalysisResponse | null>(() => data.value || null)

const yearOptions = computed(() => {
  const years = response.value?.charts.available_years
  return Array.isArray(years) && years.length ? years.map(Number) : [2025]
})

const teamOptions = computed(() => {
  const teams = response.value?.charts.teams
  return Array.isArray(teams) ? teams.map(String) : []
})

const starterOptions = computed(() => {
  const rows = response.value?.tables.rotation?.rows || []
  const seen = new Set<string>()
  return rows
    .map((row) => ({
      value: Number(row.MLBAMID),
      label: `${row.Name || '-'} (${row.Tm || '-'})`
    }))
    .filter((option) => {
      if (!Number.isFinite(option.value)) {
        return false
      }
      const key = `${option.value}:${option.label}`
      if (seen.has(key)) {
        return false
      }
      seen.add(key)
      return true
    })
})

const selectedPlayer = computed<Record<string, unknown> | null>(() => {
  const selected = response.value?.charts.selected_player
  return selected && typeof selected === 'object' && !Array.isArray(selected)
    ? selected as Record<string, unknown>
    : null
})

const selectedName = computed(() => String(selectedPlayer.value?.Name || '-'))
const selectedTeamRole = computed(() => `${selectedPlayer.value?.Tm || '-'} · ${formatNumber(selectedPlayer.value?.GS)} GS · ${formatNumber(selectedPlayer.value?.IP)} IP`)

const gameLog = computed(() => {
  const rows = response.value?.charts.game_log
  return Array.isArray(rows) ? rows as Record<string, unknown>[] : []
})
const fatigueRows = computed(() => response.value?.tables.fatigue_by_inning?.rows || [])
const selectedFatigueGame = computed(() => {
  const selectedPk = Number(response.value?.charts.selected_fatigue_game_pk || selectedFatigueGamePk.value)
  return gameLog.value.find((row) => Number(row.game_pk) === selectedPk) || gameLog.value.at(-1) || null
})
const fatigueMetrics = computed(() => {
  const rows = fatigueRows.value
  const finalRow = rows.at(-1)
  return [
    { label: 'Pregame Readiness', value: formatNumber(finalRow?.['Pregame Readiness'] ?? 100) },
    { label: 'Final Fatigue Score', value: formatNumber(finalRow?.['Fatigue Score']) },
    { label: 'Cumulative Pitches', value: formatNumber(finalRow?.['Cumulative Pitches'] ?? selectedFatigueGame.value?.pitches) },
    { label: 'Innings Tracked', value: rows.length.toLocaleString() }
  ]
})

watch(response, (value) => {
  if (selectedPitcherId.value || !value) {
    return
  }
  const selected = value.charts.selected_player
  if (selected && typeof selected === 'object' && !Array.isArray(selected)) {
    const id = Number((selected as Record<string, unknown>).MLBAMID)
    if (Number.isFinite(id)) {
      selectedPitcherId.value = id
    }
  }
}, { immediate: true })

watch(response, (value) => {
  if (!value) {
    return
  }
  const selectedPk = Number(value.charts.selected_fatigue_game_pk)
  if (Number.isFinite(selectedPk) && selectedFatigueGamePk.value !== selectedPk) {
    selectedFatigueGamePk.value = selectedPk
  }
}, { immediate: true })

function resetSelected() {
  selectedPitcherId.value = undefined
  selectedFatigueGamePk.value = null
}

function starterPersonalLink(row: Record<string, unknown>) {
  const pitcherId = Number(row.MLBAMID)
  if (!Number.isFinite(pitcherId)) {
    return undefined
  }
  return {
    path: '/pitcher-personal',
    query: {
      year: year.value,
      role: 'SP',
      team: String(row.Tm || ''),
      pitcher_id: pitcherId
    }
  }
}

function formatNumber(value: unknown) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) {
    return '-'
  }
  return Number.isInteger(numberValue) ? String(numberValue) : numberValue.toFixed(1)
}

const chartValues = computed(() => {
  const values = gameLog.value.flatMap((row) => [Number(row.game_wpa), Number(row.cum_wpa)])
    .filter((value) => Number.isFinite(value))
  if (!values.length) {
    return { min: -1, max: 1 }
  }
  const maxAbs = Math.max(...values.map((value) => Math.abs(value)), 0.25)
  return { min: -maxAbs, max: maxAbs }
})

const zeroY = computed(() => yScale(0))

const gamePoints = computed(() => {
  const rows = gameLog.value
  const count = Math.max(rows.length - 1, 1)
  return rows.map((row, index) => {
    const x = 54 + (636 * index) / count
    const gameWpa = Number(row.game_wpa || 0)
    const cumWpa = Number(row.cum_wpa || 0)
    return {
      x,
      gameWpa,
      gameY: yScale(gameWpa),
      cumWpa,
      cumY: yScale(cumWpa),
      date: String(row.game_date || ''),
      pitches: Number(row.pitches || 0)
    }
  })
})

const cumLinePoints = computed(() => gamePoints.value.map((point) => `${point.x},${point.cumY}`).join(' '))
const yTicks = computed(() => {
  const { min, max } = chartValues.value
  const ticks = [-1, -0.5, 0, 0.5, 1].map((ratio) => {
    const value = min + ((ratio + 1) / 2) * (max - min)
    return {
      value,
      label: value.toFixed(2),
      y: yScale(value)
    }
  })
  return ticks
})

const wpaTooltipStyle = computed(() => {
  if (!hoveredGame.value) {
    return {}
  }
  return {
    left: `${(hoveredGame.value.x / 720) * 100}%`,
    top: `${Math.max(12, hoveredGame.value.cumY - 16)}px`
  }
})

const fatigueGameTable = computed<TablePayload>(() => {
  const rows = gameLog.value.map((row) => {
    const pitches = Number(row.pitches || 0)
    const fatigueScore = Math.max(20, Math.min(100, 100 - pitches * 0.75))
    return {
      Date: formatDate(row.game_date),
      Opponent: row.opponent_team || '-',
      Pitches: pitches,
      'Rest Days': formatRest(row.rest_days),
      'Game WPA': Number(row.game_wpa || 0),
      'Fatigue Score': Number(fatigueScore.toFixed(1))
    }
  })
  return {
    columns: [
      { key: 'Date', label: 'Date' },
      { key: 'Opponent', label: 'Opp' },
      { key: 'Pitches', label: 'Pitches' },
      { key: 'Rest Days', label: 'Rest' },
      { key: 'Game WPA', label: 'WPA' },
      { key: 'Fatigue Score', label: 'Fatigue' }
    ],
    rows: rows.slice().reverse()
  }
})

function yScale(value: number) {
  const { min, max } = chartValues.value
  const ratio = (value - min) / (max - min || 1)
  return 226 - ratio * 190
}

function formatDate(value: unknown) {
  const text = String(value || '')
  return text.includes('T') ? text.split('T')[0] : text.slice(0, 10) || '-'
}

function formatSigned(value: number) {
  if (!Number.isFinite(value)) {
    return '-'
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(3)}`
}

function formatRest(value: unknown) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) {
    return '-'
  }
  return numberValue.toFixed(0)
}

function gameOptionLabel(row: Record<string, unknown>) {
  return `${formatDate(row.game_date)} vs ${row.opponent_team || '-'} (${formatNumber(row.pitches)} pitches)`
}
</script>

<style scoped>
.starter-page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 104px 20px 56px;
}

.filter-panel,
.selected-card,
.chart-card,
.fatigue-game-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.selected-card span {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

h2 {
  margin: 0;
  color: var(--color-foreground);
}

p {
  color: var(--color-muted-text);
}

.filter-panel {
  display: grid;
  grid-template-columns: 150px 170px 120px 140px minmax(260px, 1fr);
  gap: 14px;
  margin: 18px 0;
  padding: 16px;
}

label {
  display: grid;
  gap: 8px;
  color: var(--color-foreground);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

select,
input {
  min-width: 0;
  height: 44px;
  border: 1px solid var(--color-control-border);
  border-radius: var(--radius-sm);
  padding: 0 12px;
  color: var(--color-control-text);
  background: var(--color-control-bg);
  font: inherit;
  font-size: 14px;
  font-weight: 800;
  text-transform: none;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(420px, 0.75fr);
  gap: 16px;
  margin-top: 16px;
}

.side-stack {
  display: grid;
  gap: 16px;
  align-content: start;
}

.main-stack {
  display: grid;
  gap: 16px;
  align-content: start;
}

.fatigue-game-panel {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.fatigue-control {
  max-width: 560px;
}

.fatigue-detail-row {
  display: grid;
  grid-template-columns: minmax(220px, 0.9fr) minmax(320px, 1.35fr);
  gap: 16px;
  align-items: stretch;
}

.fatigue-metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.fatigue-metric-grid article {
  min-height: 84px;
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-muted);
}

.fatigue-metric-grid span {
  display: block;
  color: var(--color-muted-text);
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
}

.fatigue-metric-grid strong {
  display: block;
  margin-top: 8px;
  color: var(--color-foreground);
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 26px;
}

.selected-card {
  padding: 18px;
}

.selected-card h2 {
  margin-top: 6px;
  font-size: 28px;
}

.selected-card p {
  margin: 8px 0 0;
}

.chart-card header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}

.chart-card header h2 {
  font-size: 15px;
}

.chart-card header span,
.empty-chart {
  color: var(--color-muted-text);
  font-size: 13px;
}

svg {
  display: block;
  width: 100%;
  min-height: 260px;
}

.wpa-card {
  position: relative;
}

.axis {
  stroke: var(--color-muted-text);
  stroke-width: 1;
  opacity: 0.55;
}

.zero-axis {
  opacity: 0.78;
}

.grid-line {
  stroke: var(--color-border);
  stroke-width: 1;
  opacity: 0.34;
}

.y-axis text {
  fill: var(--color-muted-text);
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 10px;
  font-weight: 700;
}

.bar {
  stroke-width: 4;
  opacity: 0.55;
}

.bar.positive {
  stroke: #f59f31;
}

.bar.negative {
  stroke: #5ea0c8;
}

.cum-line {
  fill: none;
  stroke: var(--color-primary);
  stroke-width: 3;
}

.dot {
  fill: var(--color-surface);
  stroke: var(--color-primary);
  stroke-width: 2;
}

.hover-zone {
  fill: transparent;
  cursor: crosshair;
}

.wpa-tooltip {
  position: absolute;
  z-index: 4;
  display: grid;
  gap: 4px;
  min-width: 142px;
  padding: 9px 11px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-foreground);
  background: color-mix(in srgb, var(--color-surface) 94%, #000 6%);
  box-shadow: var(--shadow-sm);
  font-size: 12px;
  pointer-events: none;
  transform: translate(-50%, -100%);
}

.wpa-tooltip strong {
  color: var(--color-primary);
  font-size: 12px;
}

.wpa-tooltip span {
  color: var(--color-text);
}

.empty-chart {
  margin: 0;
  padding: 18px 14px;
}

.state-text {
  margin: 16px 0;
  color: var(--color-muted-text);
}

.state-text.error {
  color: #d04a3a;
}

@media (max-width: 980px) {
  .filter-panel,
  .detail-grid,
  .fatigue-detail-row {
    grid-template-columns: 1fr;
  }
}
</style>
