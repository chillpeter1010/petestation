<template>
  <section class="game-analysis" :aria-label="`${pitcherName} ${mode} analysis`">
    <header class="analysis-header">
      <div>
        <span>{{ modeLabel }}</span>
        <h3>{{ pitcherName }}</h3>
      </div>
      <small>Game {{ gamePk }} only · {{ filteredPitchCount }} pitches</small>
    </header>

    <p v-if="errorMessage" class="state-message error" role="alert">{{ errorMessage }}</p>
    <p v-else-if="loading && !analysis" class="state-message">Loading {{ modeLabel }}…</p>

    <template v-if="mode === 'location'">
      <div class="analysis-filters" aria-label="Location filters">
        <label>Batter Side<CheckboxDropdown v-model="stand" :options="standOptions" /></label>
        <label>Count<CheckboxDropdown v-model="count" :options="countOptions" /></label>
        <label>Pitch<CheckboxDropdown v-model="pitch" :options="pitchOptions" /></label>
        <label>Pitch Result<CheckboxDropdown v-model="pitchResult" :options="pitchResultOptions" /></label>
        <label>In Play Result<CheckboxDropdown v-model="inPlayResult" :options="inPlayResultOptions" /></label>
        <label>PA Result<CheckboxDropdown v-model="paResult" :options="paResultOptions" /></label>
        <label>Paired Catcher<CheckboxDropdown v-model="catcher" :options="catcherOptions" /></label>
        <button type="button" class="clear-button" @click="clearFilters">Clear filters</button>
      </div>
      <div v-if="analysis" class="location-layout" :aria-busy="loading">
        <StrikeZoneScatter
          title="Game Pitch Locations"
          :points="locationPoints"
          :total-pitches="filteredPitchCount"
          :selected-key="selectedPitchKey"
          :heatmap-blend="0"
          @select-point="selectPitch"
        />
        <aside class="analysis-summary">
          <div v-for="metric in summaryMetrics" :key="metric.label">
            <span>{{ metric.label }}</span><strong>{{ metric.value }}</strong>
          </div>
          <section class="selected-pitch">
            <span>Selected pitch</span>
            <strong>{{ selectedPitchLabel }}</strong>
            <p v-if="selectedPitch">Stuff+ {{ displayNumber(selectedPitch.pitch_stuff_plus) }} · Location+ {{ displayNumber(selectedPitch.location_plus_pitch) }} · Stamina+ {{ displayNumber(selectedPitch.stamina_plus_trait) }}</p>
            <button v-if="selectedPitchVideoUrl" type="button" @click="emit('select-pitch', selectedPitch!)">Open Savant video</button>
          </section>
        </aside>
      </div>
      <p v-if="analysis && !locationPoints.length" class="state-message">No pitches match these filters.</p>
    </template>

    <template v-else-if="mode === 'sequence'">
      <div class="analysis-filters" aria-label="Sequence filters">
        <label>Batter Side<CheckboxDropdown v-model="stand" :options="standOptions" /></label>
        <label>Count<CheckboxDropdown v-model="count" :options="countOptions" /></label>
        <label>Pitch<CheckboxDropdown v-model="pitch" :options="pitchOptions" /></label>
        <label>Pitch Result<CheckboxDropdown v-model="pitchResult" :options="pitchResultOptions" /></label>
        <label>Paired Catcher<CheckboxDropdown v-model="catcher" :options="catcherOptions" /></label>
        <button type="button" class="clear-button" @click="clearFilters">Clear filters</button>
      </div>
      <div v-if="analysis" class="sequence-layout" :aria-busy="loading">
        <p class="sample-note">Descriptive single-game counts only. Sequence paths and immediate follow-ups stay inside the same plate appearance.</p>
        <SequenceOutcomeTree :rows="countPitchMixRows" :source-rows="locationPoints" @select-branch="applyBranch" />
        <section class="sequence-detail">
          <header><h4>Count detail</h4><span>Current state and immediate follow-up</span></header>
          <div class="condition-controls">
            <label>Count<select v-model="detailCount"><option v-for="option in exactCountOptions" :key="option">{{ option }}</option></select></label>
            <label>Follow-up Pitch<select v-model="followupPitch"><option value="All">All</option><option v-for="option in pitchOptionsWithoutAll" :key="option">{{ option }}</option></select></label>
          </div>
          <div class="table-grid">
            <DataTable :title="`Current Pitch | ${detailCount}`" :table="analysis.tables.count_detail_current" />
            <DataTable title="Next Count Pitch Mix" :table="analysis.tables.count_detail_next" />
          </div>
          <DataTable title="Immediate Follow-up Events" :table="analysis.tables.count_followup_events" />
        </section>
        <section class="sequence-detail">
          <header><h4>Conditioned branch</h4><span>Click a tree slice or choose a count and pitch</span></header>
          <div class="condition-controls">
            <label>Count<select v-model="conditionCount"><option v-for="option in exactCountOptions" :key="option">{{ option }}</option></select></label>
            <label>Pitch<select v-model="conditionPitch"><option value="All">All</option><option v-for="option in pitchOptionsWithoutAll" :key="option">{{ option }}</option></select></label>
          </div>
          <SequenceOutcomeTree v-if="conditionedCountPitchMixRows.length" :rows="conditionedCountPitchMixRows" :source-rows="locationPoints" />
          <p v-else class="state-message">No downstream branch matches this selection.</p>
        </section>
        <details class="sequence-tables">
          <summary>Sequence tables</summary>
          <div class="table-grid">
            <DataTable title="Shallow Count Sequences" :table="analysis.tables.shallow_sequences" />
            <DataTable title="Two-Strike Sequences" :table="analysis.tables.two_strike_sequences" />
          </div>
        </details>
      </div>
    </template>

    <template v-else-if="mode === 'movement'">
      <div class="analysis-filters" :aria-label="`${modeLabel} filters`">
        <label>Batter Side<CheckboxDropdown v-model="stand" :options="standOptions" /></label>
        <label>Count<CheckboxDropdown v-model="count" :options="countOptions" /></label>
        <label>Pitch<CheckboxDropdown v-model="pitch" :options="pitchOptions" /></label>
        <label>Pitch Result<CheckboxDropdown v-model="pitchResult" :options="pitchResultOptions" /></label>
        <label>In Play Result<CheckboxDropdown v-model="inPlayResult" :options="inPlayResultOptions" /></label>
        <label>PA Result<CheckboxDropdown v-model="paResult" :options="paResultOptions" /></label>
        <label>Paired Catcher<CheckboxDropdown v-model="catcher" :options="catcherOptions" /></label>
        <button type="button" class="clear-button" @click="clearFilters">Clear filters</button>
      </div>
      <p class="sample-note">Game {{ gamePk }} only. Filters are applied locally to the shared pitch-shape payload.</p>
      <div v-if="analysis" class="shape-layout" :aria-busy="loading">
        <MovementChart
          v-model:mode="movementChartMode"
          title="Game Movement"
          :scatter-rows="filteredMovementRows"
          :summary-rows="filteredMovementSummary"
          :allow-stuff-color="true"
          :show-profile-info="false"
          :pitcher-hand="pitcherHand"
          :selected-key="movementSelectedKey"
          @select-point="selectPitch"
        />
        <aside class="analysis-summary">
          <div v-for="metric in shapeSummaryMetrics" :key="metric.label">
            <span>{{ metric.label }}</span><strong>{{ metric.value }}</strong>
          </div>
          <section class="selected-pitch">
            <span>Selected pitch</span>
            <strong>{{ selectedPitchLabel }}</strong>
            <p v-if="selectedPitch">Stuff+ {{ displayNumber(selectedPitch.pitch_stuff_plus) }} · Location+ {{ displayNumber(selectedPitch.location_plus_pitch) }} · Stamina+ {{ displayNumber(selectedPitch.stamina_plus_trait) }}</p>
            <button v-if="selectedPitchVideoUrl" type="button" @click="emit('select-pitch', selectedPitch!)">Open Savant video</button>
          </section>
        </aside>
      </div>
      <p v-if="analysis && !filteredMovementRows.length" class="state-message">No pitches with movement coordinates match these filters.</p>
    </template>

    <template v-else-if="mode === 'replay'">
      <div class="analysis-filters" aria-label="Pitch Replay filters">
        <label>Batter Side<CheckboxDropdown v-model="stand" :options="standOptions" /></label>
        <label>Count<CheckboxDropdown v-model="count" :options="countOptions" /></label>
        <label>Pitch<CheckboxDropdown v-model="pitch" :options="pitchOptions" /></label>
        <label>Pitch Result<CheckboxDropdown v-model="pitchResult" :options="pitchResultOptions" /></label>
        <label>In Play Result<CheckboxDropdown v-model="inPlayResult" :options="inPlayResultOptions" /></label>
        <label>PA Result<CheckboxDropdown v-model="paResult" :options="paResultOptions" /></label>
        <label>Paired Catcher<CheckboxDropdown v-model="catcher" :options="catcherOptions" /></label>
        <button type="button" class="clear-button" @click="clearFilters">Clear filters</button>
      </div>
      <p class="sample-note">Game {{ gamePk }} only. This is a ball-path reconstruction, not body motion capture or complete fluid physics.</p>
      <div v-if="analysis" class="replay-layout" :aria-busy="loading">
        <PitchReplayChart :rows="filteredReplayRows" @select-pitch="setSelectedPitch" />
        <aside class="analysis-summary">
          <div v-for="metric in replaySummaryMetrics" :key="metric.label">
            <span>{{ metric.label }}</span><strong>{{ metric.value }}</strong>
          </div>
          <section class="selected-pitch">
            <span>Selected pitch</span>
            <strong>{{ selectedPitchLabel }}</strong>
            <p v-if="selectedPitch">{{ replayStatusLabel }} · Flight {{ displayNumber(selectedPitch.flight_time_seconds, 3) }} s · Closure X {{ displayNumber(selectedPitch.closure_error_x_in, 2) }}″ / Z {{ displayNumber(selectedPitch.closure_error_z_in, 2) }}″</p>
            <button v-if="selectedPitchVideoUrl" type="button" @click="emit('select-pitch', selectedPitch!)">Open Savant video</button>
          </section>
        </aside>
      </div>
      <p v-if="analysis && !filteredReplayRows.length" class="state-message">No replay pitches match these filters.</p>
    </template>

  </section>
</template>

<script setup lang="ts">
import type { AnalysisResponse } from '~/types/api'

type Mode = 'location' | 'sequence' | 'movement' | 'replay'

const props = defineProps<{ mode: Mode; year: number; gamePk: number; pitcherId: number; pitcherName: string }>()
const emit = defineEmits<{ 'select-pitch': [pitch: Record<string, unknown>] }>()
const api = useApi()

const analysis = ref<AnalysisResponse | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const selectedPitch = ref<Record<string, unknown> | null>(null)
const stand = ref('All')
const count = ref('All')
const pitch = ref('All')
const pitchResult = ref('All')
const inPlayResult = ref('All')
const paResult = ref('All')
const catcher = ref('All')
const detailCount = ref('0-0')
const followupPitch = ref('All')
const conditionCount = ref('0-0')
const conditionPitch = ref('All')
const availablePitches = ref<string[]>([])
const availableCatchers = ref<string[]>([])
const movementChartMode = ref<'scatter' | 'average'>('scatter')
let requestVersion = 0
let reloadTimer: ReturnType<typeof setTimeout> | null = null

const standOptions = [{ value: 'L', label: 'LHH' }, { value: 'R', label: 'RHH' }]
const exactCountOptions = ['0-0', '0-1', '0-2', '1-0', '1-1', '1-2', '2-0', '2-1', '2-2', '3-0', '3-1', '3-2']
const countOptions = [...exactCountOptions, 'Pitcher Ahead', 'Hitter Ahead', 'Two Strikes']
const pitchResultOptions = [
  { value: 'Called Strike', label: 'Called Strike' }, { value: 'Whiff', label: 'Whiff' },
  { value: 'Foul', label: 'Foul' }, { value: 'In Play', label: 'In Play' }, { value: 'Ball', label: 'Ball' }
]
const inPlayResultOptions = ['Out', 'Hit', 'Error', 'Sacrifice']
const paResultOptions = ['Strikeout', 'Walk', 'Hit', 'Out', 'Error', 'Sacrifice']
const pitchOptions = computed(() => availablePitches.value)
const pitchOptionsWithoutAll = computed(() => availablePitches.value.filter(option => option !== 'All'))
const catcherOptions = computed(() => availableCatchers.value)
const modeLabel = computed(() => ({
  location: 'Pitcher Location',
  sequence: 'Pitcher Sequence',
  movement: 'Pitcher Movement',
  replay: 'Pitch Replay',
})[props.mode])
const locationPoints = computed(() => asRows(analysis.value?.charts.pitch_location_scatter))
const shapeRows = computed(() => asRows(analysis.value?.charts.pitch_shape_scatter))
const filteredShapeRows = computed(() => shapeRows.value.filter(matchesShapeFilters))
const filteredMovementRows = computed(() => filteredShapeRows.value.filter(row => finitePair(row.h_break, row.v_break)))
const replayRows = computed(() => asRows(analysis.value?.charts.pitch_replay))
const filteredReplayRows = computed(() => replayRows.value.filter(matchesShapeFilters))
const filteredMovementSummary = computed(() => summarizeMovement(filteredMovementRows.value))
const countPitchMixRows = computed(() => asRows(analysis.value?.charts.count_pitch_mix))
const conditionedCountPitchMixRows = computed(() => asRows(analysis.value?.charts.conditioned_count_pitch_mix))
const filterSnapshot = computed(() => (analysis.value?.charts.filter_snapshot || {}) as Record<string, unknown>)
const filteredPitchCount = computed(() => props.mode === 'movement' ? filteredShapeRows.value.length : props.mode === 'replay' ? filteredReplayRows.value.length : Number(filterSnapshot.value.pitches || locationPoints.value.length || 0))
const summaryMetrics = computed(() => [
  { label: 'Pitches', value: String(filteredPitchCount.value) },
  { label: 'Zone%', value: formatPercent(filterSnapshot.value.zone_pct) },
  { label: 'Whiff%', value: formatPercent(filterSnapshot.value.whiff_pct) },
  { label: 'AVG', value: formatAverage(filterSnapshot.value.avg) }
])
const selectedPitchKey = computed(() => selectedPitch.value ? `${selectedPitch.value.game_pk}-${selectedPitch.value.at_bat_number}-${selectedPitch.value.pitch_number}` : null)
const movementSelectedKey = computed(() => String(selectedPitch.value?._movement_point_key || '') || null)
const selectedPitchVideoUrl = computed(() => pitchVideoUrl(selectedPitch.value))
const pitcherHand = computed(() => String(analysis.value?.summary.find(item => item.key === 'pitcher_hand')?.value || 'Unknown'))
const shapeSummaryMetrics = computed(() => {
  const rows = filteredMovementRows.value
  const videoCount = rows.filter(row => Boolean(pitchVideoUrl(row))).length
  return [
    { label: 'Pitches', value: String(rows.length) },
    { label: 'Pitch Types', value: String(new Set(rows.map(row => String(row.pitch_name || 'Unknown'))).size) },
    { label: 'Videos', value: String(videoCount) },
    { label: 'Coverage', value: filteredShapeRows.value.length ? `${(rows.length / filteredShapeRows.value.length * 100).toFixed(1)}%` : '—' },
  ]
})
const replaySummaryMetrics = computed(() => {
  const supported = filteredReplayRows.value.filter(row => row.trajectory_status === 'supported').length
  const limited = filteredReplayRows.value.filter(row => row.trajectory_status === 'limited_trajectory').length
  const unavailable = filteredReplayRows.value.filter(row => row.trajectory_status === 'unavailable').length
  return [
    { label: 'Pitches', value: String(filteredReplayRows.value.length) },
    { label: 'Supported', value: String(supported) },
    { label: 'Limited', value: String(limited) },
    { label: 'Unavailable', value: String(unavailable) },
  ]
})
const replayStatusLabel = computed(() => ({ supported: 'Supported trajectory', limited_trajectory: 'Limited trajectory', unavailable: 'Replay unavailable' } as Record<string, string>)[String(selectedPitch.value?.trajectory_status || '')] || 'Select a pitch')
const selectedPitchLabel = computed(() => selectedPitch.value ? `${selectedPitch.value.pitch_name || 'Pitch'} · ${displayNumber(selectedPitch.value.release_speed)} mph · ${selectedPitch.value.balls ?? '—'}-${selectedPitch.value.strikes ?? '—'}` : 'Click a pitch in the chart')

function queryValue(value: string) { return value && value !== 'All' ? value : undefined }
function asRows(value: unknown) { return Array.isArray(value) ? value.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object' && !Array.isArray(row)) : [] }
function formatPercent(value: unknown) { const number = Number(value); return Number.isFinite(number) ? `${number.toFixed(1)}%` : '—' }
function formatAverage(value: unknown) { const number = Number(value); return Number.isFinite(number) ? number.toFixed(3).replace(/^0/, '') : '—' }
function displayNumber(value: unknown, digits = 1) { if (value === null || value === undefined || value === '') return '—'; const number = Number(value); return Number.isFinite(number) ? number.toFixed(digits) : '—' }
function pitchVideoUrl(value: Record<string, unknown> | null) { if (!value) return ''; const direct = String(value.video_url || ''); if (direct) return direct; const playId = String(value.play_id || ''); return playId ? `https://baseballsavant.mlb.com/sporty-videos?playId=${encodeURIComponent(playId)}` : '' }
function selectPitch(value: Record<string, unknown>) { selectedPitch.value = value; if (pitchVideoUrl(value)) emit('select-pitch', value) }
function setSelectedPitch(value: Record<string, unknown>) { selectedPitch.value = value }
function applyBranch(branch: { count: string; pitch: string }) { detailCount.value = branch.count; followupPitch.value = branch.pitch; conditionCount.value = branch.count; conditionPitch.value = branch.pitch }
function selectedValues(value: string) { return value === 'All' || !value ? [] : value.split(',').map(item => item.trim()).filter(Boolean) }
function finitePair(left: unknown, right: unknown) { return Number.isFinite(Number(left)) && Number.isFinite(Number(right)) }
function matchesShapeFilters(row: Record<string, unknown>) {
  const stands = selectedValues(stand.value)
  if (stands.length && !stands.includes(String(row.stand || '').toUpperCase())) return false
  const pitches = selectedValues(pitch.value)
  if (pitches.length && !pitches.includes(String(row.pitch_name || ''))) return false
  const pitchResults = selectedValues(pitchResult.value)
  if (pitchResults.length && !pitchResults.includes(String(row.pitch_result_group || 'Other'))) return false
  const inPlayResults = selectedValues(inPlayResult.value)
  if (inPlayResults.length && !inPlayResults.includes(String(row.in_play_result_group || 'Other'))) return false
  const paResults = selectedValues(paResult.value)
  if (paResults.length && !paResults.includes(String(row.pa_result_group || 'Other'))) return false
  const catchers = selectedValues(catcher.value)
  if (catchers.length && !catchers.includes(String(row.catcher_name || ''))) return false
  const counts = selectedValues(count.value)
  if (!counts.length) return true
  const balls = Number(row.balls)
  const strikes = Number(row.strikes)
  return counts.some((value) => {
    if (value === 'Pitcher Ahead') return strikes > balls
    if (value === 'Hitter Ahead') return balls > strikes
    if (value === 'Two Strikes') return strikes === 2
    return value === `${balls}-${strikes}`
  })
}
function summarizeMovement(rows: Array<Record<string, unknown>>) {
  const groups = new Map<string, Array<Record<string, unknown>>>()
  for (const row of rows) {
    const name = String(row.pitch_name || 'Unknown')
    groups.set(name, [...(groups.get(name) || []), row])
  }
  return [...groups.entries()].map(([name, group]) => ({
    Pitch: name,
    pitch_name: name,
    pitches: group.length,
    usage_pct: rows.length ? group.length / rows.length * 100 : 0,
    h_break: average(group, 'h_break'),
    v_break: average(group, 'v_break'),
    release_speed: average(group, 'release_speed'),
  })).sort((left, right) => right.pitches - left.pitches)
}
function average(rows: Array<Record<string, unknown>>, key: string) {
  const values = rows.map(row => Number(row[key])).filter(Number.isFinite)
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
}

function updateOptions(payload: AnalysisResponse) {
  const rows = asRows(payload.charts.pitch_replay).length
    ? asRows(payload.charts.pitch_replay)
    : asRows(payload.charts.pitch_shape_scatter).length
      ? asRows(payload.charts.pitch_shape_scatter)
      : asRows(payload.charts.pitch_location_scatter)
  const pitches = rows.map(row => String(row.pitch_name || '')).filter(Boolean)
  availablePitches.value = [...new Set([...availablePitches.value, ...pitches])].sort()
  const catcherOptions = Array.isArray(payload.charts.catcher_options) ? payload.charts.catcher_options.map(String).filter(Boolean) : []
  const rowCatchers = rows.map(row => String(row.catcher_name || '')).filter(Boolean)
  const catchers = [...catcherOptions, ...rowCatchers]
  availableCatchers.value = [...new Set([...availableCatchers.value, ...catchers])].sort()
}

async function loadPanel() {
  const version = ++requestVersion
  loading.value = true
  errorMessage.value = ''
  try {
    const shared = { year: props.year, gamePk: props.gamePk, pitcherId: props.pitcherId, stand: queryValue(stand.value), count: queryValue(count.value), pitch: queryValue(pitch.value), pitchResult: queryValue(pitchResult.value), catcher: queryValue(catcher.value) }
    const result = props.mode === 'location'
      ? await api.gamePitcherLocation({ ...shared, inPlayResult: queryValue(inPlayResult.value), paResult: queryValue(paResult.value) })
      : props.mode === 'sequence'
        ? await api.gamePitcherSequence({ ...shared, conditionCount: conditionCount.value, conditionPitch: conditionPitch.value, detailCount: detailCount.value, followupPitch: followupPitch.value })
        : props.mode === 'replay'
          ? await api.gamePitcherReplay({ year: props.year, gamePk: props.gamePk, pitcherId: props.pitcherId })
          : await api.gamePitcherShape({ year: props.year, gamePk: props.gamePk, pitcherId: props.pitcherId })
    if (version !== requestVersion) return
    analysis.value = result
    updateOptions(result)
    const visibleRows = props.mode === 'movement' ? shapeRows.value : props.mode === 'replay' ? replayRows.value : locationPoints.value
    if (selectedPitch.value && !visibleRows.some(row => `${row.game_pk}-${row.at_bat_number}-${row.pitch_number}` === selectedPitchKey.value)) selectedPitch.value = null
  } catch (error) {
    if (version === requestVersion) errorMessage.value = error instanceof Error ? error.message : `${modeLabel.value} request failed`
  } finally {
    if (version === requestVersion) loading.value = false
  }
}

function scheduleLoad() { if (['movement', 'replay'].includes(props.mode)) return; if (reloadTimer) clearTimeout(reloadTimer); reloadTimer = setTimeout(loadPanel, 180) }
function clearFilters() { stand.value = 'All'; count.value = 'All'; pitch.value = 'All'; pitchResult.value = 'All'; inPlayResult.value = 'All'; paResult.value = 'All'; catcher.value = 'All' }

watch([stand, count, pitch, pitchResult, inPlayResult, paResult, catcher, detailCount, followupPitch, conditionCount, conditionPitch], scheduleLoad)
onMounted(loadPanel)
onBeforeUnmount(() => { requestVersion += 1; if (reloadTimer) clearTimeout(reloadTimer) })
</script>

<style scoped>
.game-analysis{display:grid;gap:14px;padding:16px;background:color-mix(in srgb,var(--color-surface) 86%,var(--color-background))}.analysis-header{display:flex;align-items:end;justify-content:space-between;gap:12px}.analysis-header span{color:var(--color-primary);font-size:11px;font-weight:900;letter-spacing:.06em;text-transform:uppercase}.analysis-header h3,.sequence-detail h4{margin:2px 0 0}.analysis-header small,.sample-note{color:var(--color-muted-text)}.analysis-filters{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:10px}.analysis-filters label,.condition-controls label{display:grid;gap:5px;color:var(--color-muted-text);font-size:10px;font-weight:900;text-transform:uppercase}.clear-button,.selected-pitch button{align-self:end;min-height:38px;border:1px solid var(--color-primary);border-radius:8px;padding:8px 12px;color:var(--color-on-primary);background:var(--color-primary);font-weight:850;cursor:pointer}.location-layout,.shape-layout,.replay-layout{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(220px,.4fr);gap:14px;align-items:start}.analysis-summary{display:grid;grid-template-columns:1fr 1fr;gap:8px}.analysis-summary>div,.selected-pitch{display:grid;gap:3px;border:1px solid var(--color-border);border-radius:10px;padding:12px;background:var(--color-surface)}.analysis-summary span,.selected-pitch span{color:var(--color-muted-text);font-size:10px;font-weight:850;text-transform:uppercase}.analysis-summary strong{font-size:21px}.selected-pitch{grid-column:1/-1}.selected-pitch p{margin:0;color:var(--color-muted-text);font-size:12px}.selected-pitch button{margin-top:7px}.state-message{margin:0;border:1px dashed var(--color-border);border-radius:8px;padding:12px;color:var(--color-muted-text)}.state-message.error{border-color:#ef4444;color:#ef4444}.sequence-layout{display:grid;gap:14px}.sample-note{margin:0;border-left:3px solid var(--color-primary);padding:8px 10px;font-size:12px}.sequence-detail{display:grid;gap:10px;border:1px solid var(--color-border);border-radius:10px;padding:12px;background:var(--color-surface)}.sequence-detail>header{display:flex;align-items:baseline;justify-content:space-between;gap:10px}.sequence-detail>header span{color:var(--color-muted-text);font-size:11px}.condition-controls{display:flex;flex-wrap:wrap;gap:10px}.condition-controls label{min-width:180px}.condition-controls select{min-height:38px;border:1px solid var(--color-border);border-radius:7px;padding:7px 9px;color:var(--color-foreground);background:var(--color-background)}.table-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.sequence-tables{border:1px solid var(--color-border);border-radius:10px;padding:10px;background:var(--color-surface)}.sequence-tables summary{cursor:pointer;font-weight:850}.sequence-tables .table-grid{margin-top:10px}
@media(max-width:980px){.analysis-filters{grid-template-columns:repeat(2,minmax(130px,1fr))}.location-layout,.shape-layout,.replay-layout,.table-grid{grid-template-columns:1fr}}
@media(max-width:640px){.analysis-header,.sequence-detail>header{align-items:start;flex-direction:column}.analysis-filters{grid-template-columns:1fr}.game-analysis{padding:12px}.condition-controls label{width:100%;min-width:0}}
</style>
