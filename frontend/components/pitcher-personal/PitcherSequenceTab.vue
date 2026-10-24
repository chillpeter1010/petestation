<template>
  <section class="panel-grid">
    <section class="stuff-filters wide-panel">
      <label>
        Year
        <select v-model="year">
          <option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <label>
        Batter Side
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
        Paired Catcher
        <CheckboxDropdown v-model="catcher" :options="catcherOptions" />
      </label>
      <label class="date-range-toggle">
        Date Detail
        <span class="date-range-toggle__control">
          <input v-model="useCustomDates" type="checkbox">
          Use date range
        </span>
      </label>
      <label>
        Start Date
        <input v-model="startDate" type="date" :min="`${year}-01-01`" :max="`${year}-12-31`" :disabled="!useCustomDates">
      </label>
      <label>
        End Date
        <input v-model="endDate" type="date" :min="`${year}-01-01`" :max="`${year}-12-31`" :disabled="!useCustomDates">
      </label>
      <button class="clear-date-button" type="button" @click="useFullSeason">Full Season</button>
      <span class="filter-status">{{ loading ? 'Updating Sequence' : `${activeScope} · ${filteredTotal || 0} filtered pitches` }}</span>
    </section>
    <SummaryCards :metrics="snapshotMetrics" />
    <SequenceOutcomeTree
      class="wide-panel"
      :rows="countPitchMixRows"
      :source-rows="sequencePitchRows"
      @select-branch="applyBranch"
    />
    <section class="panel-section wide-panel">
      <header>
        <h2>Count Detail</h2>
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
        <span class="filter-status">Current and next-count pitch mix</span>
      </div>
      <div class="detail-table-grid">
        <DataTable :title="`Current Pitch | ${detailCount}`" :table="sequence?.tables.count_detail_current" />
        <DataTable title="Next Pitch" :table="sequence?.tables.count_detail_next" />
      </div>
      <DataTable
        class="followup-table"
        :title="followupPitch === 'All' ? 'Immediate Follow-up Events' : `After ${detailCount} -> ${followupPitch}`"
        :table="sequence?.tables.count_followup_events"
      />
    </section>
    <section class="panel-section wide-panel">
      <header>
        <h2>Conditioned Branch</h2>
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
        <span class="filter-status">{{ conditionLabel }}</span>
      </div>
      <SummaryCards :metrics="conditionMetrics" />
      <SequenceOutcomeTree v-if="conditionedCountPitchMixRows.length" :rows="conditionedCountPitchMixRows" :source-rows="sequencePitchRows" />
      <p v-else class="muted-note">Select a pitch branch to show downstream count-state pitch mix.</p>
    </section>
    <DataTable title="Conditioned WPA Summary" :table="sequence?.tables.conditioned_wpa_summary" />
    <DataTable title="Shallow Count Sequences" :table="sequence?.tables.shallow_sequences" />
    <DataTable title="Two-Strike Sequences" :table="sequence?.tables.two_strike_sequences" />
  </section>
</template>

<script setup lang="ts">
import type { AnalysisResponse, MetricItem } from '~/types/api'

type SelectOption = { value: string; label: string }

const year = defineModel<number>('year', { required: true })
const stand = defineModel<string>('stand', { required: true })
const count = defineModel<string>('count', { required: true })
const pitch = defineModel<string>('pitch', { required: true })
const pitchResult = defineModel<string>('pitchResult', { required: true })
const catcher = defineModel<string>('catcher', { required: true })
const useCustomDates = defineModel<boolean>('useCustomDates', { required: true })
const startDate = defineModel<string>('startDate', { required: true })
const endDate = defineModel<string>('endDate', { required: true })
const conditionCount = defineModel<string>('conditionCount', { required: true })
const conditionPitch = defineModel<string>('conditionPitch', { required: true })
const detailCount = defineModel<string>('detailCount', { required: true })
const followupPitch = defineModel<string>('followupPitch', { required: true })

const props = defineProps<{
  sequence: AnalysisResponse | null
  yearOptions: number[]
  standOptions: SelectOption[]
  countOptions: string[]
  exactCountOptions: string[]
  pitchOptions: string[]
  pitchResultOptions: SelectOption[]
  catcherOptions: string[]
  loading: boolean
  filteredTotal: number | null
  snapshotMetrics: MetricItem[]
  countPitchMixRows: Array<Record<string, unknown>>
  conditionedCountPitchMixRows: Array<Record<string, unknown>>
  conditionPitchOptions: string[]
  detailPitchOptions: string[]
  conditionMetrics: MetricItem[]
  conditionLabel: string
}>()

const sequencePitchRows = computed(() => {
  const rows = props.sequence?.charts.pitch_location_scatter
  return Array.isArray(rows) ? rows.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object' && !Array.isArray(row)) : []
})

const activeScope = computed(() => {
  const standLabel = props.standOptions.find((option) => option.value === stand.value)?.label || stand.value
  const dateLabel = useCustomDates.value && (startDate.value || endDate.value)
    ? `${startDate.value || `${year.value}-01-01`} to ${endDate.value || `${year.value}-12-31`}`
    : `${year.value} full season`
  return `${dateLabel} · ${standLabel}`
})

function applyBranch(branch: { count: string; pitch: string }) {
  conditionCount.value = branch.count
  conditionPitch.value = branch.pitch
  detailCount.value = branch.count
  followupPitch.value = branch.pitch
}

function useFullSeason() {
  useCustomDates.value = false
  startDate.value = ''
  endDate.value = ''
}
</script>

<style scoped>
.clear-date-button {
  align-self: end;
  min-height: 38px;
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  background: var(--color-plot-bg);
  color: var(--color-text);
  font-weight: 800;
  cursor: pointer;
}

.clear-date-button:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.date-range-toggle__control {
  min-height: 38px;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  background: var(--color-plot-bg);
  color: var(--color-text);
  font-size: 13px;
  font-weight: 750;
  text-transform: none;
}

.date-range-toggle__control input {
  width: 15px;
  height: 15px;
  margin: 0;
  accent-color: var(--color-primary);
}
</style>
