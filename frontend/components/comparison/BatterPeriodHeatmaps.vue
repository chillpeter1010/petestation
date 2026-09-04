<template>
  <section class="period-heatmaps">
    <header>
      <div>
        <span>Zone behavior</span>
        <h2>Period A / B swing maps</h2>
        <p>{{ explanation }}</p>
      </div>
      <div class="metric-switch" role="group" aria-label="Heatmap metric">
        <button type="button" :class="{ active: metric === 'bat-speed' }" @click="metric = 'bat-speed'">Bat speed</button>
        <button type="button" :class="{ active: metric === 'choice' }" @click="metric = 'choice'">Choice</button>
      </div>
    </header>
    <HeatmapBlendControl v-model="blend" title="Shared A/B heatmap blend" />
    <div class="zone-grid">
      <StrikeZoneScatter
        :points="leftPoints"
        :total-pitches="leftPoints.length"
        :title="`Period A · ${chartTitle}`"
        :heatmap-blend="blend"
        :heatmap-mode="metric"
        :heatmap-metric-domain="activeDomain"
        compact
      />
      <StrikeZoneScatter
        :points="rightPoints"
        :total-pitches="rightPoints.length"
        :title="`Period B · ${chartTitle}`"
        :heatmap-blend="blend"
        :heatmap-mode="metric"
        :heatmap-metric-domain="activeDomain"
        compact
      />
    </div>
    <footer>
      <span>Lower</span><i aria-hidden="true" /><span>Higher</span>
      <small>{{ footerNote }}</small>
    </footer>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{
  leftPoints: Record<string, unknown>[]
  rightPoints: Record<string, unknown>[]
  batSpeedDomain: [number, number] | null
}>()

const metric = ref<'bat-speed' | 'choice'>('bat-speed')
const blend = ref(0.8)
const activeDomain = computed(() => metric.value === 'bat-speed' ? props.batSpeedDomain : [0, 1] as [number, number])
const chartTitle = computed(() => metric.value === 'bat-speed' ? 'Competitive bat speed' : 'Swing frequency')
const explanation = computed(() => metric.value === 'bat-speed'
  ? 'Both periods use the same mph color domain; only competitive tracked swings contribute.'
  : 'Both periods use the same 0–100% swing-frequency color domain.')
const footerNote = computed(() => metric.value === 'choice'
  ? 'Blue = fewer swings · red = more swings. Frequency is not a good/bad grade.'
  : 'Low-sample areas remain faint; untracked and non-competitive swings do not enter the average.')
</script>

<style scoped>
.period-heatmaps {
  margin-top: 18px;
  border: 1px solid var(--color-border);
  border-radius: 0;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.period-heatmaps > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}

header span { color: var(--color-primary); font-size: 12px; font-weight: 850; text-transform: uppercase; }
h2 { margin: 3px 0 0; color: var(--color-foreground); font-size: 20px; }
p { margin: 4px 0 0; color: var(--color-muted-text); font-size: 13px; }

.metric-switch { display: inline-flex; border: 1px solid var(--color-border-strong); }
.metric-switch button { min-height: 36px; border: 0; border-right: 1px solid var(--color-border-strong); padding: 7px 12px; color: var(--color-muted-text); background: var(--color-plot-bg); cursor: pointer; font-weight: 800; }
.metric-switch button:last-child { border-right: 0; }
.metric-switch button.active { color: var(--color-on-primary); background: var(--color-primary); }
.period-heatmaps :deep(.heatmap-blend-control) { border: 0; border-bottom: 1px solid var(--color-border); border-radius: 0; box-shadow: none; }
.zone-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: var(--color-border); }
.zone-grid :deep(.zone-chart) { border: 0; border-radius: 0; box-shadow: none; }
footer { display: grid; grid-template-columns: auto minmax(120px, 220px) auto minmax(260px, 1fr); align-items: center; gap: 8px; padding: 10px 14px; border-top: 1px solid var(--color-border); color: var(--color-muted-text); font-size: 12px; }
footer i { height: 8px; background: linear-gradient(90deg, #1e3a8a, #dbeafe 48%, #fee2e2 52%, #991b1b); }
footer small { justify-self: end; text-align: right; }

@media (max-width: 820px) {
  .period-heatmaps > header { align-items: flex-start; flex-direction: column; }
  .zone-grid { grid-template-columns: 1fr; }
  footer { grid-template-columns: auto 1fr auto; }
  footer small { grid-column: 1 / -1; justify-self: start; text-align: left; }
}
</style>
