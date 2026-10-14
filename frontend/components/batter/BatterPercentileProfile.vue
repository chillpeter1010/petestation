<template>
  <PercentileMirrorCard side="right" :player="player" :metrics="comparisonMetrics" />
</template>

<script setup lang="ts">
import PercentileMirrorCard from '~/components/comparison/PercentileMirrorCard.vue'
import type { ComparisonMetric, ComparisonPlayer } from '~/types/api'

export type BatterPercentileMetric = {
  key: string
  label: string
  value: number | null
  unit: 'runs' | 'rate' | 'mph' | 'percent'
  percentile: number | null
  sample: number
}

const props = withDefaults(defineProps<{ year: number; playerId?: number; name?: string; team?: string; metrics: BatterPercentileMetric[] }>(), {
  playerId: 0,
  name: '',
  team: ''
})
const player = computed<ComparisonPlayer>(() => ({
  player_id: props.playerId,
  display_name: props.name || 'MLB Percentile Rankings',
  team: props.team || '-',
  role: 'Batter',
  display_label: props.name || 'MLB Percentile Rankings',
  meta: { year: props.year }
}))
const comparisonMetrics = computed<ComparisonMetric[]>(() => props.metrics.map(toComparisonMetric))

function toComparisonMetric(metric: BatterPercentileMetric): ComparisonMetric {
  return {
    key: metric.key,
    label: metric.label,
    value: metric.value,
    formatted_value: displayValue(metric),
    percentile: metric.percentile,
    higher_is_better: !['chase_rate', 'whiff_rate', 'strikeout_rate'].includes(metric.key)
  }
}

function displayValue(metric: BatterPercentileMetric) {
  if (metric.value == null || !Number.isFinite(Number(metric.value))) return '-'
  const value = Number(metric.value)
  if (metric.unit === 'percent') return `${(value * 100).toFixed(1)}%`
  if (metric.unit === 'rate') return value.toFixed(3).replace(/^0/, '')
  if (metric.unit === 'mph') return value.toFixed(1)
  return value.toFixed(1)
}
</script>
