<template>
  <section class="panel-grid">
    <DisciplineFiltersBar
      v-model:stand="stand"
      v-model:count="count"
      v-model:pitch="pitch"
      v-model:secondary="catcher"
      v-model:heatmap-blend="heatmapBlend"
      :stand-options="standOptions"
      :count-options="countOptions"
      :pitch-options="pitchOptions"
      secondary-label="Paired catcher"
      :secondary-options="catcherOptions"
      :loading="loading"
      :filtered-total="filteredTotal"
    />
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
