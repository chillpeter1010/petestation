<template>
  <section class="panel-grid">
    <SummaryCards :metrics="rotation?.summary || []" />
    <WpaLineChart class="wide-panel" :rows="wpaGameRows" />
    <section class="rotation-control wide-panel">
      <label>
        Rotation / Fatigue Game
        <select v-model.number="selectedGamePk">
          <option v-for="row in wpaGameRows" :key="String(row.game_pk)" :value="Number(row.game_pk)">
            {{ row.label || `${String(row.game_date).slice(0, 10)} | gamePk ${row.game_pk}` }}
          </option>
        </select>
      </label>
    </section>
    <SummaryCards :metrics="fatigueMetrics" />
    <FatigueBarChart :rows="fatigueRows" />
    <DataTable title="Game Log" :table="rotation?.tables.game_log" />
    <DataTable title="WPA Games" :table="wpaGamesTable" />
    <DataTable title="Fatigue By Inning" :table="rotation?.tables.fatigue_by_inning" />
  </section>
</template>

<script setup lang="ts">
import type { AnalysisResponse, MetricItem, TablePayload } from '~/types/api'

const selectedGamePk = defineModel<number | null>('selectedGamePk', { required: true })

defineProps<{
  rotation: AnalysisResponse | null
  wpaGameRows: Array<Record<string, unknown>>
  fatigueMetrics: MetricItem[]
  fatigueRows: Array<Record<string, unknown>>
  wpaGamesTable: TablePayload
}>()
</script>
