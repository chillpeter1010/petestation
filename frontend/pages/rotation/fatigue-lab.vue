<template>
  <main class="fatigue-lab-page">
    <ComparisonPageHeader
      eyebrow="Rotation"
      title="Fatigue Lab"
      description="Prototype pregame readiness with age, rest, recent load, previous start, and season-start context."
      back-to="/rotation/starter"
      back-label="Starter Rotation"
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
      <label class="game-select">
        Game
        <select v-model.number="selectedGamePk">
          <option v-for="row in gameLog" :key="String(row.game_pk)" :value="Number(row.game_pk)">
            {{ gameOptionLabel(row) }}
          </option>
        </select>
      </label>
    </section>

    <p v-if="pending" class="state-text">Loading fatigue lab...</p>
    <p v-else-if="error" class="state-text error">Fatigue Lab API failed.</p>

    <template v-else-if="response">
      <SummaryCards :metrics="response.summary" />

      <section class="lab-grid">
        <section class="selected-card">
          <span>Selected Starter</span>
          <h2>{{ selectedName }}</h2>
          <p>{{ selectedMeta }}</p>
        </section>

        <section class="fatigue-detail-row">
          <div class="readiness-card">
            <span>Prototype Readiness</span>
            <strong>{{ formatNumber(finalRow?.['Pregame Readiness']) }}</strong>
            <p>Fatigue rate: {{ fatigueRateLabel }}</p>
          </div>
          <FatigueBarChart :rows="fatigueRows" />
          <FatiguePaTrendChart :rows="fatiguePaRows" />
        </section>

        <FatiguePitchQualityChart :rows="pitchQualityRows" />
        <p v-if="!pitchQualityRows.length" class="quality-warning">
          {{ pitchQualityWarning }}
        </p>
        <DataTable
          title="Stuff+ / Location+ by inning and pitch type"
          :table="response.tables.pitch_quality_by_inning"
          :max-rows="120"
        />

        <section class="lower-grid">
          <div class="table-stack">
          <DataTable title="Readiness Breakdown" :table="response.tables.readiness_breakdown" :max-rows="12" />
          <DataTable title="Game Readiness Trial" :table="response.tables.fatigue_games" :max-rows="40" />
          </div>

          <aside class="side-stack">
          <details class="method-card">
            <summary>Rule v1</summary>
            <p>Starts at 100, then adjusts for recovery and workload signals. This is intentionally transparent so the weights can be tuned before model training.</p>
            <section class="rule-note">
              <strong>Suppression (PA result proxy)</strong>
              <p>Starts at 68. CSW, whiffs, outs, and strikeouts add points; hits, walks, hard contact, home runs, heart-zone contact, and fastball velocity loss subtract points. It is bounded to 10-110.</p>
              <small>This is a transparent plate-appearance result score, not Stuff+, and not a measured physical-fatigue value.</small>
            </section>
            <dl>
              <div>
                <dt>Rest Days</dt>
                <dd>+3 to -14</dd>
              </div>
              <div>
                <dt>Recent 7D Load</dt>
                <dd>reference</dd>
              </div>
              <div>
                <dt>Previous Start</dt>
                <dd>0 to -7</dd>
              </div>
              <div>
                <dt>Season Start #</dt>
                <dd>0 to -6</dd>
              </div>
              <div>
                <dt>Age Recovery</dt>
                <dd>0 to -6</dd>
              </div>
            </dl>
          </details>

          <DataTable
            title="Starter Pool"
            :table="response.tables.rotation"
            :max-rows="24"
            link-column="Name"
            :link-to="starterPersonalLink"
          />
          </aside>
        </section>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import type { AnalysisResponse } from '~/types/api'

const api = useApi()

const year = ref(2026)
const team = ref('All')
const minGs = ref(3)
const minIpPerGs = ref(3)
const selectedPitcherId = ref<number | undefined>()
const selectedGamePk = ref<number | null>(null)

const { data, pending, error } = await useAsyncData(
  'rotation-fatigue-lab',
  () => api.rotationFatigueLab({
    year: year.value,
    team: team.value,
    minGs: minGs.value,
    minIpPerGs: minIpPerGs.value,
    playerId: selectedPitcherId.value,
    gamePk: selectedGamePk.value
  }),
  { watch: [year, team, minGs, minIpPerGs, selectedPitcherId, selectedGamePk] }
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
  const seen = new Set<number>()
  return rows
    .map((row) => ({ value: Number(row.MLBAMID), label: `${row.Name || '-'} (${row.Tm || '-'})` }))
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
  return `${player?.Tm || '-'} · Age ${formatNumber(player?.Age)} · ${formatNumber(player?.GS)} GS · ${formatNumber(player?.IP)} IP`
})

const gameLog = computed(() => {
  const rows = response.value?.charts.game_log
  return Array.isArray(rows) ? rows as Record<string, unknown>[] : []
})

const fatigueRows = computed(() => response.value?.tables.fatigue_by_inning?.rows || [])
const fatiguePaRows = computed(() => {
  const rows = response.value?.charts.fatigue_pa_series
  return Array.isArray(rows) ? rows as Record<string, unknown>[] : []
})
const pitchQualityRows = computed(() => {
  const rows = response.value?.charts.pitch_quality_series
  return Array.isArray(rows) ? rows as Record<string, unknown>[] : []
})
const pitchQualityWarning = computed(() => {
  const warning = response.value?.meta.warnings.find(item => item.includes('per-pitch') || item.includes('cache'))
  return warning || 'No cached per-pitch Stuff+ is available for the selected outing.'
})
const finalRow = computed(() => fatigueRows.value.at(-1))
const fatigueRateLabel = computed(() => {
  const readiness = Number(finalRow.value?.['Pregame Readiness'])
  if (!Number.isFinite(readiness)) {
    return '-'
  }
  if (readiness >= 95) {
    return '0.65 / pitch'
  }
  if (readiness >= 85) {
    return '0.75 / pitch'
  }
  return '0.85 / pitch'
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
  const selectedPk = Number(value.charts.selected_game_pk)
  if (Number.isFinite(selectedPk) && selectedGamePk.value !== selectedPk) {
    selectedGamePk.value = selectedPk
  }
}, { immediate: true })

function resetSelected() {
  selectedPitcherId.value = undefined
  selectedGamePk.value = null
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

function formatDate(value: unknown) {
  const text = String(value || '')
  return text.includes('T') ? text.split('T')[0] : text.slice(0, 10) || '-'
}

function gameOptionLabel(row: Record<string, unknown>) {
  return `${formatDate(row.game_date)} vs ${row.opponent_team || '-'} (${formatNumber(row.pitches)} pitches)`
}
</script>

<style scoped>
.fatigue-lab-page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 104px 20px 56px;
}

.filter-panel,
.selected-card,
.readiness-card,
.method-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.filter-panel {
  display: grid;
  grid-template-columns: 130px 150px 110px 130px minmax(240px, 1fr) minmax(280px, 1.1fr);
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
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.table-stack,
.side-stack {
  display: grid;
  gap: 16px;
  align-content: start;
  min-width: 0;
}

.lower-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  min-width: 0;
}

.selected-card,
.readiness-card,
.method-card {
  padding: 18px;
}

.selected-card span,
.readiness-card span {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

h2,
strong {
  color: var(--color-foreground);
}

.selected-card h2 {
  margin: 6px 0 0;
  font-size: 28px;
}

p {
  color: var(--color-muted-text);
}

.fatigue-detail-row {
  display: grid;
  grid-template-columns: 220px minmax(360px, auto) minmax(520px, 1fr);
  gap: 16px;
  align-items: stretch;
  overflow-x: auto;
  padding-bottom: 4px;
}

.readiness-card strong {
  display: block;
  margin-top: 10px;
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 48px;
  line-height: 1;
}

.method-card {
  padding: 0;
  overflow: hidden;
}

.method-card summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 54px;
  padding: 0 18px;
  color: var(--color-foreground);
  cursor: pointer;
  font-size: 18px;
  font-weight: 900;
  list-style: none;
}

.method-card summary::-webkit-details-marker {
  display: none;
}

.method-card summary::after {
  content: "+";
  color: var(--color-primary);
  font-size: 22px;
}

.method-card[open] summary::after {
  content: "-";
}

.method-card p {
  margin: 0;
  padding: 0 18px 14px;
}

.rule-note {
  margin: 0 18px 16px;
  border: 1px solid color-mix(in srgb, var(--color-primary) 35%, var(--color-border));
  border-radius: var(--radius-sm);
  padding: 14px;
  background: color-mix(in srgb, var(--color-primary) 7%, transparent);
}

.rule-note strong {
  display: block;
  margin-bottom: 7px;
  color: var(--color-primary);
}

.rule-note p {
  padding: 0;
  color: var(--color-foreground);
  line-height: 1.55;
}

.rule-note small,
.quality-warning {
  color: var(--color-muted-text);
  line-height: 1.5;
}

.quality-warning {
  margin: -8px 0 0;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
}

.method-card dl {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0 18px 18px;
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
  color: #d04a3a;
}

@media (max-width: 1040px) {
  .filter-panel,
  .lab-grid,
  .fatigue-detail-row,
  .lower-grid {
    grid-template-columns: 1fr;
  }
}
</style>
