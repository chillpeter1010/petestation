<template>
  <section class="percentile-profile">
    <header>
      <h2>{{ year }} MLB Percentile Rankings</h2>
      <small>Minimum 50 PA</small>
    </header>
    <div class="guide"><i /><span>Great</span><span>Average</span><span>Poor</span><i /></div>
    <div v-if="metrics.length" class="metric-groups">
      <section v-for="group in groups" :key="group.label">
        <h3>{{ group.label }}</h3>
        <div v-for="metric in group.metrics" :key="metric.key" class="percentile-row">
          <strong>{{ displayValue(metric) }}</strong>
          <div class="track"><b :style="markerStyle(metric)">{{ percentile(metric) }}</b></div>
          <span>{{ metric.label }}</span>
        </div>
      </section>
    </div>
    <p v-else class="empty">No qualified percentile profile is available.</p>
    <footer>Higher percentile is always more favorable.</footer>
  </section>
</template>

<script setup lang="ts">
import { performanceColor } from '~/utils/performanceColor'

export type BatterPercentileMetric = {
  key: string
  label: string
  value: number | null
  unit: 'runs' | 'rate' | 'mph' | 'percent'
  percentile: number | null
  sample: number
}

const props = defineProps<{ year: number; metrics: BatterPercentileMetric[] }>()
const groups = computed(() => [
  { label: 'Value', metrics: props.metrics.filter(metric => metric.key === 'batting_run_value') },
  { label: 'Batting', metrics: props.metrics.filter(metric => metric.key !== 'batting_run_value') }
].filter(group => group.metrics.length))

function percentile(metric: BatterPercentileMetric) {
  const value = Number(metric.percentile)
  return Number.isFinite(value) ? Math.round(value) : '-'
}

function markerStyle(metric: BatterPercentileMetric) {
  const value = Number(metric.percentile)
  const percentileValue = Number.isFinite(value) ? Math.max(2, Math.min(98, value)) : 50
  return { left: `${100 - percentileValue}%`, background: performanceColor((percentileValue - 50) / 50) }
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

<style scoped>
.percentile-profile {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 0;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.percentile-profile > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 14px 16px;
}

h2 { margin: 0; color: var(--color-foreground); font-size: 20px; }
header small { color: var(--color-muted-text); font-size: 11px; }
.guide { display: grid; grid-template-columns: 58px repeat(3, 1fr) 112px; align-items: center; padding: 10px 16px 2px; color: var(--color-muted-text); font-size: 10px; font-weight: 850; text-transform: uppercase; }
.guide span:nth-of-type(2) { text-align: center; }
.guide span:nth-of-type(3) { text-align: right; }
.metric-groups { display: grid; gap: 10px; padding: 12px 16px 14px; }
.metric-groups section { display: grid; gap: 7px; }
h3 { margin: 0; border-bottom: 1px solid var(--color-border); padding-bottom: 5px; color: var(--color-foreground); font-size: 14px; }
.percentile-row { display: grid; grid-template-columns: 58px minmax(150px, 1fr) 112px; align-items: center; gap: 10px; min-height: 31px; }
.percentile-row > span { color: var(--color-foreground); font-size: 12px; font-weight: 800; }
.track { position: relative; height: 24px; border: 1px solid var(--color-border); border-radius: 999px; background: linear-gradient(90deg, rgb(132 24 35), rgb(211 61 65), rgb(252 190 190), rgb(248 250 252), rgb(186 217 239), rgb(45 104 178), rgb(23 55 110)); }
.track > b { position: absolute; top: 50%; display: grid; place-items: center; width: 27px; height: 27px; border: 2px solid var(--color-surface); border-radius: 50%; color: #fff; font: 800 10px "Fira Sans", sans-serif; transform: translate(-50%, -50%); box-shadow: 0 5px 12px rgba(0, 0, 0, .2); }
.percentile-row > strong { color: var(--color-text); font: 650 12px "Fira Code", monospace; }
.percentile-profile > footer { border-top: 1px solid var(--color-border); padding: 9px 14px; color: var(--color-muted-text); font-size: 10px; line-height: 1.4; }
.empty { margin: 0; padding: 28px 16px; color: var(--color-muted-text); }
</style>
