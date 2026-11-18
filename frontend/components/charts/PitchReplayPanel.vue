<template>
  <section class="pitch-replay-panel" :aria-label="`${pitcherName} ${title}`" :aria-busy="loading">
    <header class="analysis-header">
      <div><span>{{ title }}</span><h3>{{ pitcherName }}</h3></div>
      <div class="panel-actions"><small>Game {{ gamePk }} only · {{ filteredRows.length }} pitches</small><button type="button" :aria-expanded="controlsOpen" @click="controlsOpen=!controlsOpen">{{ controlsOpen ? '收合控制區' : '展開控制區' }}</button></div>
    </header>
    <p v-if="errorMessage" class="state-message error" role="alert">{{ errorMessage }} <button type="button" @click="loadPanel">Retry</button></p>
    <p v-else-if="loading" class="state-message" role="status">Loading pitches…</p>
    <template v-else-if="analysis">
      <div v-show="controlsOpen" class="analysis-filters" :aria-label="`${title} filters`">
        <label>Batter Side<CheckboxDropdown v-model="filters.stand" :options="standOptions" /></label>
        <label>Count<CheckboxDropdown v-model="filters.count" :options="countOptions" /></label>
        <label>Pitch<CheckboxDropdown v-model="filters.pitch" :options="pitchOptions" /></label>
        <label>Pitch Result<CheckboxDropdown v-model="filters.pitchResult" :options="pitchResultOptions" /></label>
        <label>In Play Result<CheckboxDropdown v-model="filters.inPlayResult" :options="['Out', 'Hit', 'Error', 'Sacrifice']" /></label>
        <label>PA Result<CheckboxDropdown v-model="filters.paResult" :options="['Strikeout', 'Walk', 'Hit', 'Out', 'Error', 'Sacrifice']" /></label>
        <label>Paired Catcher<CheckboxDropdown v-model="filters.catcher" :options="catcherOptions" /></label>
        <button type="button" class="clear-button" @click="clearFilters">Clear filters</button>
      </div>
      <div v-if="filteredRows.length" class="replay-layout">
        <div class="replay-main">
          <PitchReplayChart :key="`${year}:${gamePk}:${pitcherId}`" :title="title" :year="year" :rows="filteredRows" :all-rows="rows" :controls-open="controlsOpen" @select-pitch="selectedPitch = $event" @open-video="openPitchVideo" />
        </div>
        <aside class="analysis-summary">
          <InGameMatchupCards v-if="selectedPitch && validCount" class="sidebar-matchup" :year="year" :pitcher-id="pitcherId" :batter-id="Number(selectedPitch.batter)" :pitcher-name="pitcherName" :batter-name="String(selectedPitch.batter_name||'')" :batter-side="String(selectedPitch.stand||'')" :pitcher-hand="String(selectedPitch.p_throws||'')" :balls="Number(selectedPitch.balls)" :strikes="Number(selectedPitch.strikes)" />
          <InGameSequence v-if="selectedPitch" :year="year" :pitcher-id="pitcherId" :rows="rows" :selected="selectedPitch" />
        </aside>
      </div>
      <p v-else class="state-message">{{ rows.length ? 'No pitches match these filters.' : 'No eligible pitch data is available for this pitcher and game.' }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import InGameSequence from './InGameSequence.vue'
import type { AnalysisResponse } from '~/types/api'
import { inGamePitchVideoUrl, matchesInGameFilters, type InGameFilters, type InGameRow } from '~/utils/pitcherInGame'

const props = withDefaults(defineProps<{ year: number; gamePk: number; pitcherId: number; pitcherName: string; title?: string }>(), { title: 'Pitch Replay' })
const emit = defineEmits<{ 'select-pitch': [pitch: InGameRow] }>()
const api = useApi()
const analysis = ref<AnalysisResponse | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const selectedPitch = ref<InGameRow | null>(null)
const controlsOpen=ref(true)
const filters = reactive<InGameFilters>({ stand: 'All', count: 'All', pitch: 'All', pitchResult: 'All', inPlayResult: 'All', paResult: 'All', catcher: 'All' })
let requestVersion = 0
const standOptions = [{ value: 'L', label: 'LHH' }, { value: 'R', label: 'RHH' }]
const countOptions = ['0-0', '0-1', '0-2', '1-0', '1-1', '1-2', '2-0', '2-1', '2-2', '3-0', '3-1', '3-2', 'Pitcher Ahead', 'Hitter Ahead', 'Two Strikes']
const pitchResultOptions = ['Called Strike', 'Whiff', 'Foul', 'In Play', 'Ball']
const rows = computed<InGameRow[]>(() => Array.isArray(analysis.value?.charts.pitch_replay) ? analysis.value!.charts.pitch_replay as InGameRow[] : [])
const filteredRows = computed(() => rows.value.filter(row => matchesInGameFilters(row, filters)))
const pitchOptions = computed(() => [...new Set(rows.value.map(row => String(row.pitch_name || '')).filter(Boolean))].sort())
const catcherOptions = computed(() => [...new Set([
  ...(Array.isArray(analysis.value?.charts.catcher_options) ? analysis.value!.charts.catcher_options as string[] : []),
  ...rows.value.map(row => String(row.catcher_name || '')).filter(Boolean)
])].sort())
const validCount=computed(()=>selectedPitch.value?.balls!=null&&selectedPitch.value?.strikes!=null&&Number(selectedPitch.value.balls)>=0&&Number(selectedPitch.value.balls)<=3&&Number(selectedPitch.value.strikes)>=0&&Number(selectedPitch.value.strikes)<=2&&Number(selectedPitch.value.batter)>0)
function openPitchVideo(row: InGameRow) { if (inGamePitchVideoUrl(row)) emit('select-pitch', row) }
function clearFilters() { for (const key of Object.keys(filters) as Array<keyof InGameFilters>) filters[key] = 'All' }
async function loadPanel() {
  const version = ++requestVersion
  analysis.value = null
  selectedPitch.value = null
  errorMessage.value = ''
  loading.value = true
  try {
    const result = await api.gamePitcherReplay({ year: props.year, gamePk: props.gamePk, pitcherId: props.pitcherId })
    if (version === requestVersion) analysis.value = result
  } catch (error) {
    if (version === requestVersion) errorMessage.value = error instanceof Error ? error.message : 'Pitch data request failed'
  } finally {
    if (version === requestVersion) loading.value = false
  }
}
watch(() => [props.year, props.gamePk, props.pitcherId], () => { clearFilters(); void loadPanel() }, { immediate: true })
watch(filteredRows, rows => { if (selectedPitch.value && !rows.includes(selectedPitch.value)) selectedPitch.value = null })
onBeforeUnmount(() => { requestVersion += 1 })
</script>

<style scoped>
.pitch-replay-panel { display:grid; grid-template-columns:minmax(0,1fr) minmax(290px,340px); gap:14px; align-items:start; min-width:0; padding:16px; background:color-mix(in srgb,var(--color-surface) 86%,var(--color-background)); }
.analysis-header { grid-column:1; grid-row:1; display:flex; align-items:end; justify-content:space-between; gap:12px; }
.analysis-header span { color:var(--color-primary); font-size:11px; font-weight:900; text-transform:uppercase; }
.analysis-header h3 { margin:2px 0 0; }
.panel-actions{display:flex;align-items:center;justify-content:end;gap:8px;flex-wrap:wrap}.panel-actions button{font-size:12px;min-height:30px;padding:5px 9px}
.analysis-header small,.sample-note,.selected-pitch p { color:var(--color-muted-text); }
.analysis-filters { grid-column:1; grid-row:2; min-width:0; display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }
.analysis-filters label { display:grid; gap:5px; color:var(--color-muted-text); font-size:10px; font-weight:900; text-transform:uppercase; }
button { min-height:38px; border:1px solid var(--color-primary); border-radius:8px; padding:8px 12px; color:var(--color-on-primary); background:var(--color-primary); font:inherit; font-weight:850; cursor:pointer; }
button:focus-visible { outline:2px solid var(--color-primary); outline-offset:3px; }
.clear-button { align-self:end; }
.sample-note { margin:0; border-left:3px solid var(--color-primary); padding:8px 10px; font-size:12px; }
.replay-layout { display:contents; }
.replay-main { grid-column:1; grid-row:3; min-width:0; }
.analysis-summary { grid-column:2; grid-row:1 / span 3; display:grid; grid-template-columns:minmax(0,1fr); gap:12px; min-width:0; }
.analysis-summary>div,.selected-pitch { display:grid; gap:3px; border:1px solid var(--color-border); border-radius:10px; padding:12px; background:var(--color-surface); }
.analysis-summary span { color:var(--color-muted-text); font-size:10px; font-weight:850; text-transform:uppercase; }
.analysis-summary strong { font-size:21px; }
.selected-pitch { grid-column:1/-1; }
.sidebar-matchup{grid-column:1/-1}
.selected-pitch p { margin:0; font-size:12px; }
.selected-pitch button { margin-top:7px; }
.pitch-details { border:1px solid var(--color-border); border-radius:10px; padding:14px; background:var(--color-surface); }
.pitch-details h3 { margin:0 0 12px; }
.pitch-details dl { display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:12px; margin:0; }
.pitch-details dt { color:var(--color-muted-text); font-size:11px; }
.pitch-details dd { margin:4px 0 0; overflow-wrap:anywhere; font-variant-numeric:tabular-nums; }
.state-message { grid-column:1/-1; margin:0; border:1px dashed var(--color-border); border-radius:8px; padding:12px; color:var(--color-muted-text); }
.error { border-color:#ef4444; color:#ef4444; }
@media(max-width:980px) { .pitch-replay-panel { grid-template-columns:minmax(0,1fr); } .analysis-filters { grid-template-columns:repeat(2,minmax(0,1fr)); } .analysis-summary { grid-column:1; grid-row:4; } }
@media(max-width:640px) { .analysis-header { align-items:start; flex-direction:column; } .analysis-filters { grid-template-columns:1fr; } .pitch-replay-panel { padding:12px; } }
</style>
