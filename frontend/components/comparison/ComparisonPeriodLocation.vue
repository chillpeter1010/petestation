<template>
  <section class="period-location-panel">
    <header>
      <div>
        <h2>{{ title }}</h2>
        <p>{{ subtitle }}</p>
      </div>
      <span>{{ totalPitches.toLocaleString() }} pitches</span>
    </header>
    <div class="location-grid">
      <StrikeZoneScatter
        title="Period A Location"
        :points="leftPoints"
        :total-pitches="leftPoints.length"
        :selected-key="leftSelectedKey"
        :point-scale="1"
        :plot-scale="1.25"
        compact
        @select-point="emit('select-left-point', $event)"
      />
      <StrikeZoneScatter
        title="Period B Location"
        :points="rightPoints"
        :total-pitches="rightPoints.length"
        :selected-key="rightSelectedKey"
        :point-scale="1"
        :plot-scale="1.25"
        compact
        @select-point="emit('select-right-point', $event)"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  title?: string
  subtitle?: string
  leftPoints: Record<string, unknown>[]
  rightPoints: Record<string, unknown>[]
  leftSelectedKey?: string | null
  rightSelectedKey?: string | null
}>(), {
  title: 'Period Location',
  subtitle: 'Pitch location scatter by selected date window.',
  leftSelectedKey: null,
  rightSelectedKey: null
})

const emit = defineEmits<{
  'select-left-point': [point: Record<string, unknown>]
  'select-right-point': [point: Record<string, unknown>]
}>()

const totalPitches = computed(() => props.leftPoints.length + props.rightPoints.length)
</script>

<style scoped>
.period-location-panel {
  margin-top: 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.period-location-panel > header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border);
}

.period-location-panel h2,
.period-location-panel p {
  margin: 0;
}

.period-location-panel h2 {
  color: var(--color-foreground);
  font-size: 16px;
}

.period-location-panel p,
.period-location-panel span {
  color: var(--color-muted-text);
  font-size: 13px;
}

.location-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  padding: 14px;
  min-height: 620px;
}

.period-location-panel :deep(.zone-chart.compact .plot-wrap) {
  min-height: 500px;
  display: flex;
  align-items: center;
}

.period-location-panel :deep(.zone-chart.compact svg) {
  max-height: 540px;
}

@media (max-width: 940px) {
  .period-location-panel > header {
    align-items: flex-start;
    flex-direction: column;
  }

  .location-grid {
    grid-template-columns: 1fr;
  }
}
</style>
