<template>
  <section class="pitch-replay-panel" :aria-label="`${pitcherName} ${title}`" :aria-busy="loading">
    <header class="analysis-header">
      <div><span>{{ title }}</span><h3>{{ pitcherName }}</h3></div>
      <small>Game {{ gamePk }} only · {{ filteredRows.length }} pitches</small>
    </header>
    <p v-if="errorMessage" class="state-message error" role="alert">{{ errorMessage }} <button type="button" @click="loadPanel">Retry</button></p>
    <p v-else-if="loading" class="state-message" role="status">Loading pitches…</p>
    <template v-else-if="analysis">
      <div class="analysis-filters" :aria-label="`${title} filters`">
        <label>Batter Side<CheckboxDropdown v-model="filters.stand" :options="standOptions" /></label>
        <label>Count<CheckboxDropdown v-model="filters.count" :options="countOptions" /></label>
        <label>Pitch<CheckboxDropdown v-model="filters.pitch" :options="pitchOptions" /></label>
        <label>Pitch Result<CheckboxDropdown v-model="filters.pitchResult" :options="pitchResultOptions" /></label>
        <label>In Play Result<CheckboxDropdown v-model="filters.inPlayResult" :options="['Out', 'Hit', 'Error', 'Sacrifice']" /></label>
        <label>PA Result<CheckboxDropdown v-model="filters.paResult" :options="['Strikeout', 'Walk', 'Hit', 'Out', 'Error', 'Sacrifice']" /></label>
        <label>Paired Catcher<CheckboxDropdown v-model="filters.catcher" :options="catcherOptions" /></label>
        <button type="button" class="clear-button" @click="clearFilters">Clear filters</button>
      </div>
      <p class="sample-note">Historical Statcast ball-path reconstruction for this pitcher and game, not synthetic simulation, body motion capture or complete fluid physics. Pitch Out and pitchless events are excluded.</p>
      <p v-if="analysis.meta.warnings.length" class="sample-note">{{ analysis.meta.warnings.join(' ') }}</p>
      <div v-if="filteredRows.length" class="replay-layout">
        <PitchReplayChart :key="`${year}:${gamePk}:${pitcherId}`" :title="title" :year="year" :rows="filteredRows" @select-pitch="selectedPitch = $event" @open-video="openPitchVideo" />
        <aside class="analysis-summary">
          <div v-for="metric in summary" :key="metric.label"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong></div>
          <section class="selected-pitch">
            <span>Selected pitch</span><strong>{{ selectedPitchLabel }}</strong>
            <p v-if="selectedPitch">{{ selectedPitch.trajectory_status }} · Flight {{ displayNumber(selectedPitch.flight_time_seconds, 3) }} s · Closure X {{ displayNumber(selectedPitch.closure_error_x_in, 2) }}″ / Z {{ displayNumber(selectedPitch.closure_error_z_in, 2) }}″</p>
            <button v-if="selectedPitchVideoUrl" type="button" @click="openPitchVideo(selectedPitch!)">Open Video</button>
            <p v-else-if="selectedPitch">No video mapping is available for this pitch yet.</p>
          </section>
        </aside>
      </div>
      <p v-else class="state-message">{{ rows.length ? 'No pitches match these filters.' : 'No eligible pitch data is available for this pitcher and game.' }}</p>
      <section v-if="selectedPitch && filteredRows.length" class="pitch-details" aria-label="Selected pitch details">
        <h3>Selected Pitch</h3>
        <dl><div v-for="field in selectedPitchFields" :key="field.key"><dt>{{ field.label }}</dt><dd>{{ field.value }}</dd></div></dl>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import type { AnalysisResponse } from '~/types/api'
import { inGamePitchDetails, inGamePitchVideoUrl, matchesInGameFilters, type InGameFilters, type InGameRow } from '~/utils/pitcherInGame'

const props = withDefaults(defineProps<{ year: number; gamePk: number; pitcherId: number; pitcherName: string; title?: string }>(), { title: 'Pitch Replay' })
const emit = defineEmits<{ 'select-pitch': [pitch: InGameRow] }>()
const api = useApi()
const analysis = ref<AnalysisResponse | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const selectedPitch = ref<InGameRow | null>(null)
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
const summary = computed(() => [
  { label: 'Pitches', value: filteredRows.value.length },
  ...[['Supported', 'supported'], ['Limited', 'limited_trajectory'], ['Unavailable', 'unavailable']].map(([label, status]) => ({ label, value: filteredRows.value.filter(row => row.trajectory_status === status).length }))
])
const selectedPitchLabel = computed(() => selectedPitch.value ? `${selectedPitch.value.pitch_name || 'Pitch'} · ${displayNumber(selectedPitch.value.release_speed)} mph · ${selectedPitch.value.balls ?? '—'}-${selectedPitch.value.strikes ?? '—'}` : 'Select a pitch')
const selectedPitchVideoUrl = computed(() => inGamePitchVideoUrl(selectedPitch.value))
const selectedPitchFields = computed(() => inGamePitchDetails(selectedPitch.value))
function openPitchVideo(row: InGameRow) { selectedPitch.value = row; if (inGamePitchVideoUrl(row)) emit('select-pitch', row) }
function displayNumber(value: unknown, digits = 1) {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(digits) : '—'
}
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
.pitch-replay-panel { display:grid; gap:14px; min-width:0; padding:16px; background:color-mix(in srgb,var(--color-surface) 86%,var(--color-background)); }
.analysis-header { display:flex; align-items:end; justify-content:space-between; gap:12px; }
.analysis-header span { color:var(--color-primary); font-size:11px; font-weight:900; text-transform:uppercase; }
.analysis-header h3 { margin:2px 0 0; }
.analysis-header small,.sample-note,.selected-pitch p { color:var(--color-muted-text); }
.analysis-filters { display:grid; grid-template-columns:repeat(4,minmax(130px,1fr)); gap:10px; }
.analysis-filters label { display:grid; gap:5px; color:var(--color-muted-text); font-size:10px; font-weight:900; text-transform:uppercase; }
button { min-height:38px; border:1px solid var(--color-primary); border-radius:8px; padding:8px 12px; color:var(--color-on-primary); background:var(--color-primary); font:inherit; font-weight:850; cursor:pointer; }
button:focus-visible { outline:2px solid var(--color-primary); outline-offset:3px; }
.clear-button { align-self:end; }
.sample-note { margin:0; border-left:3px solid var(--color-primary); padding:8px 10px; font-size:12px; }
.replay-layout { display:grid; grid-template-columns:minmax(0,1.6fr) minmax(220px,.4fr); gap:14px; align-items:start; }
.analysis-summary { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.analysis-summary>div,.selected-pitch { display:grid; gap:3px; border:1px solid var(--color-border); border-radius:10px; padding:12px; background:var(--color-surface); }
.analysis-summary span { color:var(--color-muted-text); font-size:10px; font-weight:850; text-transform:uppercase; }
.analysis-summary strong { font-size:21px; }
.selected-pitch { grid-column:1/-1; }
.selected-pitch p { margin:0; font-size:12px; }
.selected-pitch button { margin-top:7px; }
.pitch-details { border:1px solid var(--color-border); border-radius:10px; padding:14px; background:var(--color-surface); }
.pitch-details h3 { margin:0 0 12px; }
.pitch-details dl { display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:12px; margin:0; }
.pitch-details dt { color:var(--color-muted-text); font-size:11px; }
.pitch-details dd { margin:4px 0 0; overflow-wrap:anywhere; font-variant-numeric:tabular-nums; }
.state-message { margin:0; border:1px dashed var(--color-border); border-radius:8px; padding:12px; color:var(--color-muted-text); }
.error { border-color:#ef4444; color:#ef4444; }
@media(max-width:980px) { .analysis-filters { grid-template-columns:repeat(2,minmax(130px,1fr)); } .replay-layout { grid-template-columns:1fr; } }
@media(max-width:640px) { .analysis-header { align-items:start; flex-direction:column; } .analysis-filters { grid-template-columns:1fr; } .pitch-replay-panel { padding:12px; } }
</style>
