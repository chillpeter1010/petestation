<template>
  <section class="fingerprint">
    <header>
      <div><span>V2.5 · Timing fingerprint</span><h2>Bat-to-ball alignment</h2><p>球員與聯盟平均的同條件比較；差值只描述表現，不代表因果。</p></div>
      <NuxtLink :to="labLink">Open Timing Lab <ArrowUpRight :size="14" aria-hidden="true" /></NuxtLink>
    </header>
    <div v-if="loading" class="fingerprint-loading"><i v-for="item in 5" :key="item" /></div>
    <p v-else-if="!timing?.player || !timing.league" class="empty">此球季沒有可用的 Swing Timing summary；Statcast tracking 自 2023 明星賽後開始。</p>
    <div v-else class="metrics">
      <article v-for="metric in metrics" :key="metric.label">
        <span>{{ metric.label }}</span><strong>{{ metric.value }}</strong>
        <small :class="metric.tone">{{ metric.delta }} <i>vs MLB {{ metric.league }}</i></small>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ArrowUpRight } from '@lucide/vue'
import type { SwingTimingPlayerDetailResponse } from '~/types/api'

const props = defineProps<{ timing: SwingTimingPlayerDetailResponse | null; loading?: boolean }>()
const player = computed(() => props.timing?.player)
const league = computed(() => props.timing?.league)
const metrics = computed(() => [
  timingMetric('On Time', player.value?.on_time_pct, league.value?.on_time_pct, true, '%'),
  timingMetric('Centered', player.value?.centered_pct, league.value?.centered_pct, true, '%'),
  timingMetric('Lined Up', player.value?.lined_up_pct, league.value?.lined_up_pct, true, '%'),
  timingMetric('Perfect', player.value?.perfect_pct, league.value?.perfect_pct, true, '%'),
  timingMetric('Miss Distance', player.value?.miss_distance, league.value?.miss_distance, false, ' in')
])
const labLink = computed(() => ({
  path: '/batters/lab/swing-timing',
  query: { year: props.timing?.year, batter_id: props.timing?.batter_id, find: props.timing?.name }
}))

function timingMetric(label: string, value: number | null | undefined, baseline: number | null | undefined, higherBetter: boolean, suffix: string) {
  if (value == null || baseline == null) return { label, value: '—', league: '—', delta: 'No data', tone: '' }
  const gap = value - baseline
  const favorable = higherBetter ? gap : -gap
  return {
    label,
    value: `${value.toFixed(1)}${suffix}`,
    league: `${baseline.toFixed(1)}${suffix}`,
    delta: `${gap >= 0 ? '+' : ''}${gap.toFixed(1)}${suffix}`,
    tone: favorable > 0.05 ? 'positive' : favorable < -0.05 ? 'negative' : ''
  }
}
</script>

<style scoped>
.fingerprint { grid-column: 1 / -1; overflow: hidden; border: 1px solid var(--color-border); border-radius: 16px; background: var(--color-surface); box-shadow: var(--shadow-sm); }.fingerprint > header { display: flex; align-items: center; justify-content: space-between; gap: 18px; border-bottom: 1px solid var(--color-border); padding: 17px 19px; }.fingerprint header span { color: var(--color-primary); font-size: 13px; font-weight: 900; letter-spacing: .07em; text-transform: uppercase; }.fingerprint h2 { margin: 4px 0 0; font-size: 25px; }.fingerprint header p { margin: 4px 0 0; color: var(--color-muted-text); font-size: 14px; }.fingerprint header a { display: inline-flex; align-items: center; gap: 6px; flex: 0 0 auto; border-radius: 999px; padding: 9px 13px; color: #111; background: var(--color-primary); font-size: 13px; font-weight: 850; text-decoration: none; }.metrics,.fingerprint-loading { display: grid; grid-template-columns: repeat(5,minmax(0,1fr)); }.metrics article { display: grid; gap: 5px; min-width: 0; border-right: 1px solid var(--color-border); padding: 16px 18px; }.metrics article:last-child { border-right: 0; }.metrics span { color: var(--color-muted-text); font-size: 12px; font-weight: 900; text-transform: uppercase; }.metrics strong { font: 750 27px "Fira Code",monospace; }.metrics small { color: var(--color-muted-text); font-size: 12px; }.metrics small.positive { color: #55b778; }.metrics small.negative { color: #e06b70; }.metrics small i { color: var(--color-muted-text); font-style: normal; }.fingerprint-loading { gap: 10px; padding: 16px; }.fingerprint-loading i { height: 78px; border-radius: 10px; background: var(--color-muted); }.empty { margin: 0; padding: 22px; color: var(--color-muted-text); }@media(max-width:900px){.metrics,.fingerprint-loading{grid-template-columns:repeat(2,1fr)}.metrics article{border-bottom:1px solid var(--color-border)}.fingerprint>header{align-items:flex-start;flex-direction:column}}@media(max-width:560px){.metrics,.fingerprint-loading{grid-template-columns:1fr}}
</style>
