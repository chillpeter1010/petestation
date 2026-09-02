<template>
  <section class="batter-zone-heatmap">
    <header>
      <div>
        <span>Zone behavior</span>
        <h2>Swing map</h2>
        <p>{{ description }}</p>
      </div>
      <div class="metric-switch" role="group" aria-label="Heatmap metric">
        <button type="button" :class="{ active: metric === 'bat-speed' }" @click="metric = 'bat-speed'">Bat speed</button>
        <button type="button" :class="{ active: metric === 'choice' }" @click="metric = 'choice'">Choice</button>
      </div>
    </header>
    <StrikeZoneScatter
      :points="points"
      :heatmap-blend="heatmapBlend"
      :heatmap-mode="metric"
      :selected-key="selectedKey"
      :title="metric === 'bat-speed' ? 'Average bat speed by location' : 'Swing choice by location'"
      @select-point="emit('select-point', $event)"
    />
    <footer>
      <span>Lower</span><i aria-hidden="true" /><span>Higher</span>
      <small v-if="metric === 'choice'">Blue = more takes · red = more swings; this is frequency, not a good/bad grade.</small>
      <small v-else>Competitive and tracked swings only; low-sample areas remain faint.</small>
    </footer>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{
  points: Record<string, unknown>[]
  heatmapBlend: number
  selectedKey?: string | null
}>()

const emit = defineEmits<{ 'select-point': [point: Record<string, unknown>] }>()

const metric = ref<'bat-speed' | 'choice'>('bat-speed')
const description = computed(() => metric.value === 'bat-speed'
  ? 'Average tracked bat speed at each pitch location.'
  : 'Swing frequency at each pitch location.')
</script>

<style scoped>
.batter-zone-heatmap {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 0;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.batter-zone-heatmap > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
  padding: 14px 16px;
}

header span {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 850;
  letter-spacing: .06em;
  text-transform: uppercase;
}

h2 { margin: 3px 0 0; color: var(--color-foreground); font-size: 20px; }
p { margin: 3px 0 0; color: var(--color-muted-text); font-size: 13px; }

.metric-switch {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  border-radius: 0;
  background: var(--color-plot-bg);
}

.metric-switch button {
  min-height: 36px;
  border: 0;
  border-right: 1px solid var(--color-border-strong);
  padding: 7px 12px;
  color: var(--color-muted-text);
  background: transparent;
  cursor: pointer;
  font-weight: 750;
}

.metric-switch button:last-child { border-right: 0; }
.metric-switch button.active { color: var(--color-on-primary); background: var(--color-primary); }
.batter-zone-heatmap :deep(.zone-chart) { border: 0; border-radius: 0; box-shadow: none; }

footer {
  display: grid;
  grid-template-columns: auto minmax(120px, 220px) auto minmax(220px, 1fr);
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--color-border);
  padding: 10px 14px;
  color: var(--color-muted-text);
  font-size: 12px;
}

footer i {
  height: 8px;
  border-radius: 999px;
  background: linear-gradient(90deg, #1e3a8a, #dbeafe 48%, #fee2e2 52%, #991b1b);
}

footer small { justify-self: end; text-align: right; }

@media (max-width: 700px) {
  .batter-zone-heatmap > header { align-items: flex-start; flex-direction: column; }
  footer { grid-template-columns: auto 1fr auto; }
  footer small { grid-column: 1 / -1; justify-self: start; text-align: left; }
}
</style>
