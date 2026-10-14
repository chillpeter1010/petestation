<template>
  <section class="panel-grid">
    <PercentileMirrorCard
      v-if="percentileMetrics.length"
      class="percentile-profile"
      side="right"
      :player="pitcher"
      :metrics="percentileMetrics"
    />
    <DataTable title="Dashboard" :table="overview?.tables.dashboard" :max-rows="4" />
    <DataTable title="BR / Rotation" :table="overview?.tables.br" :max-rows="4" />
    <DataTable class="game-log-table" title="Season Game Log" :table="overview?.tables.game_log" :max-rows="80" />
  </section>
</template>

<script setup lang="ts">
import PercentileMirrorCard from '~/components/comparison/PercentileMirrorCard.vue'
import type { ComparisonMetric, ComparisonPlayer, PersonalOverviewResponse } from '~/types/api'

const props = defineProps<{
  overview: PersonalOverviewResponse | null
}>()

const percentileMetrics = computed(() => {
  const metrics = props.overview?.charts?.percentile_profile
  return Array.isArray(metrics) ? metrics as ComparisonMetric[] : []
})

const pitcher = computed<ComparisonPlayer | null>(() => {
  const selected = props.overview?.selected_pitcher
  if (!selected) return null
  const name = String(selected.name || selected.label || 'Pitcher Percentile Rankings')
  return {
    player_id: Number(selected.value || props.overview?.pitcher_id || 0),
    display_name: name,
    team: String(selected.team || '-'),
    role: String(selected.role || '-'),
    display_label: name,
    meta: { year: props.overview?.meta.year || null }
  }
})
</script>

<style scoped>
.panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.game-log-table {
  grid-column: 1 / -1;
}

.percentile-profile {
  grid-column: 1 / -1;
}

@media (max-width: 900px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
