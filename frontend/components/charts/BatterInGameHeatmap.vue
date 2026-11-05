<template>
  <section class="batter-heatmap" aria-label="Season batter zone rates">
    <header><strong>Batter zone rates · <NuxtLink :to="{path:'/batter-personal',query:{year,batter_id:batterId}}">{{ batterName || 'Batter name unavailable' }}</NuxtLink></strong><label><input v-model="enabled" type="checkbox"> Show heatmap</label></header>
    <div class="heatmap-controls">
      <label><span>Outside zones</span><input v-model="showOutside" type="checkbox" aria-label="Show grouped outside zones"></label>
      <label>Pitcher hand<select v-model="hand"><option disabled value="">Select hand</option><option value="R">vs RHP</option><option value="L">vs LHP</option><option value="All">All hands</option></select></label>
      <label>Metric<select v-model="metric"><option v-for="item in data?.metrics || []" :key="item.key" :value="item.key">{{ item.label }}</option></select></label>
      <button v-if="error" type="button" @click="load(true)">Retry</button>
    </div>
    <p v-if="!hand">Pitcher hand is unknown. Select a hand to view season data.</p>
    <p v-else-if="loading" role="status">Loading batter zone rates…</p>
    <p v-else-if="error" role="alert">Batter zone rates could not load. The original replay remains available.</p>
    <template v-else-if="data">
      <details class="heatmap-notes"><summary>Heatmap guide / samples / color reference</summary>
      <p>{{ year }} regular season · {{ data.season_pa }} total PA · {{ data.split_pitches }} pitches in hand split. Eligibility: total season PA &gt; 30.</p>
      <p v-if="!data.eligible">{{ data.status === 'unavailable' ? 'Season source unavailable.' : 'No heatmap: at least 31 completed season PA are required.' }}</p>
      <p v-else-if="data.status !== 'ready'">No located pitches for this hand split.</p>
      <template v-else>
        <p>{{ selectedMetric?.denominator }} · {{ data.missing_location_pitches }} missing locations · {{ data.zone_height_fallback_pitches }} zone-height fallbacks. Zone: 17-inch plate, normalized recorded height.</p>
        <p class="legend"><i /> PR 0 → 50 → 100 · {{ selectedMetric?.direction === 'lower' ? 'Lower raw value favors the batter (reversed PR).' : selectedMetric?.direction === 'higher' ? 'Higher raw value favors the batter.' : 'Frequency percentile only; higher/lower is not a skill grade.' }}</p>
        <p v-if="data.benchmark_status !== 'ready'">League PR baseline {{ data.benchmark_status || 'unavailable' }}. Raw values remain below; no absolute-scale fallback colors.</p>
        <p>Same season, pitcher hand, zone and metric. Peers: season PA &gt; 30 and cell denominator ≥10; at least 5 peers. PR50 is the peer median, not necessarily the weighted league average.</p>
        <p>Contours interpolate PR for display. Outside groups appear as a narrow fading halo, not pitch-level density. Exact values and league averages remain below; low-sample/no-reference areas stay unpainted.</p>
        <p v-if="metric === 'avg' || metric === 'woba'">PA results use only the final pitch's location, not every pitch in that PA. Missing wOBA values are excluded, never filled with zero.</p>
        <details><summary>Zone values and sample sizes</summary>
          <p>Rows run top to bottom. Outside regions group all pitches beyond the zone. — = missing, not applicable, insufficient sample or insufficient peers. PR uses midrank ties; equal peer values are neutral.</p>
          <table><thead><tr><th>Region</th><th>{{ selectedMetric?.label }}</th><th>Qualified league avg</th><th>Color PR</th><th>Peers</th><th>Numerator / denominator</th></tr></thead>
            <tbody><tr v-for="cell in displayCells" :key="cell.id"><th>{{ cell.label }}</th><td>{{ formatZoneRate(cell.rates[metric]?.value, metric) }}</td><td>{{ formatZoneRate(cell.rates[metric]?.league_average, metric) }}</td><td>{{ cell.rates[metric]?.color_pr == null ? '—' : cell.rates[metric].color_pr!.toFixed(0) }}</td><td>{{ cell.rates[metric]?.peer_count ?? 0 }}</td><td>{{ Number((cell.rates[metric]?.numerator ?? 0).toFixed(3)) }} / {{ Number((cell.rates[metric]?.denominator ?? 0).toFixed(3)) }}</td></tr></tbody>
          </table>
        </details>
      </template>
      </details>
    </template>
  </section>
</template>

<script setup lang="ts">
import type { BatterZoneRatesResponse } from '~/types/api'
import type { BatterHeatmapOverlay } from '~/utils/batterZoneRates'
import { formatZoneRate } from '~/utils/batterZoneRates'

const props = defineProps<{ year: number; batterId: number; batterName?: string; pitcherId: number; pitcherHand: string }>()
const emit = defineEmits<{ overlay: [value: BatterHeatmapOverlay | null] }>()
const api = useApi()
const enabled = ref(true), hand = ref<'' | 'All' | 'L' | 'R'>(''), metric = ref('swing')
const showOutside = ref(false)
const data = ref<BatterZoneRatesResponse | null>(null), loading = ref(false), error = ref(false)
const cache = new Map<string, { at: number; data: BatterZoneRatesResponse }>()
let version = 0
const selectedMetric = computed(() => data.value?.metrics.find(m => m.key === metric.value))
const displayCells = computed(() => [...(data.value?.cells || [])].sort((a, b) => a.region.localeCompare(b.region) || b.bounds[1] - a.bounds[1] || a.bounds[0] - b.bounds[0]))
watch(() => [props.year, props.batterId, props.pitcherId, props.pitcherHand], () => {
  hand.value = props.pitcherHand === 'R' || props.pitcherHand === 'L' ? props.pitcherHand : ''
}, { immediate: true })
async function load(retry = false) {
  const token = ++version
  data.value = null; error.value = false; loading.value = false
  if (!hand.value || !enabled.value) return
  const key = `${props.year}:${props.batterId}:${hand.value}`
  const cached = cache.get(key)
  if (!retry && cached && Date.now() - cached.at < 120_000) { data.value = cached.data; return }
  loading.value = true
  try {
    const result = await api.batterZoneRates({ year: props.year, batterId: props.batterId, pitcherHand: hand.value })
    if (token !== version) return
    data.value = result
    if (cache.size >= 32) cache.delete(cache.keys().next().value!)
    cache.set(key, { at: Date.now(), data: result })
  } catch { if (token === version) error.value = true }
  finally { if (token === version) loading.value = false }
}
watch(() => [props.year, props.batterId, props.pitcherId, hand.value, enabled.value], () => void load(), { immediate: true })
watch(metric, value => { if (value.startsWith('o_')) showOutside.value = true })
watch([data, metric, enabled, showOutside], () => emit('overlay', enabled.value && data.value?.status === 'ready' ? { data: { ...data.value, cells: data.value.cells.filter(cell => showOutside.value || cell.region === 'zone') }, metric: metric.value, context: `${props.year}:${props.batterId}:${props.pitcherId}:${props.pitcherHand}` } : null), { immediate: true })
onBeforeUnmount(() => { version += 1; emit('overlay', null) })
</script>

<style scoped>
.batter-heatmap{display:grid;gap:9px;margin-top:12px;padding:12px;border:1px solid var(--color-border);border-radius:8px;background:var(--color-surface)}
header,.heatmap-controls{display:flex;flex-wrap:wrap;align-items:center;gap:12px;justify-content:space-between}
.heatmap-controls{justify-content:flex-start}.heatmap-controls label{display:grid;gap:4px}select,button{padding:7px;color:var(--color-foreground);background:var(--color-plot-bg);border:1px solid var(--color-border);border-radius:5px}
p{margin:0;color:var(--color-muted-text);font-size:12px}.legend{display:flex;align-items:center;gap:8px}.legend i{width:100px;height:10px;flex-shrink:0;background:linear-gradient(90deg,#0050ff,#fafaff 50%,#ff142d)}
details{overflow-x:auto}summary{cursor:pointer}table{width:100%;font-size:12px;text-align:left;border-collapse:collapse}th,td{padding:6px;border-bottom:1px solid var(--color-border);font-variant-numeric:tabular-nums}
</style>
