<template>
  <main class="reliever-page">
    <ComparisonPageHeader
      eyebrow="Reliever"
      title="Bullpen Role"
      description="Reliever role table, save/hold context, inherited runners, leverage usage, and workload profile."
      back-to="/rotation"
      back-label="Rotation Hub"
      secondary-to="/rotation/reliever-fatigue-lab"
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
        Min G
        <input v-model.number="minGames" type="number" min="0" @change="resetSelected">
      </label>
      <label class="reliever-select">
        Reliever
        <select v-model.number="selectedPitcherId">
          <option v-for="pitcher in relieverOptions" :key="pitcher.value" :value="pitcher.value">
            {{ pitcher.label }}
          </option>
        </select>
      </label>
      <label>
        Availability Date
        <input v-model="availabilityDate" type="date">
      </label>
    </section>

    <p v-if="pending" class="state-text">Loading bullpen role...</p>
    <p v-else-if="error" class="state-text error">Bullpen role API failed.</p>

    <template v-else-if="response">
      <SummaryCards :metrics="response.summary" />

      <section class="detail-grid">
        <DataTable
          title="Bullpen Role"
          :table="response.tables.bullpen"
          :max-rows="120"
          link-column="Name"
          :link-to="relieverPersonalLink"
        />
        <aside class="side-stack">
          <section class="selected-card">
            <span>Selected Reliever</span>
            <h2>{{ selectedName }}</h2>
            <p>{{ cleanSelectedMeta }}</p>
          </section>
          <DataTable title="Role Usage" :table="response.tables.role_usage_horizontal" :max-rows="1" />
        </aside>
      </section>

      <section class="availability-panel">
        <header class="table-header">
          <div>
            <h2>{{ cleanAvailabilityTitle }}</h2>
            <p>Last three days and selected-date workload from the 2026 bullpen availability slice.</p>
          </div>
          <span>{{ availabilityRows.length }} relievers</span>
        </header>
        <div v-if="availabilityRows.length" class="availability-chart">
          <div class="availability-legend">
            <span><i class="legend-last-three" />Last three days</span>
            <span><i class="legend-yesterday" />Availability day</span>
            <span><i class="legend-capacity" />45-pitch workload line</span>
          </div>
          <div class="availability-plot">
            <article v-for="row in availabilityRows" :key="`bar-${String(row.MLBAMID)}`" class="availability-slot">
              <span class="hand-label">{{ String(row.Throws || 'R').toUpperCase() === 'L' ? 'LEFTY' : 'RIGHTY' }}</span>
              <strong class="pitch-total">{{ formatValue(row['Pitches Last 3']) }}</strong>
              <div class="availability-bar">
                <span class="capacity" />
                <span class="last-three" :style="{ height: `${availabilityWidth(row['Pitches Last 3'])}%` }" />
                <span class="yesterday" :style="{ height: `${availabilityWidth(row['Pitches Yesterday'])}%` }" />
                <b v-if="Number(row['Pitches Yesterday']) > 0" :style="{ bottom: `${availabilityWidth(row['Pitches Yesterday'])}%` }">
                  {{ formatValue(row['Pitches Yesterday']) }}
                </b>
              </div>
              <p>{{ splitName(String(row.Name || '-')).first }}<br>{{ splitName(String(row.Name || '-')).last }}</p>
            </article>
          </div>
        </div>

        <div v-if="availabilityRows.length" class="availability-grid">
          <article v-for="row in availabilityRows" :key="String(row.MLBAMID)" class="availability-card">
            <div class="availability-card-head">
              <div>
                <h3>{{ row.Name }}</h3>
                <p>{{ row.Team }} · {{ row.Throws || '-' }}</p>
              </div>
              <strong>{{ formatValue(row.Availability) }}</strong>
            </div>
            <div class="availability-meter" aria-hidden="true">
              <span class="last-three" :style="{ width: `${availabilityWidth(row['Pitches Last 3'])}%` }" />
              <span class="yesterday" :style="{ width: `${availabilityWidth(row['Pitches Yesterday'])}%` }" />
            </div>
            <dl>
              <div>
                <dt>Last 3</dt>
                <dd>{{ formatValue(row['Pitches Last 3']) }}</dd>
              </div>
              <div>
                <dt>Selected Day</dt>
                <dd>{{ formatValue(row['Pitches Yesterday']) }}</dd>
              </div>
              <div>
                <dt>Last Game</dt>
                <dd>{{ row['Last Game'] || '-' }}</dd>
              </div>
            </dl>
          </article>
        </div>
        <p v-else class="empty-availability">No availability rows for the selected team/date.</p>
      </section>

      <section class="derived-panel">
        <header class="section-header">
          <div>
            <h2>Bullpen Role Views</h2>
            <p>Tactical tags, role classification, usage timing, and role stability from the legacy bullpen module.</p>
          </div>
        </header>
        <div class="tab-row" role="tablist" aria-label="Bullpen role views">
          <button
            v-for="tab in derivedTabs"
            :key="tab.key"
            type="button"
            :class="{ active: activeDerivedTab === tab.key }"
            @click="activeDerivedTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>
        <div class="role-snapshot">
          <article v-for="card in roleSnapshotCards" :key="card.label">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
          </article>
        </div>
        <DataTable
          :title="activeDerivedTitle"
          :table="activeDerivedTable"
          :max-rows="160"
          link-column="Name"
          :link-to="relieverPersonalLink"
        />
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import type { AnalysisResponse } from '~/types/api'

const api = useApi()

const year = ref(2025)
const team = ref('All')
const minGames = ref(5)
const availabilityDate = ref('')
const selectedPitcherId = ref<number | undefined>()
const activeDerivedTab = ref('tactical')
const derivedTabs = [
  { key: 'tactical', label: 'Tactical Tags' },
  { key: 'role_board', label: 'Role Board' },
  { key: 'usage_timing', label: 'Usage Timing' },
  { key: 'stability', label: 'Stability' }
]

const { data, pending, error } = await useAsyncData(
  'rotation-reliever',
  () => api.rotationReliever({
    year: year.value,
    team: team.value,
    minGames: minGames.value,
    playerId: selectedPitcherId.value,
    availabilityDate: availabilityDate.value || undefined
  }),
  { watch: [year, team, minGames, selectedPitcherId, availabilityDate] }
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
const relieverOptions = computed(() => {
  const rows = response.value?.tables.bullpen?.rows || []
  return rows
    .map((row) => ({
      value: Number(row.MLBAMID),
      label: `${row.Name || '-'} (${row.Team || '-'})`
    }))
    .filter((option) => Number.isFinite(option.value))
})
const selectedPlayer = computed<Record<string, unknown> | null>(() => {
  const selected = response.value?.charts.selected_player
  return selected && typeof selected === 'object' && !Array.isArray(selected)
    ? selected as Record<string, unknown>
    : null
})
const selectedName = computed(() => String(selectedPlayer.value?.Name || '-'))
const selectedMeta = computed(() => {
  const player = selectedPlayer.value
  if (!player) {
    return '-'
  }
  return `${player.Team || '-'} · ${formatValue(player.G)} G · ${formatValue(player.SV)} SV · ${formatValue(player.Hold)} HLD · aLI ${formatValue(player.aLI)}`
})

const activeDerivedTable = computed(() => response.value?.tables[activeDerivedTab.value])
const activeDerivedTitle = computed(() => {
  return derivedTabs.find((tab) => tab.key === activeDerivedTab.value)?.label || 'Role View'
})
const availabilityRows = computed(() => response.value?.tables.availability?.rows || [])
const availabilityTitle = computed(() => {
  const availabilityYear = response.value?.charts.availability_year || 2026
  const availabilityTeam = response.value?.charts.availability_team || team.value
  const date = response.value?.charts.availability_date || 'latest'
  return `${availabilityYear} ${availabilityTeam} Bullpen Availability · ${date}`
})
const cleanSelectedMeta = computed(() => {
  const player = selectedPlayer.value
  if (!player) {
    return '-'
  }
  return `${player.Team || '-'} · ${formatValue(player.G)} G · ${formatValue(player.SV)} SV · ${formatValue(player.Hold)} HLD · aLI ${formatValue(player.aLI)}`
})
const cleanAvailabilityTitle = computed(() => {
  const availabilityYear = response.value?.charts.availability_year || 2026
  const availabilityTeam = response.value?.charts.availability_team || team.value || 'Team'
  const date = response.value?.charts.availability_date || 'latest'
  return `${availabilityYear} ${availabilityTeam} Bullpen Availability · ${date}`
})

const roleSnapshotCards = computed(() => {
  const roleRows = response.value?.tables.role_board?.rows || []
  const tacticalRows = response.value?.tables.tactical?.rows || []
  return [
    { label: 'Closers', value: countRows(roleRows, 'PrimaryRole', 'Closer') },
    { label: 'Setup', value: countRows(roleRows, 'PrimaryRole', 'Setup') },
    { label: 'Fireman Tags', value: countIncludes(tacticalRows, 'TacticalTags', 'Fireman') },
    { label: 'Durable Tags', value: countIncludes(tacticalRows, 'TacticalTags', 'Durable') }
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
  if (availabilityDate.value || !value) {
    return
  }
  const date = String(value.charts.availability_date || '')
  if (/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    availabilityDate.value = date
  }
}, { immediate: true })

function resetSelected() {
  selectedPitcherId.value = undefined
}

function relieverPersonalLink(row: Record<string, unknown>) {
  const pitcherId = Number(row.MLBAMID)
  if (!Number.isFinite(pitcherId)) {
    return undefined
  }
  return {
    path: '/pitcher-personal',
    query: {
      year: year.value,
      role: 'RP',
      team: String(row.Team || ''),
      pitcher_id: pitcherId
    }
  }
}

function formatValue(value: unknown) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) {
    return '-'
  }
  return Number.isInteger(numberValue) ? String(numberValue) : numberValue.toFixed(2)
}

function availabilityWidth(value: unknown) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) {
    return 0
  }
  return Math.max(0, Math.min(100, (numberValue / 45) * 100))
}

function splitName(value: string) {
  const parts = value.trim().split(/\s+/)
  if (parts.length <= 1) {
    return { first: value, last: '' }
  }
  return { first: parts[0], last: parts.slice(1).join(' ') }
}

function countRows(rows: Record<string, unknown>[], key: string, value: string) {
  return rows.filter((row) => String(row[key] || '') === value).length
}

function countIncludes(rows: Record<string, unknown>[], key: string, value: string) {
  return rows.filter((row) => String(row[key] || '').includes(value)).length
}
</script>

<style scoped>
.reliever-page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 104px 20px 56px;
}

.filter-panel,
.selected-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.filter-panel {
  display: grid;
  grid-template-columns: 110px 140px 90px minmax(230px, 1fr) 170px;
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
  border: 1px solid var(--color-control-border, var(--color-border-strong));
  border-radius: var(--radius-sm);
  padding: 0 12px;
  color: var(--color-control-text, var(--color-text));
  background: var(--color-control-bg, var(--color-surface));
  font: inherit;
  font-size: 14px;
  font-weight: 800;
  text-transform: none;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(380px, 0.85fr);
  gap: 16px;
  margin-top: 16px;
}

.availability-panel {
  margin-top: 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.availability-panel .table-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}

.availability-panel h2,
.availability-panel h3,
.availability-panel p {
  margin: 0;
}

.availability-panel h2 {
  color: var(--color-foreground);
  font-size: 18px;
}

.availability-panel p,
.availability-panel span,
.availability-card dt {
  color: var(--color-muted-text);
}

.availability-chart {
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
  background: color-mix(in srgb, var(--color-surface) 94%, #000);
}

.availability-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 800;
}

.availability-legend span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.availability-legend i {
  display: inline-block;
  width: 18px;
  height: 10px;
  border-radius: 999px;
}

.legend-last-three {
  background: #3d862e;
}

.legend-yesterday {
  border: 1px solid #ebe5d6;
  background: #f4f0e8;
}

.legend-capacity {
  border: 1px solid #7f8794;
  background: #9b9e9f;
}

.availability-plot {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(82px, 1fr);
  width: 100%;
  min-height: 360px;
  overflow-x: auto;
  padding: 8px 4px 2px;
}

.availability-slot {
  display: grid;
  grid-template-rows: 18px 20px 210px auto;
  justify-items: center;
  gap: 6px;
  min-width: 82px;
}

.hand-label {
  color: var(--color-primary);
  font-size: 10px;
  font-weight: 950;
  letter-spacing: 0.02em;
}

.pitch-total {
  color: var(--color-foreground);
  font-size: 15px;
}

.availability-bar {
  position: relative;
  display: flex;
  align-items: end;
  justify-content: center;
  width: 34px;
  height: 210px;
}

.availability-bar span {
  position: absolute;
  bottom: 0;
  width: 28px;
  border-radius: 6px 6px 0 0;
}

.availability-bar .capacity {
  height: 100%;
  border: 1px solid #aeb4b8;
  background: #9b9e9f;
  opacity: 0.95;
}

.availability-bar .last-three {
  background: #3d862e;
  box-shadow: 0 0 0 1px rgba(206, 220, 206, 0.55);
}

.availability-bar .yesterday {
  width: 18px;
  background: #f4f0e8;
  box-shadow: 0 0 0 1px #ffffff;
}

.availability-bar b {
  position: absolute;
  left: 50%;
  z-index: 2;
  min-width: 24px;
  transform: translate(-50%, 50%);
  color: #9c2825;
  font-size: 13px;
  font-weight: 950;
  text-align: center;
}

.availability-slot p {
  max-width: 78px;
  color: var(--color-foreground);
  font-size: 11px;
  font-weight: 850;
  line-height: 1.3;
  text-align: center;
}

.availability-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  padding: 16px;
}

.availability-card {
  display: grid;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 14px;
  background: color-mix(in srgb, var(--color-surface) 86%, var(--color-muted));
}

.availability-card-head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 12px;
}

.availability-card h3 {
  color: var(--color-foreground);
  font-size: 15px;
}

.availability-card strong {
  color: var(--color-primary);
  font-size: 18px;
}

.availability-meter {
  position: relative;
  height: 16px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-muted);
}

.availability-meter span {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
}

.availability-meter .last-three {
  background: #3d862e;
}

.availability-meter .yesterday {
  background: #f4f0e8;
  mix-blend-mode: screen;
}

.availability-card dl {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.availability-card dt {
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.availability-card dd {
  margin: 2px 0 0;
  color: var(--color-foreground);
  font-weight: 850;
}

.empty-availability {
  padding: 16px;
}

.derived-panel {
  display: grid;
  gap: 14px;
  margin-top: 18px;
}

.section-header {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
}

.section-header h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 22px;
}

.section-header p {
  margin: 4px 0 0;
  color: var(--color-muted-text);
}

.tab-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tab-row button {
  min-height: 38px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 0 14px;
  color: var(--color-foreground);
  background: var(--color-surface);
  font: inherit;
  font-size: 13px;
  font-weight: 850;
  cursor: pointer;
}

.tab-row button.active {
  border-color: var(--color-primary);
  color: var(--color-on-primary);
  background: var(--color-primary);
}

.role-snapshot {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 10px;
}

.role-snapshot article {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 12px;
  background: var(--color-surface);
}

.role-snapshot span {
  display: block;
  color: var(--color-muted-text);
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
}

.role-snapshot strong {
  display: block;
  margin-top: 4px;
  color: var(--color-foreground);
  font-size: 24px;
}

.side-stack {
  display: grid;
  gap: 16px;
  align-content: start;
}

.role-usage-vertical {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.role-usage-vertical header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}

.role-usage-vertical h2,
.role-usage-vertical h3 {
  margin: 0;
  color: var(--color-foreground);
}

.role-usage-vertical h2 {
  font-size: 15px;
}

.role-usage-vertical header span {
  color: var(--color-muted-text);
  font-size: 13px;
}

.role-usage-groups {
  display: grid;
  gap: 10px;
  padding: 12px;
}

.role-usage-groups article {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 12px;
  background: color-mix(in srgb, var(--color-surface) 86%, var(--color-muted));
}

.role-usage-groups h3 {
  font-size: 13px;
}

.role-usage-groups dl {
  display: grid;
  gap: 8px;
  margin: 10px 0 0;
}

.role-usage-groups dl div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.role-usage-groups dt {
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 800;
}

.role-usage-groups dd {
  margin: 0;
  color: var(--color-foreground);
  font-size: 14px;
  font-weight: 900;
}

.selected-card {
  padding: 18px;
}

.selected-card span {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.selected-card h2 {
  margin: 6px 0 0;
  color: var(--color-foreground);
  font-size: 28px;
}

.selected-card p,
.state-text {
  color: var(--color-muted-text);
}

.state-text.error {
  color: var(--color-destructive);
}

@media (max-width: 980px) {
  .filter-panel,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
