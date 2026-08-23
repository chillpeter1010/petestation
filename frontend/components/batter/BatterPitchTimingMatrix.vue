<template>
  <section class="matrix">
    <header><span>V2.3 · Pitch matrix</span><h4>Which pitch shapes break the alignment?</h4></header>
    <div class="scroll"><table><thead><tr><th>Pitch</th><th>Swings</th><th>Miss</th><th>Flawed</th><th>Perfect</th><th>Centered</th><th>On Time</th><th>Lined Up</th><th>Whiff</th></tr></thead><tbody><tr v-for="row in rows" :key="row.pitch_type"><td><b>{{ row.pitch_label }}</b><small>{{ row.pitch_type }}</small></td><td>{{ row.n_swings }}</td><td>{{ num(row.miss_distance, ' in') }}</td><td>{{ pct(row.flawed_pct) }}</td><td>{{ pct(row.perfect_pct) }}</td><td>{{ pct(row.centered_pct) }}</td><td>{{ pct(row.on_time_pct) }}</td><td>{{ pct(row.lined_up_pct) }}</td><td>{{ pct(row.whiff_pct) }}</td></tr></tbody></table></div>
    <p v-if="!rows.length">No pitch-level profile matches this selection.</p>
  </section>
</template>
<script setup lang="ts">
import type { SwingTimingPitchProfile } from '~/types/api'
defineProps<{ rows: SwingTimingPitchProfile[] }>()
function pct(value: number | null) { return value == null ? '—' : `${value.toFixed(1)}%` }
function num(value: number | null, suffix = '') { return value == null ? '—' : `${value.toFixed(1)}${suffix}` }
</script>
<style scoped>
.matrix { margin-top: 12px; border: 1px solid var(--color-border); border-radius: 14px; padding: 16px; background: var(--color-surface); }.matrix header span { color: var(--color-primary); font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }.matrix h4 { margin: 3px 0 12px; font-size: 17px; }.scroll { overflow-x: auto; }.matrix table { width: 100%; min-width: 850px; border-collapse: collapse; }.matrix th,.matrix td { border-bottom: 1px solid var(--color-border); padding: 8px; text-align: right; font-size: 10px; }.matrix th:first-child,.matrix td:first-child { text-align: left; }.matrix td:first-child small { display: block; color: var(--color-muted-text); }.matrix p { color: var(--color-muted-text); font-size: 11px; }
</style>
