<template>
  <section class="dimension-chart">
    <header><div><span>V2.2 · 3D alignment</span><h4>Bat-to-ball timing summary</h4></div><small>Player bar · league marker</small></header>
    <div class="axes">
      <article v-for="axis in axes" :key="axis.title">
        <h5>{{ axis.title }}</h5>
        <div v-for="metric in axis.metrics" :key="metric.label" class="metric">
          <div><b>{{ metric.label }}</b><span>{{ pct(metric.player) }} <small>MLB {{ pct(metric.league) }}</small></span></div>
          <div class="track"><i :style="{ width: `${clamp(metric.player)}%` }" /><em :style="{ left: `${clamp(metric.league)}%` }" /></div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { SwingTimingLeaderboardRow } from '~/types/api'
const props = defineProps<{ player: SwingTimingLeaderboardRow; league: SwingTimingLeaderboardRow }>()
const axes = computed(() => [
  { title: 'Horizontal · inches', metrics: [
    { label: 'Tied Up', player: props.player.tied_up_pct, league: props.league.tied_up_pct },
    { label: 'Centered', player: props.player.centered_pct, league: props.league.centered_pct },
    { label: 'Flail', player: props.player.flail_pct, league: props.league.flail_pct }
  ] },
  { title: 'Timing · milliseconds', metrics: [
    { label: 'Late', player: props.player.late_pct, league: props.league.late_pct },
    { label: 'On Time', player: props.player.on_time_pct, league: props.league.on_time_pct },
    { label: 'Early', player: props.player.early_pct, league: props.league.early_pct }
  ] },
  { title: 'Vertical · inches', metrics: [
    { label: 'Over', player: props.player.over_pct, league: props.league.over_pct },
    { label: 'Lined Up', player: props.player.lined_up_pct, league: props.league.lined_up_pct },
    { label: 'Under', player: props.player.under_pct, league: props.league.under_pct }
  ] }
])
function clamp(value: number | null) { return Math.max(0, Math.min(100, value || 0)) }
function pct(value: number | null) { return value == null ? '—' : `${value.toFixed(1)}%` }
</script>

<style scoped>
.dimension-chart { margin-top: 14px; border: 1px solid var(--color-border); border-radius: 14px; padding: 16px; background: var(--color-surface); }.dimension-chart > header { display: flex; justify-content: space-between; gap: 16px; }.dimension-chart header span { color: var(--color-primary); font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }.dimension-chart h4 { margin: 3px 0 0; font-size: 17px; }.dimension-chart header small { color: var(--color-muted-text); }.axes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 14px; }.axes article { border: 1px solid var(--color-border); border-radius: 10px; padding: 12px; }.axes h5 { margin: 0 0 12px; }.metric { margin-top: 9px; }.metric > div:first-child { display: flex; justify-content: space-between; font-size: 10px; }.metric span small { margin-left: 5px; color: var(--color-muted-text); }.track { position: relative; height: 8px; margin-top: 5px; border-radius: 999px; background: var(--color-muted); }.track i { display: block; height: 100%; border-radius: inherit; background: #8fd3f4; }.track em { position: absolute; top: -3px; width: 2px; height: 14px; background: var(--color-primary); transform: translateX(-1px); }@media(max-width:800px){.axes{grid-template-columns:1fr}}
</style>
