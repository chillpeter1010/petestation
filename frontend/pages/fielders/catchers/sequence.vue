<template>
  <main class="catcher-sequence-page">
    <section class="page-hero">
      <div>
        <span class="eyebrow">Catcher Sequence</span>
        <h1>{{ selectedCatcherLabel || 'Catcher Pairing' }}</h1>
        <p>Pitch mix by count, filtered by catcher and paired pitcher.</p>
      </div>
      <NuxtLink class="hub-link" to="/fielders/catchers">Catcher Station</NuxtLink>
    </section>

    <section class="filter-panel">
      <label>
        Year
        <select v-model.number="year">
          <option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <label>
        Catcher
        <select v-model="catcherId">
          <option v-for="option in catcherOptions" :key="option.value" :value="String(option.value)">
            {{ option.label }}
          </option>
        </select>
      </label>
      <label>
        Paired Pitcher
        <select v-model="pairedPitcherId">
          <option v-for="option in pairedPitcherOptions" :key="option.value" :value="String(option.value)">
            {{ option.label }}
          </option>
        </select>
      </label>
      <label>
        Stand
        <CheckboxDropdown v-model="stand" :options="standOptions" />
      </label>
      <label>
        Count
        <CheckboxDropdown v-model="count" :options="countOptions" />
      </label>
      <label>
        Pitch
        <CheckboxDropdown v-model="pitch" :options="pitchOptions" />
      </label>
      <label>
        Pitch Result
        <CheckboxDropdown v-model="pitchResult" :options="pitchResultOptions" />
      </label>
      <label>
        Start Date
        <input v-model="startDate" type="date">
      </label>
      <label>
        End Date
        <input v-model="endDate" type="date">
      </label>
      <button type="button" @click="clearDates">Clear Dates</button>
      <span class="filter-total">{{ loading ? 'Updating' : `${filteredTotal} filtered pitches` }}</span>
    </section>

    <section v-if="errorMessage" class="state-panel">{{ errorMessage }}</section>
    <section v-else-if="!catcherId" class="state-panel">No catcher options for the selected season.</section>

    <template v-else>
      <SummaryCards :metrics="snapshotMetrics" />

      <section class="dashboard-grid">
        <DataTable title="Paired Pitchers" :table="sequence?.tables.paired_pitchers" />
        <section class="panel-section">
          <header>
            <h2>Pitcher Mix</h2>
            <span>{{ pairedPitcherMix.length }} rows</span>
          </header>
          <div class="mix-list">
            <div v-for="row in pairedPitcherMix" :key="String(row['Pitcher ID'] || row.Pitcher)" class="mix-row">
              <span>{{ row.Pitcher }}</span>
              <strong>{{ formatNumber(row.usage_pct, 1) }}%</strong>
              <div class="mix-bar"><i :style="{ width: `${Math.min(100, Number(row.usage_pct || 0))}%` }" /></div>
            </div>
          </div>
        </section>
      </section>

      <SequenceOutcomeTree
        class="wide-panel"
        :rows="countPitchMixRows"
        :source-rows="sequencePitchRows"
        @select-branch="applyBranch"
      />

      <section class="panel-section wide-panel">
        <header>
          <h2>Count Detail</h2>
          <span>{{ detailCount }}</span>
        </header>
        <div class="condition-controls">
          <label>
            Count
            <select v-model="detailCount">
              <option v-for="option in exactCountOptions" :key="option" :value="option">{{ option }}</option>
            </select>
          </label>
          <label>
            Follow-up Pitch
            <select v-model="followupPitch">
              <option value="All">All</option>
              <option v-for="option in detailPitchOptions" :key="option" :value="option">{{ option }}</option>
            </select>
          </label>
        </div>
        <div class="detail-table-grid">
          <DataTable :title="`Current Pitch | ${detailCount}`" :table="sequence?.tables.count_detail_current" />
          <DataTable title="Next Pitch" :table="sequence?.tables.count_detail_next" />
        </div>
        <DataTable
          :title="followupPitch === 'All' ? 'Immediate Follow-up Events' : `After ${detailCount} -> ${followupPitch}`"
          :table="sequence?.tables.count_followup_events"
        />
      </section>

      <section class="panel-section wide-panel">
        <header>
          <h2>Conditioned Branch</h2>
          <span>{{ conditionLabel }}</span>
        </header>
        <div class="condition-controls">
          <label>
            Count
            <select v-model="conditionCount">
              <option v-for="option in exactCountOptions" :key="option" :value="option">{{ option }}</option>
            </select>
          </label>
          <label>
            Pitch
            <select v-model="conditionPitch">
              <option value="All">All</option>
              <option v-for="option in conditionPitchOptions" :key="option" :value="option">{{ option }}</option>
            </select>
          </label>
        </div>
        <SummaryCards :metrics="conditionMetrics" />
        <SequenceOutcomeTree
          v-if="conditionedCountPitchMixRows.length"
          :rows="conditionedCountPitchMixRows"
          :source-rows="sequencePitchRows"
        />
      </section>

      <section class="dashboard-grid">
        <DataTable title="Conditioned WPA Summary" :table="sequence?.tables.conditioned_wpa_summary" />
        <DataTable title="Shallow Count Sequences" :table="sequence?.tables.shallow_sequences" />
      </section>
      <DataTable class="wide-panel" title="Two-Strike Sequences" :table="sequence?.tables.two_strike_sequences" />
    </template>
  </main>
</template>

<script setup lang="ts">
import type { AnalysisResponse, MetricItem, OptionItem } from '~/types/api'

type SelectOption = { value: string; label: string }

const api = useApi()
const yearOptions = [2026, 2025, 2024, 2023, 2022, 2021]
const exactCountOptions = ['0-0', '0-1', '1-0', '0-2', '1-1', '2-0', '1-2', '2-1', '3-0', '2-2', '3-1', '3-2']
const countOptions = [...exactCountOptions, 'Pitcher Ahead', 'Hitter Ahead', 'Two Strikes']
const standOptions = ['L', 'R']
const pitchResultOptions: SelectOption[] = [
  { value: 'called_strike', label: 'Called Strike' },
  { value: 'swing', label: 'Swing' },
  { value: 'swinging_strike', label: 'Swinging Strike' },
  { value: 'foul', label: 'Foul' },
  { value: 'ball', label: 'Ball' },
  { value: 'in_play', label: 'In Play' }
]

const year = ref(2026)
const catcherId = ref('')
const pairedPitcherId = ref('All')
const stand = ref('All')
const count = ref('All')
const pitch = ref('All')
const pitchResult = ref('All')
const startDate = ref('')
const endDate = ref('')
const conditionCount = ref('0-0')
const conditionPitch = ref('All')
const detailCount = ref('0-0')
const followupPitch = ref('All')
const catcherOptions = ref<OptionItem[]>([])
const pairedPitcherOptions = ref<OptionItem[]>([{ value: 'All', label: 'All', meta: {} }])
const sequence = ref<AnalysisResponse | null>(null)
const loading = ref(false)
const errorMessage = ref('')
let sequenceRequestId = 0

const selectedCatcherLabel = computed(() => catcherOptions.value.find((option) => String(option.value) === catcherId.value)?.label || '')
const sequencePitchRows = computed(() => {
  const rows = sequence.value?.charts.pitch_location_scatter
  return Array.isArray(rows) ? rows.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object' && !Array.isArray(row)) : []
})
const countPitchMixRows = computed(() => asRows(sequence.value?.charts.count_pitch_mix))
const conditionedCountPitchMixRows = computed(() => asRows(sequence.value?.charts.conditioned_count_pitch_mix))
const pairedPitcherMix = computed(() => asRows(sequence.value?.charts.paired_pitcher_mix))
const filteredTotal = computed(() => Number((sequence.value?.charts.filter_snapshot as Record<string, unknown> | undefined)?.pitches || 0))
const snapshotMetrics = computed<MetricItem[]>(() => {
  const snapshot = sequence.value?.charts.filter_snapshot as Record<string, unknown> | undefined
  if (!snapshot) return []
  return [
    { key: 'pitches', label: 'Pitches', value: Number(snapshot.pitches || 0) },
    { key: 'zone_pct', label: 'Zone%', value: snapshot.zone_pct as number | null, unit: '%' },
    { key: 'swing_pct', label: 'Swing%', value: snapshot.swing_pct as number | null, unit: '%' },
    { key: 'strike_pct', label: 'Str%', value: snapshot.strike_pct as number | null, unit: '%' },
    { key: 'whiff_pct', label: 'Whiff%', value: snapshot.whiff_pct as number | null, unit: '%' },
    { key: 'avg', label: 'AVG', value: snapshot.avg as number | null }
  ]
})
const pitchOptions = computed(() => {
  const chartOptions = sequence.value?.charts.pitch_options
  const values = Array.isArray(chartOptions) ? chartOptions.map(String) : []
  const fromRows = sequencePitchRows.value.map((row) => String(row.pitch_name || row.Pitch || '')).filter(Boolean)
  return [...new Set([...values, ...fromRows])].sort()
})
const conditionPitchOptions = computed(() => uniquePitchRows(countPitchMixRows.value, conditionCount.value))
const detailPitchOptions = computed(() => uniquePitchRows(countPitchMixRows.value, detailCount.value))
const conditionMetrics = computed<MetricItem[]>(() => {
  const summary = sequence.value?.charts.conditioned_summary as Record<string, unknown> | undefined
  if (!summary) return []
  return [
    { key: 'pitches', label: 'Pitches', value: Number(summary.pitches || 0) },
    { key: 'strike_pct', label: 'Str%', value: summary.strike_pct as number | null, unit: '%' },
    { key: 'swing_pct', label: 'Swing%', value: summary.swing_pct as number | null, unit: '%' },
    { key: 'whiff_pct', label: 'Whiff%', value: summary.whiff_pct as number | null, unit: '%' },
    { key: 'avg', label: 'AVG', value: summary.avg as number | null }
  ]
})
const conditionLabel = computed(() => `${conditionCount.value} | ${conditionPitch.value}`)

watch(year, async () => {
  await loadCatchers()
}, { immediate: true })

watch(catcherId, async () => {
  await loadPairedPitchers()
}, { immediate: false })

watch(
  [year, catcherId, pairedPitcherId, stand, count, pitch, pitchResult, startDate, endDate, conditionCount, conditionPitch, detailCount, followupPitch],
  () => {
    void loadSequence()
  }
)

async function loadCatchers() {
  errorMessage.value = ''
  catcherOptions.value = []
  catcherId.value = ''
  pairedPitcherId.value = 'All'
  sequence.value = null
  try {
    catcherOptions.value = await api.catcherOptions(year.value)
    catcherId.value = String(catcherOptions.value[0]?.value || '')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load catchers.'
  }
}

async function loadPairedPitchers() {
  const previousPitcherId = pairedPitcherId.value
  pairedPitcherOptions.value = [{ value: 'All', label: 'All', meta: {} }]
  if (!catcherId.value) return
  try {
    const options = await api.catcherPitchers({ year: year.value, catcherId: catcherId.value })
    pairedPitcherOptions.value = options.length ? options : [{ value: 'All', label: 'All', meta: {} }]
    if (!pairedPitcherOptions.value.some((option) => String(option.value) === previousPitcherId)) {
      pairedPitcherId.value = 'All'
    }
  } catch {
    pairedPitcherOptions.value = [{ value: 'All', label: 'All', meta: {} }]
    pairedPitcherId.value = 'All'
  }
}

async function loadSequence() {
  if (!catcherId.value) return
  const requestId = ++sequenceRequestId
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await api.catcherSequence({
      year: year.value,
      catcherId: catcherId.value,
      pitcherId: queryValue(pairedPitcherId.value),
      startDate: queryValue(startDate.value),
      endDate: queryValue(endDate.value),
      stand: queryValue(stand.value),
      count: queryValue(count.value),
      pitch: queryValue(pitch.value),
      pitchResult: queryValue(pitchResult.value),
      conditionCount: queryValue(conditionCount.value),
      conditionPitch: queryValue(conditionPitch.value),
      detailCount: queryValue(detailCount.value),
      followupPitch: queryValue(followupPitch.value)
    })
    if (requestId === sequenceRequestId) {
      sequence.value = response
    }
  } catch (error) {
    if (requestId === sequenceRequestId) {
      errorMessage.value = error instanceof Error ? error.message : 'Failed to load catcher sequence.'
    }
  } finally {
    if (requestId === sequenceRequestId) {
      loading.value = false
    }
  }
}

function clearDates() {
  startDate.value = ''
  endDate.value = ''
}

function applyBranch(branch: { count: string; pitch: string }) {
  conditionCount.value = branch.count
  conditionPitch.value = branch.pitch
  detailCount.value = branch.count
  followupPitch.value = branch.pitch
}

function asRows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object' && !Array.isArray(row)) : []
}

function queryValue(value: unknown) {
  const stringValue = String(value || '').trim()
  return stringValue && stringValue !== 'All' ? stringValue : undefined
}

function uniquePitchRows(rows: Array<Record<string, unknown>>, targetCount: string) {
  return [...new Set(rows.filter((row) => String(row.count) === targetCount).map((row) => String(row.pitch_name || row.Pitch || '')).filter(Boolean))]
}

function formatNumber(value: unknown, digits = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : '-'
}
</script>

<style scoped>
.catcher-sequence-page {
  display: grid;
  gap: 20px;
  padding: 24px;
}

.page-hero,
.filter-panel,
.panel-section,
.state-panel {
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.page-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 26px;
}

.eyebrow {
  color: var(--color-primary);
  font-size: clamp(18px, 1.6vw, 26px);
  font-weight: 900;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  margin-top: 8px;
  font-size: clamp(34px, 4vw, 58px);
  line-height: 1;
}

p {
  margin-top: 8px;
  color: var(--color-text-muted);
  font-size: 18px;
}

.hub-link {
  border: 1px solid var(--color-border-strong);
  border-radius: 999px;
  padding: 10px 18px;
  color: var(--color-primary);
  font-weight: 900;
  text-decoration: none;
}

.filter-panel {
  display: grid;
  grid-template-columns: 0.7fr 1.3fr 1.5fr repeat(4, minmax(130px, 1fr)) repeat(2, 150px) auto auto;
  gap: 12px;
  align-items: end;
  padding: 16px;
}

label {
  display: grid;
  gap: 7px;
  min-width: 0;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

select,
input,
button {
  min-height: 42px;
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  background: var(--color-plot-bg);
  color: var(--color-text);
  padding: 8px 10px;
  font: inherit;
  font-weight: 800;
}

button {
  color: var(--color-primary);
  cursor: pointer;
}

.filter-total {
  color: var(--color-text-muted);
  font-weight: 900;
  white-space: nowrap;
}

.dashboard-grid,
.detail-table-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.wide-panel {
  min-width: 0;
}

.panel-section,
.state-panel {
  padding: 18px;
}

.panel-section header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-section header span {
  color: var(--color-text-muted);
  font-weight: 800;
}

.mix-list {
  display: grid;
  gap: 10px;
}

.mix-row {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) 70px;
  gap: 8px;
  align-items: center;
  color: var(--color-text);
  font-weight: 800;
}

.mix-bar {
  grid-column: 1 / -1;
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-table-header);
}

.mix-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--color-primary), #f97316);
}

.condition-controls {
  display: grid;
  grid-template-columns: repeat(2, minmax(160px, 240px));
  gap: 12px;
  margin-bottom: 14px;
}

@media (max-width: 1500px) {
  .filter-panel {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .page-hero,
  .dashboard-grid,
  .detail-table-grid,
  .condition-controls,
  .filter-panel {
    grid-template-columns: 1fr;
  }

  .page-hero {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
