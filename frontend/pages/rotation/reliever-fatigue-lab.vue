<template>
  <main class="reliever-fatigue-page">
    <ComparisonPageHeader
      eyebrow="Reliever"
      title="Bullpen Fatigue Lab"
      description="Prototype reliever readiness with yesterday, three-day load, seven-day load, leverage, and outing-length context."
      back-to="/rotation/reliever"
      back-label="Bullpen Role"
      secondary-to="/rotation"
      secondary-label="Rotation Hub"
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
    </section>

    <p v-if="pending" class="state-text">Loading bullpen fatigue lab...</p>
    <p v-else-if="error" class="state-text error">Bullpen Fatigue Lab API failed.</p>

    <template v-else-if="response">
      <SummaryCards :metrics="response.summary" />

      <section class="lab-grid">
        <div class="main-stack">
          <section class="selected-card">
            <span>Selected Reliever</span>
            <h2>{{ selectedName }}</h2>
            <p>{{ selectedMeta }}</p>
          </section>

          <DataTable title="Selected Readiness" :table="response.tables.selected_readiness" :max-rows="1" />
          <DataTable title="Readiness Breakdown" :table="response.tables.readiness_breakdown" :max-rows="12" />
          <DataTable
            title="Bullpen Readiness Board"
            :table="response.tables.readiness_board"
            :max-rows="120"
            link-column="Name"
            :link-to="relieverPersonalLink"
          />
        </div>

        <aside class="side-stack">
          <section class="method-card">
            <h2>Rule v1</h2>
            <p>Starts at 100, then subtracts short-rest and workload stress. This is intentionally transparent so we can tune weights before training a model.</p>
            <dl>
              <div>
                <dt>Yesterday Pitches</dt>
                <dd>0 to -14</dd>
              </div>
              <div>
                <dt>Last 3 Days</dt>
                <dd>0 to -12</dd>
              </div>
              <div>
                <dt>Last 7 Days</dt>
                <dd>0 to -9</dd>
              </div>
              <div>
                <dt>Back-to-Back</dt>
                <dd>0 or -6</dd>
              </div>
              <div>
                <dt>Leverage Stress</dt>
                <dd>0 to -5</dd>
              </div>
              <div>
                <dt>Out/GR</dt>
                <dd>0 to -4</dd>
              </div>
              <div>
                <dt>Rest Days</dt>
                <dd>0 or +3</dd>
              </div>
            </dl>
          </section>

          <DataTable
            title="Reliever Pool"
            :table="response.tables.relievers"
            :max-rows="36"
            link-column="Name"
            :link-to="relieverPersonalLink"
          />
        </aside>
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
const selectedPitcherId = ref<number | undefined>()

const { data, pending, error } = await useAsyncData(
  'rotation-reliever-fatigue-lab',
  () => api.rotationRelieverFatigueLab({
    year: year.value,
    team: team.value,
    minGames: minGames.value,
    playerId: selectedPitcherId.value
  }),
  { watch: [year, team, minGames, selectedPitcherId] }
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
  const rows = response.value?.tables.relievers?.rows || []
  const seen = new Set<number>()
  return rows
    .map((row) => ({
      value: Number(row.MLBAMID),
      label: `${row.Name || '-'} (${row.Team || '-'})`
    }))
    .filter((option) => {
      if (!Number.isFinite(option.value) || seen.has(option.value)) {
        return false
      }
      seen.add(option.value)
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
const selectedMeta = computed(() => {
  const player = selectedPlayer.value
  return `${player?.Team || '-'} - ${formatValue(player?.G)} G - ${formatValue(player?.SV)} SV - ${formatValue(player?.Hold)} HLD - aLI ${formatValue(player?.aLI)}`
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
</script>

<style scoped>
.reliever-fatigue-page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 104px 20px 56px;
}

.filter-panel,
.selected-card,
.method-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.filter-panel {
  display: grid;
  grid-template-columns: 130px 160px 110px minmax(260px, 1fr);
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

.lab-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.75fr);
  gap: 16px;
  margin-top: 16px;
}

.main-stack,
.side-stack {
  display: grid;
  gap: 16px;
  align-content: start;
}

.selected-card,
.method-card {
  padding: 18px;
}

.selected-card span {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.selected-card h2,
.method-card h2 {
  margin: 6px 0 0;
  color: var(--color-foreground);
}

.selected-card h2 {
  font-size: 28px;
}

p {
  color: var(--color-muted-text);
}

.method-card h2 {
  margin: 0;
}

.method-card dl {
  display: grid;
  gap: 10px;
  margin: 16px 0 0;
}

.method-card div {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 8px;
}

.method-card dt {
  color: var(--color-muted-text);
  font-weight: 800;
}

.method-card dd {
  margin: 0;
  color: var(--color-primary);
  font-family: "Fira Code", "Consolas", monospace;
}

.state-text {
  margin: 16px 0;
  color: var(--color-muted-text);
}

.state-text.error {
  color: var(--color-destructive);
}

@media (max-width: 980px) {
  .filter-panel,
  .lab-grid {
    grid-template-columns: 1fr;
  }
}
</style>
