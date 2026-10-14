<template>
  <section class="comparison-cards-grid">
    <slot name="left"><PercentileMirrorCard side="left" :player="leftPlayer" :metrics="leftMetrics" /></slot>
    <slot name="right"><PercentileMirrorCard side="right" :player="rightPlayer" :metrics="rightMetrics" /></slot>
  </section>
</template>

<script setup lang="ts">
import type { ComparisonMetric, ComparisonPlayer } from '~/types/api'

withDefaults(defineProps<{ leftPlayer?: ComparisonPlayer | null; rightPlayer?: ComparisonPlayer | null; leftMetrics?: ComparisonMetric[]; rightMetrics?: ComparisonMetric[] }>(), { leftPlayer: null, rightPlayer: null, leftMetrics: () => [], rightMetrics: () => [] })
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
