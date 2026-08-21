<template>
  <section class="comparison-cards-grid">
    <PercentileMirrorCard side="left" :player="leftPlayer" :metrics="leftMetrics" />
    <PercentileMirrorCard side="right" :player="rightPlayer" :metrics="rightMetrics" />
  </section>
</template>

<script setup lang="ts">
import type { ComparisonMetric, ComparisonPlayer } from '~/types/api'

defineProps<{
  leftPlayer: ComparisonPlayer | null
  rightPlayer: ComparisonPlayer | null
  leftMetrics: ComparisonMetric[]
  rightMetrics: ComparisonMetric[]
}>()
</script>

<style scoped>
.comparison-cards-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-top: 18px;
}

@media (max-width: 940px) {
  .comparison-cards-grid {
    grid-template-columns: 1fr;
  }
}
</style>
