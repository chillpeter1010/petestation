<template>
  <section class="panel-grid">
    <section class="stuff-filters wide-panel">
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
        Paired Catcher
        <CheckboxDropdown v-model="catcher" :options="catcherOptions" />
      </label>
      <label class="range-filter">
        Heatmap Blend
        <input v-model.number="heatmapBlend" type="range" min="0" max="1" step="0.1">
        <span>{{ Math.round(heatmapBlend * 100) }}%</span>
      </label>
      <span class="filter-status">{{ loading ? 'Updating Discipline' : `${filteredTotal || 0} filtered pitches` }}</span>
    </section>
    <SummaryCards :metrics="snapshotMetrics" />
    <DataTable title="Summary" :table="discipline?.tables.discipline_summary" />
    <DataTable title="Stand Split" :table="discipline?.tables.stand_split" />
    <DisciplinePanelBoard
      :heatmap-blend="heatmapBlend"
      :pitch-result-panels="resultPanels"
      :pa-result-panels="paResultPanels"
      :batted-ball-panels="battedBallPanels"
      :count-situation-panels="countPanels"
      :count-swing-panels="countSwingPanels"
      :exact-count-panels="exactCountPanels"
    />
  </section>
</template>

<script setup lang="ts">
import type { AnalysisResponse, MetricItem } from '~/types/api'

type Panel = {
  key: string
  label: string
  rows: Array<Record<string, unknown>>
}

const stand = defineModel<string>('stand', { required: true })
const count = defineModel<string>('count', { required: true })
const pitch = defineModel<string>('pitch', { required: true })
const catcher = defineModel<string>('catcher', { required: true })
const heatmapBlend = defineModel<number>('heatmapBlend', { required: true })

defineProps<{
  discipline: AnalysisResponse | null
  standOptions: string[]
  countOptions: string[]
  pitchOptions: string[]
  catcherOptions: string[]
  loading: boolean
  filteredTotal: number | null
  snapshotMetrics: MetricItem[]
  resultPanels: Panel[]
  paResultPanels: Panel[]
  battedBallPanels: Panel[]
  countPanels: Panel[]
  countSwingPanels: Panel[]
  exactCountPanels: Panel[]
}>()
</script>
