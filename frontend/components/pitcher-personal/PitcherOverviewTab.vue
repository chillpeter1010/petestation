<template>
  <section class="panel-grid">
    <DataTable title="Dashboard" :table="overview?.tables.dashboard" :max-rows="4" />
    <DataTable title="BR / Rotation" :table="overview?.tables.br" :max-rows="4" />
    <DataTable class="game-log-table" title="Season Game Log" :table="overview?.tables.game_log" :max-rows="80" />
  </section>
</template>

<script setup lang="ts">
import type { PersonalOverviewResponse } from '~/types/api'

defineProps<{
  overview: PersonalOverviewResponse | null
}>()
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

@media (max-width: 900px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
