<template>
  <section class="intel-card pitch-matrix">
    <header>
      <div><span class="eyebrow">PITCH-FAMILY MATCHUP MATRIX</span><h3>Which shapes stress the lineup?</h3></div>
      <div class="metric-toggle" aria-label="Matrix metric">
        <button v-for="option in metrics" :key="option.key" type="button" :class="{ active: metric === option.key }" @click="metric = option.key">{{ option.short }}</button>
      </div>
    </header>
    <p class="deck">顏色相對該球種群組的 MLB 平均：暖色較好、冷色較差。RV/100 是有 bat tracking 揮棒的實際 run value，未做環境校正。</p>
    <div class="matrix-scroll">
      <table>
        <thead><tr><th>Hitter</th><th v-for="family in families" :key="family.family">{{ family.label }}<small>MLB {{ displayValue(family.league) }}</small></th></tr></thead>
        <tbody>
          <tr v-for="row in lineup" :key="row.batter_id">
            <th><NuxtLink :to="playerLink(row.batter_id)"><MlbPlayerHeadshot :player-id="row.batter_id" :name="row.name" :size="32" shape="circle" decorative /><span>{{ row.name }}<small>{{ row.swings }} swings</small></span></NuxtLink></th>
            <td v-for="family in families" :key="`${row.batter_id}-${family.family}`" :style="cellStyle(family, row.batter_id)">
              <strong>{{ displayValue(findHitter(family, row.batter_id)) }}</strong><small>{{ findHitter(family, row.batter_id)?.swings || 0 }} swings</small>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { TeamHitterIntelligenceRow, TeamHittingProfile, TeamPitchFamilyHitter, TeamPitchFamilyProfile } from '~/types/api'
type MetricKey = 'perfect_pct' | 'on_time_pct' | 'whiff_pct' | 'miss_distance' | 'run_value_per_100_swings'
const props = defineProps<{ families: TeamPitchFamilyProfile[]; lineup: TeamHitterIntelligenceRow[]; teamId: string; year: number }>()
const metric = ref<MetricKey>('perfect_pct')
const metrics: { key: MetricKey; short: string }[] = [{ key: 'perfect_pct', short: 'Perfect' }, { key: 'on_time_pct', short: 'On Time' }, { key: 'whiff_pct', short: 'Whiff' }, { key: 'miss_distance', short: 'Miss' }, { key: 'run_value_per_100_swings', short: 'RV/100' }]
const families = computed(() => props.families)
const findHitter = (family: TeamPitchFamilyProfile, id: number) => family.hitters.find(row => row.batter_id === id)
const metricValue = (row: TeamPitchFamilyHitter | TeamHittingProfile | undefined) => row ? Number(row[metric.value]) : null
function displayValue(row: TeamPitchFamilyHitter | TeamHittingProfile | undefined) {
  const value = metricValue(row); if (value == null || !Number.isFinite(value)) return '—'
  if (metric.value === 'miss_distance') return `${value.toFixed(1)} in`
  if (metric.value === 'run_value_per_100_swings') return `${value >= 0 ? '+' : ''}${value.toFixed(1)}`
  return `${value.toFixed(1)}%`
}
function cellStyle(family: TeamPitchFamilyProfile, id: number) {
  const actual = metricValue(findHitter(family, id)); const baseline = metricValue(family.league)
  if (actual == null || baseline == null) return {}
  const lowerIsBetter = metric.value === 'whiff_pct' || metric.value === 'miss_distance'
  const rawDifference = (actual - baseline) * (lowerIsBetter ? -1 : 1)
  const scale = metric.value === 'run_value_per_100_swings' ? 6 : metric.value === 'miss_distance' ? 2 : 12
  const strength = Math.min(.68, .14 + Math.abs(rawDifference) / scale * .54)
  return { background: rawDifference >= 0 ? `rgba(185, 67, 59, ${strength})` : `rgba(74, 126, 176, ${strength})` }
}
const playerLink = (batterId: number) => ({ path: '/batter-personal', query: { year: props.year, team: props.teamId, batter_id: batterId } })
</script>

<style scoped>
.intel-card { min-width: 0; overflow: hidden; border: 1px solid var(--team-panel-border); border-radius: 16px; background: var(--team-panel-bg); } header { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; padding: 22px 22px 0; } h3 { margin: 5px 0 0; color: var(--color-text); font-size: clamp(21px,2vw,30px); }.eyebrow { color: var(--team-accent); font-size: 11px; font-weight: 900; letter-spacing: .12em; }.deck { margin: 8px 22px 18px; color: var(--color-muted-text); font-size: 13px; line-height: 1.6; }.metric-toggle { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 4px; }.metric-toggle button { min-height: 34px; border: 1px solid var(--team-panel-border); border-radius: 8px; padding: 6px 9px; color: var(--color-muted-text); background: var(--color-background); font-size: 10px; font-weight: 850; cursor: pointer; }.metric-toggle button.active { color: #fff; border-color: var(--team-primary); background: var(--team-primary); }.matrix-scroll { max-width: 100%; overflow-x: auto; } table { width: 100%; min-width: 720px; table-layout: fixed; border-collapse: collapse; } th,td { border-top: 1px solid var(--team-panel-border); padding: 12px 10px; text-align: center; } thead th { color: var(--color-muted-text); background: color-mix(in srgb,var(--color-background) 75%,transparent); font-size: 11px; letter-spacing: .04em; } thead th:first-child,tbody th { width: 31%; text-align: left; } th small,td small { display: block; margin-top: 3px; color: var(--color-muted-text); font-size: 9px; font-weight: 650; } tbody th a { min-width: 0; display: flex; align-items: center; gap: 9px; color: var(--color-text); font-size: 12px; text-decoration: none; } tbody th a span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } td { color: var(--color-text); } td strong { font-size: 13px; }
@media(max-width:760px){header{flex-direction:column}.metric-toggle{justify-content:flex-start}}
</style>
