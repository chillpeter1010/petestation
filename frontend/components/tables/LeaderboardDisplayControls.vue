<template>
  <div class="leaderboard-display-controls">
    <div class="display-control">
      <span>Display</span>
      <div class="mode-toggle" role="group" aria-label="Metric display">
        <button type="button" :class="{ active: displayMode === 'actual' }" :aria-pressed="displayMode === 'actual'" @click="$emit('update:displayMode', 'actual')">實際數據</button>
        <button type="button" :class="{ active: displayMode === 'percentile' }" :aria-pressed="displayMode === 'percentile'" @click="$emit('update:displayMode', 'percentile')">PR值</button>
      </div>
    </div>
    <div class="display-control">
      <span>Heat map</span>
      <div class="mode-toggle" role="group" aria-label="Heat map">
        <button type="button" :class="{ active: !heatmapEnabled }" :aria-pressed="!heatmapEnabled" @click="$emit('update:heatmapEnabled', false)">Off</button>
        <button type="button" :class="{ active: heatmapEnabled }" :aria-pressed="heatmapEnabled" @click="$emit('update:heatmapEnabled', true)">On</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { LeaderboardDisplayMode } from '~/utils/leaderboardDisplay'

defineProps<{ displayMode: LeaderboardDisplayMode; heatmapEnabled: boolean }>()
defineEmits<{
  'update:displayMode': [value: LeaderboardDisplayMode]
  'update:heatmapEnabled': [value: boolean]
}>()
</script>

<style scoped>
.leaderboard-display-controls { display: flex; align-items: end; justify-content: flex-end; gap: 12px; flex-wrap: wrap; }
.display-control { display: grid; gap: 5px; }
.display-control > span { color: var(--color-muted-text); font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.mode-toggle { display: flex; border: 1px solid var(--color-border); border-radius: 9px; padding: 3px; background: var(--color-background); }
.mode-toggle button { min-height: 34px; border: 0; border-radius: 6px; padding: 6px 12px; color: var(--color-muted-text); background: transparent; cursor: pointer; font: inherit; font-size: 13px; font-weight: 800; }
.mode-toggle button.active { color: var(--color-on-primary); background: var(--color-primary); }
.mode-toggle button:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
@media (max-width: 680px) { .leaderboard-display-controls { justify-content: flex-start; } }
</style>
