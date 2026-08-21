<template>
  <section class="comparison-details-grid">
    <DataTable :title="tableTitle" :table="table" :max-rows="maxRows" />
    <ComparisonAdvantageSummary
      :title="summaryTitle"
      :subtitle="summarySubtitle"
      :left-title="leftTitle"
      :right-title="rightTitle"
      :left-rows="leftRows"
      :right-rows="rightRows"
    />
  </section>
</template>

<script setup lang="ts">
import type { TablePayload } from '~/types/api'

withDefaults(defineProps<{
  tableTitle: string
  table?: TablePayload
  maxRows?: number
  summaryTitle: string
  summarySubtitle: string
  leftTitle?: string
  rightTitle?: string
  leftRows: Record<string, unknown>[]
  rightRows: Record<string, unknown>[]
}>(), {
  table: undefined,
  maxRows: 16,
  leftTitle: 'Left Edge',
  rightTitle: 'Right Edge'
})
</script>

<style scoped>
.comparison-details-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
  gap: 18px;
  margin-top: 18px;
}

@media (max-width: 940px) {
  .comparison-details-grid {
    grid-template-columns: 1fr;
  }
}
</style>
