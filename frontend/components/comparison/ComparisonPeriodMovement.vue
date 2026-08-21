<template>
  <section class="period-movement-panel">
    <header>
      <div>
        <h2>{{ title }}</h2>
        <p>{{ subtitle }}</p>
      </div>
      <span>{{ totalPitchTypes.toLocaleString() }} pitch types</span>
    </header>
    <div class="movement-grid">
      <MovementChart
        v-model:mode="leftMode"
        title="Period A Movement"
        :scatter-rows="left.scatter"
        :summary-rows="left.summary"
        :league-rows="left.league"
        :pitcher-hand="left.pitcher_hand"
        allow-stuff-color
        :stuff-color-loading="stuffColorLoading"
        @request-stuff-colors="$emit('request-stuff-colors')"
      />
      <MovementChart
        v-model:mode="rightMode"
        title="Period B Movement"
        :scatter-rows="right.scatter"
        :summary-rows="right.summary"
        :league-rows="right.league"
        :pitcher-hand="right.pitcher_hand"
        allow-stuff-color
        :stuff-color-loading="stuffColorLoading"
        @request-stuff-colors="$emit('request-stuff-colors')"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
type MovementPayload = {
  scatter: Record<string, unknown>[]
  summary: Record<string, unknown>[]
  league: Record<string, unknown>[]
  pitcher_hand?: string
}

const props = withDefaults(defineProps<{
  title?: string
  subtitle?: string
  left: MovementPayload
  right: MovementPayload
  stuffColorLoading?: boolean
}>(), {
  title: 'Period Movement',
  subtitle: 'Movement scatter and average profile by selected date window.'
})

defineEmits<{ 'request-stuff-colors': [] }>()

const leftMode = ref<'scatter' | 'average'>('scatter')
const rightMode = ref<'scatter' | 'average'>('scatter')
const totalPitchTypes = computed(() => props.left.summary.length + props.right.summary.length)
</script>

<style scoped>
.period-movement-panel {
  margin-top: 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.period-movement-panel > header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border);
}

.period-movement-panel h2,
.period-movement-panel p {
  margin: 0;
}

.period-movement-panel h2 {
  color: var(--color-foreground);
  font-size: 16px;
}

.period-movement-panel p,
.period-movement-panel span {
  color: var(--color-muted-text);
  font-size: 13px;
}

.movement-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  align-items: start;
  padding: 14px;
}

.movement-grid :deep(.movement-chart) {
  width: 100%;
}

.movement-grid :deep(.scatter-svg circle) {
  stroke: #020617 !important;
  stroke-width: 1.4 !important;
  vector-effect: non-scaling-stroke;
}

@media (max-width: 940px) {
  .period-movement-panel > header {
    align-items: flex-start;
    flex-direction: column;
  }

  .movement-grid {
    grid-template-columns: 1fr;
  }
}
</style>
