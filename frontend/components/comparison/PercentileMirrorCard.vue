<template>
  <section class="percentile-card" :class="side">
    <header>
      <div>
        <p>{{ player?.meta?.year || '-' }} · {{ player?.team || '-' }} · {{ player?.role || '-' }}</p>
        <h2>{{ player?.display_name || 'Select Pitcher' }}</h2>
        <small v-if="player?.meta?.period" class="period-context">{{ player.meta.period }} · {{ Number(player.meta.pitches || 0).toLocaleString() }} pitches</small>
      </div>
      <span>{{ sideLabel }}</span>
    </header>

    <div class="guide">
      <span>{{ isLeft ? 'Great' : 'Poor' }}</span>
      <span>Average</span>
      <span>{{ isLeft ? 'Poor' : 'Great' }}</span>
    </div>

    <div class="metric-list">
      <div v-for="metric in metrics" :key="metric.key" class="metric-row">
        <span class="metric-value">{{ metric.formatted_value }}</span>
        <div class="metric-track">
          <div class="metric-fill" :style="fillStyle(metric)" />
          <i class="metric-dot" :style="dotStyle(metric)">{{ roundedPercentile(metric) }}</i>
        </div>
        <span class="metric-label">{{ metric.label }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { ComparisonMetric, ComparisonPlayer } from '~/types/api'

const props = defineProps<{
  player: ComparisonPlayer | null
  metrics: ComparisonMetric[]
  side: 'left' | 'right'
}>()

const isLeft = computed(() => props.side === 'left')
const sideLabel = computed(() => (isLeft.value ? 'Left' : 'Right'))

function percentile(metric: ComparisonMetric) {
  const value = Number(metric.percentile)
  return Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0
}

function roundedPercentile(metric: ComparisonMetric) {
  return Math.round(percentile(metric))
}

function savantColor(value: number) {
  if (value >= 98) return '#c6322a'
  if (value >= 90) return '#d55243'
  if (value >= 80) return '#dc7b61'
  if (value >= 70) return '#e3a188'
  if (value >= 60) return '#e7bfae'
  if (value >= 40) return '#b8c9cf'
  if (value >= 20) return '#7ea6bc'
  return '#4f7796'
}

function fillStyle(metric: ComparisonMetric) {
  const value = percentile(metric)
  const size = `${value}%`
  return {
    background: savantColor(value),
    width: size,
    left: isLeft.value ? `${100 - value}%` : '0'
  }
}

function dotStyle(metric: ComparisonMetric) {
  const value = percentile(metric)
  return {
    background: savantColor(value),
    left: isLeft.value ? `${100 - value}%` : `${value}%`,
    color: value >= 40 && value <= 60 ? '#111827' : '#ffffff'
  }
}
</script>

<style scoped>
.percentile-card {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 18px;
  background:
    radial-gradient(circle at 50% 0, color-mix(in srgb, var(--color-primary) 10%, transparent), transparent 34%),
    var(--color-surface);
  box-shadow: var(--shadow-md);
}

header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
}

h2,
p {
  margin: 0;
}

p,
header span,
.guide,
.metric-value {
  color: var(--color-muted-text);
}

h2 {
  margin-top: 4px;
  color: var(--color-foreground);
  font-size: 24px;
}

.period-context {
  display: block;
  margin-top: 4px;
  color: var(--color-muted-text);
  font-size: 12px;
}

header span {
  border: 1px solid var(--color-border);
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.guide {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin-bottom: 10px;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.guide span:nth-child(2) {
  text-align: center;
}

.guide span:nth-child(3) {
  text-align: right;
}

.metric-list {
  display: grid;
  gap: 10px;
}

.metric-row {
  display: grid;
  grid-template-columns: 58px minmax(220px, 1fr) 118px;
  align-items: center;
  gap: 12px;
}

.right .metric-row {
  grid-template-columns: 118px minmax(220px, 1fr) 58px;
}

.right .metric-value {
  order: 3;
  text-align: right;
}

.right .metric-track {
  order: 2;
}

.right .metric-label {
  order: 1;
  text-align: right;
}

.metric-value,
.metric-label {
  font-size: 13px;
  font-weight: 800;
}

.metric-label {
  color: var(--color-foreground);
}

.metric-track {
  position: relative;
  height: 28px;
  border-radius: 999px;
  overflow: visible;
  background: color-mix(in srgb, var(--color-muted) 76%, transparent);
}

.metric-fill {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 999px;
}

.metric-dot {
  position: absolute;
  top: 50%;
  display: grid;
  width: 29px;
  height: 29px;
  border: 2px solid var(--color-surface);
  border-radius: 999px;
  color: #ffffff;
  font-size: 10px;
  font-style: normal;
  font-weight: 900;
  place-items: center;
  transform: translate(-50%, -50%);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.22);
}

@media (max-width: 780px) {
  .metric-row,
  .right .metric-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .right .metric-value,
  .right .metric-track,
  .right .metric-label {
    order: initial;
    text-align: left;
  }
}
</style>
