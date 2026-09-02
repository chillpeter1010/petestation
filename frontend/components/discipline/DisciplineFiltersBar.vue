<template>
  <section class="discipline-filters-bar wide-panel" aria-label="Discipline filters">
    <label>
      <span>Stand</span>
      <CheckboxDropdown v-model="stand" :options="standOptions" />
    </label>
    <label>
      <span>Count</span>
      <CheckboxDropdown v-model="count" :options="countOptions" />
    </label>
    <label>
      <span>Pitch</span>
      <CheckboxDropdown v-model="pitch" :options="pitchOptions" />
    </label>
    <label v-if="secondaryLabel">
      <span>{{ secondaryLabel }}</span>
      <CheckboxDropdown v-model="secondary" :options="secondaryOptions" />
    </label>
    <label v-if="showDates" class="date-filter">
      <span>Start date</span>
      <input v-model="startDate" type="date">
    </label>
    <label v-if="showDates" class="date-filter">
      <span>End date</span>
      <input v-model="endDate" type="date">
    </label>
    <button v-if="showDates" class="clear-dates" type="button" @click="clearDates">Clear dates</button>
    <span class="filter-status">{{ loading ? 'Updating discipline' : `${(filteredTotal || 0).toLocaleString()} filtered pitches` }}</span>
    <HeatmapBlendControl v-if="showHeatmap" v-model="heatmapBlend" class="heatmap-control" />
  </section>
</template>

<script setup lang="ts">
type FilterOption = string | { value: string; label: string }

const stand = defineModel<string>('stand', { required: true })
const count = defineModel<string>('count', { required: true })
const pitch = defineModel<string>('pitch', { required: true })
const secondary = defineModel<string>('secondary', { default: 'All' })
const startDate = defineModel<string>('startDate', { default: '' })
const endDate = defineModel<string>('endDate', { default: '' })
const heatmapBlend = defineModel<number>('heatmapBlend', { required: true })

withDefaults(defineProps<{
  standOptions: FilterOption[]
  countOptions: FilterOption[]
  pitchOptions: FilterOption[]
  secondaryLabel?: string
  secondaryOptions?: FilterOption[]
  showDates?: boolean
  showHeatmap?: boolean
  loading?: boolean
  filteredTotal?: number | null
}>(), {
  secondaryLabel: '',
  secondaryOptions: () => ['All'],
  showDates: false,
  showHeatmap: true,
  loading: false,
  filteredTotal: 0
})

function clearDates() {
  startDate.value = ''
  endDate.value = ''
}
</script>

<style scoped>
.discipline-filters-bar {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr)) repeat(2, minmax(145px, .85fr)) auto;
  align-items: end;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: 0;
  padding: 14px;
  background: color-mix(in srgb, var(--color-surface) 86%, transparent);
  box-shadow: var(--shadow-sm);
}

label {
  min-width: 0;
  display: grid;
  gap: 6px;
}

label > span {
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 750;
  letter-spacing: .04em;
  text-transform: uppercase;
}

.date-filter input {
  width: 100%;
  min-height: 38px;
  border: 1px solid var(--color-border-strong);
  border-radius: 0;
  padding: 7px 10px;
  color: var(--color-text);
  background: var(--color-plot-bg);
}

.clear-dates {
  min-height: 38px;
  border: 1px solid var(--color-border-strong);
  border-radius: 0;
  padding: 7px 11px;
  color: var(--color-text);
  background: var(--color-muted);
  cursor: pointer;
  font-weight: 750;
}

.filter-status {
  align-self: center;
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
}

.heatmap-control { grid-column: 1 / -1; }

@media (max-width: 1260px) {
  .discipline-filters-bar { grid-template-columns: repeat(3, minmax(150px, 1fr)); }
}

@media (max-width: 760px) {
  .discipline-filters-bar { grid-template-columns: 1fr; }
}
</style>
