<template>
  <details class="intel-card pitch-matrix">
    <summary>
      <div><span class="eyebrow">PITCH-FAMILY MATCHUP MATRIX</span><h3>Which shapes stress the lineup?</h3><p>點擊表頭展開球種群組對戰矩陣</p></div>
      <span class="expand-label"><span class="open-copy">Collapse</span><span class="closed-copy">Expand</span><ChevronDown :size="19" aria-hidden="true" /></span>
    </summary>
    <div class="matrix-body">
      <div class="matrix-intro">
        <div><p class="deck">顏色相對該球種群組的 MLB 平均：紅色較好、白色接近平均、藍色較差。RV/100 是有 bat tracking 揮棒的實際 run value，未做環境校正。</p><div class="color-legend" aria-label="Performance color scale"><span v-for="stop in colorLegend" :key="stop.score" :style="performanceColorStyle(stop.score)">{{ stop.label }}</span></div></div>
        <div class="metric-toggle" aria-label="Matrix metric">
          <button v-for="option in metrics" :key="option.key" type="button" :class="{ active: metric === option.key }" @click="metric = option.key">{{ option.short }}</button>
        </div>
      </div>
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
    </div>
  </details>
</template>

<script setup lang="ts">
import { ChevronDown } from '@lucide/vue'
import type { TeamHitterIntelligenceRow, TeamHittingProfile, TeamPitchFamilyHitter, TeamPitchFamilyProfile } from '~/types/api'
import { performanceColorStyle } from '~/utils/performanceColor'
type MetricKey = 'perfect_pct' | 'on_time_pct' | 'whiff_pct' | 'miss_distance' | 'run_value_per_100_swings'
const props = defineProps<{ families: TeamPitchFamilyProfile[]; lineup: TeamHitterIntelligenceRow[]; teamId: string; year: number }>()
const metric = ref<MetricKey>('perfect_pct')
const metrics: { key: MetricKey; short: string }[] = [{ key: 'perfect_pct', short: 'Perfect' }, { key: 'on_time_pct', short: 'On Time' }, { key: 'whiff_pct', short: 'Whiff' }, { key: 'miss_distance', short: 'Miss' }, { key: 'run_value_per_100_swings', short: 'RV/100' }]
const colorLegend = [{ label: 'Better', score: 1 }, { label: '', score: .66 }, { label: '', score: .33 }, { label: 'Average', score: 0 }, { label: '', score: -.33 }, { label: '', score: -.66 }, { label: 'Worse', score: -1 }]
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
  return performanceColorStyle(rawDifference / scale)
}
const playerLink = (batterId: number) => ({ path: '/batter-personal', query: { year: props.year, team: props.teamId, batter_id: batterId } })
</script>

<style scoped>
.intel-card{min-width:0;overflow:hidden;border:1px solid var(--team-panel-border);border-radius:16px;background:var(--team-panel-bg)}summary{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:22px;cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}summary h3{margin:5px 0 0;color:var(--color-text);font-size:clamp(21px,2vw,30px)}summary p{margin:5px 0 0;color:var(--color-muted-text);font-size:12px}.eyebrow{color:var(--team-accent);font-size:11px;font-weight:900;letter-spacing:.12em}.expand-label{display:inline-flex;align-items:center;gap:8px;color:var(--team-accent);font-size:11px;font-weight:850;text-transform:uppercase}.expand-label svg{transition:transform .18s ease}.pitch-matrix[open] .expand-label svg{transform:rotate(180deg)}.open-copy,.pitch-matrix[open] .closed-copy{display:none}.pitch-matrix[open] .open-copy{display:inline}.matrix-body{border-top:1px solid var(--team-panel-border)}.matrix-intro{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:18px 22px}.deck{max-width:820px;margin:0;color:var(--color-muted-text);font-size:13px;line-height:1.6}.color-legend{display:grid;grid-template-columns:repeat(7,minmax(42px,72px));margin-top:11px}.color-legend span{min-height:22px;display:grid;place-items:center;font-size:8px;font-weight:850;text-transform:uppercase}.metric-toggle{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:4px}.metric-toggle button{min-height:34px;border:1px solid var(--team-panel-border);border-radius:8px;padding:6px 9px;color:var(--color-muted-text);background:var(--color-background);font-size:10px;font-weight:850;cursor:pointer}.metric-toggle button.active{color:#fff;border-color:var(--team-primary);background:var(--team-primary)}.matrix-scroll{max-width:100%;overflow-x:auto}table{width:100%;min-width:720px;table-layout:fixed;border-collapse:collapse}th,td{border-top:1px solid var(--team-panel-border);padding:12px 10px;text-align:center}thead th{color:var(--color-muted-text);background:color-mix(in srgb,var(--color-background) 75%,transparent);font-size:11px;letter-spacing:.04em}thead th:first-child,tbody th{width:31%;text-align:left}th small,td small{display:block;margin-top:3px;color:inherit;opacity:.76;font-size:9px;font-weight:650}tbody th a{min-width:0;display:flex;align-items:center;gap:9px;color:var(--color-text);font-size:12px;text-decoration:none}tbody th a span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}td strong{font-size:13px}@media(max-width:760px){.matrix-intro{align-items:flex-start;flex-direction:column}.metric-toggle{justify-content:flex-start}}
</style>
