<template>
  <section class="gear">
    <header><span>V2.4 · Bat-speed gear change</span><h4>Does the hitter add or subtract speed by pitch type?</h4><p>條件棒速減去該打者該季 competitive swing 平均；不是反應時間的直接測量。</p></header>
    <div class="gear-grid"><article v-for="row in rows" :key="row.pitch_type"><div><b>{{ row.pitch_label }}</b><span>{{ signed(row.bat_speed_delta) }}</span></div><div class="delta"><i :class="{ negative: (row.bat_speed_delta || 0) < 0 }" :style="bar(row.bat_speed_delta)" /></div><footer><span>{{ num(row.avg_bat_speed) }} mph</span><span>Fast {{ pct(row.fast_swing_pct) }}</span><span>{{ row.n_swings }} swings</span></footer></article></div>
    <p v-if="!rows.some(row => row.bat_speed_delta != null)">This selection has no pitch-level Bat Tracking values.</p>
  </section>
</template>
<script setup lang="ts">
import type { SwingTimingPitchProfile } from '~/types/api'
defineProps<{ rows: SwingTimingPitchProfile[] }>()
function signed(value: number | null) { return value == null ? '—' : `${value >= 0 ? '+' : ''}${value.toFixed(1)} mph` }
function num(value: number | null) { return value == null ? '—' : value.toFixed(1) }
function pct(value: number | null) { return value == null ? '—' : `${value.toFixed(1)}%` }
function bar(value: number | null) { const width = Math.min(50, Math.abs(value || 0) * 12.5); return { width: `${width}%`, left: (value || 0) < 0 ? `${50 - width}%` : '50%' } }
</script>
<style scoped>
.gear { margin-top: 12px; border: 1px solid var(--color-border); border-radius: 14px; padding: 16px; background: var(--color-surface); }.gear header span { color: var(--color-primary); font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }.gear h4 { margin: 3px 0 2px; font-size: 17px; }.gear header p,.gear > p { margin: 0; color: var(--color-muted-text); font-size: 10px; }.gear-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 9px; margin-top: 13px; }.gear article { border: 1px solid var(--color-border); border-radius: 10px; padding: 11px; }.gear article > div:first-child,.gear footer { display: flex; justify-content: space-between; gap: 8px; font-size: 10px; }.gear article > div:first-child span { color: var(--color-primary); font-weight: 900; }.delta { position: relative; height: 8px; margin: 9px 0; border-radius: 999px; background: linear-gradient(90deg,var(--color-muted) 49.5%,var(--color-border) 49.5%,var(--color-border) 50.5%,var(--color-muted) 50.5%); }.delta i { position: absolute; height: 100%; border-radius: 999px; background: #5ab3d7; }.delta i.negative { background: var(--color-destructive); }.gear footer { color: var(--color-muted-text); }@media(max-width:1100px){.gear-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.gear-grid{grid-template-columns:1fr}}
</style>
