<template>
  <main class="batter-personal-page">
    <BatterPersonalHero
      :player-id="selectedBatterId"
      :name="selectedName"
      :team="selectedTeam"
      :year="year"
      :data-through="dataThrough"
      :loading="pending"
    />

    <section class="selector-panel" aria-label="Batter selection">
      <div class="selector-panel__title"><SlidersHorizontal :size="17" aria-hidden="true" /><span><strong>Player selector</strong><small>Change context without leaving the page</small></span></div>
      <label><span>Season</span><select v-model.number="year"><option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option></select></label>
      <label><span>Team</span><select v-model="team"><option value="All">All teams</option><option v-for="option in teamOptions" :key="option" :value="option">{{ option }}</option></select></label>
      <label class="player-select"><span>Batter</span><select v-model.number="selectedBatterId"><option v-for="option in batterOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
    </section>

    <nav class="tabs" aria-label="Batter personal sections">
      <button type="button" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'"><LayoutDashboard :size="17" aria-hidden="true" />Overview</button>
      <button type="button" :class="{ active: activeTab === 'timing' }" @click="activeTab = 'timing'"><Timer :size="17" aria-hidden="true" />Swing Timing</button>
      <button type="button" :class="{ active: activeTab === 'discipline' }" @click="activeTab = 'discipline'"><ScanSearch :size="17" aria-hidden="true" />Discipline & zones</button>
    </nav>

    <div v-if="pending" class="loading-grid" aria-label="Loading batter page"><span v-for="item in 5" :key="item" /></div>
    <p v-else-if="!selectedBatterId" class="state-card">Select a batter to load the page.</p>
    <BatterOverviewTab v-else-if="activeTab === 'overview'" :overview="overview" :timing="timing" :timing-loading="timingPending" />

    <template v-else-if="activeTab === 'discipline'">
      <section class="discipline-visual-section">
        <div class="location-workspace">
          <div class="location-left">
            <HeatmapBlendControl v-model="disciplineHeatmapBlend" />
            <BatterZoneHeatmap
              class="location-main"
              :points="locationPoints"
              :heatmap-blend="disciplineHeatmapBlend"
              :selected-key="selectedPitchKey"
              @select-point="openPitchVideo"
            />
          </div>
          <aside class="location-side">
            <SummaryCards :metrics="discipline?.summary || []" />
            <DisciplineFiltersBar
              v-model:stand="stand"
              v-model:count="count"
              v-model:pitch="pitch"
              v-model:secondary="pitchResult"
              v-model:start-date="startDate"
              v-model:end-date="endDate"
              v-model:heatmap-blend="disciplineHeatmapBlend"
              :stand-options="standOptions"
              :count-options="countOptions"
              :pitch-options="pitchOptions"
              secondary-label="Pitch result"
              :secondary-options="pitchResultOptions"
              show-dates
              :show-heatmap="false"
              :loading="disciplinePending"
              :filtered-total="locationPoints.length"
            />
          </aside>
        </div>
        <DisciplinePanelBoard
          :heatmap-blend="disciplineHeatmapBlend"
          :pitch-result-panels="resultPanels"
          :pa-result-panels="paResultPanels"
          :batted-ball-panels="battedBallPanels"
          :count-situation-panels="countSituationPanels"
          :count-swing-panels="countSwingPanels"
          :exact-count-panels="exactCountPanels"
        />
      </section>

      <section class="discipline-table-section">
        <header class="section-heading">
          <div><span>Data tables</span><h2>Discipline detail</h2></div>
          <p>Drag horizontally inside each table to inspect every column.</p>
        </header>
        <DataTable
          class="discipline-table discipline-table--wide"
          title="Discipline Summary"
          :table="disciplineTable('discipline_summary')"
          :max-rows="80"
        />
        <DataTable class="discipline-table" title="Stand Split" :table="disciplineTable('stand_split')" :max-rows="20" />
        <DataTable class="discipline-table" title="Count Split" :table="disciplineTable('count_split')" :max-rows="20" />
        <DataTable
          class="discipline-table"
          title="Pitcher Hand Split"
          :table="disciplineTable('pitcher_hand_split')"
          :max-rows="10"
        />
        <DataTable class="discipline-table" title="Pitchers Faced" :table="disciplineTable('pitchers_faced')" :max-rows="200" />
        <DataTable class="discipline-table" title="Pitch Mix" :table="disciplineTable('pitch_mix')" :max-rows="60" />
        <DataTable class="discipline-table" title="Pitch Results" :table="disciplineTable('pitch_results')" :max-rows="80" />
        <DataTable class="discipline-table" title="Batted Ball" :table="disciplineTable('batted_ball')" :max-rows="40" />
      </section>
    </template>

    <section v-else class="timing-section">
      <header class="section-heading">
        <div><span>V2.6 · Player timing</span><h2>Swing Timing profile</h2></div>
        <NuxtLink :to="timingLabLink">Open full Timing Lab</NuxtLink>
      </header>
      <div class="timing-filters">
        <label><span>Pitch group</span><select v-model="timingPitchGroup"><option v-for="option in timingPitchGroups" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
        <label><span>Pitch type</span><select v-model="timingPitchType"><option value="All">All in group</option><option v-for="option in visibleTimingPitchTypes" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
        <label><span>Pitcher hand</span><select v-model="timingPitcherHand"><option value="All">All pitchers</option><option value="L">LHP</option><option value="R">RHP</option></select></label>
      </div>
      <p v-if="timingPending" class="state-card">Loading Swing Timing profile…</p>
      <p v-else-if="timingError" class="state-card timing-error">Unable to load Swing Timing for this batter.</p>
      <template v-else-if="timing">
        <p v-for="warning in timing.warnings" :key="warning" class="state-card">{{ warning }}</p>
        <SwingTimingDimensionChart v-if="timing.player && timing.league && timing.data_mode === 'summary'" :player="timing.player" :league="timing.league" />
        <BatterPitchTimingMatrix :rows="timing.pitch_matrix" />
        <BatSpeedGearChange :rows="timing.pitch_matrix" />
      </template>
    </section>

    <Teleport to="body">
      <div v-if="videoModalOpen" class="video-modal-backdrop" @click.self="videoModalOpen = false">
        <section class="video-modal" role="dialog" aria-modal="true" aria-label="Selected batter pitch video">
          <header>
            <div><h2>Selected Pitch Video</h2><p>{{ selectedPitchLabel }}</p></div>
            <button type="button" aria-label="Close video" @click="videoModalOpen = false">×</button>
          </header>
          <iframe v-if="selectedPitchVideoUrl" :src="selectedPitchVideoUrl" title="Selected batter pitch video" />
          <p v-else class="video-unavailable">This pitch does not have a cached video link.</p>
          <footer>
            <dl>
              <div><dt>Stuff+</dt><dd>{{ plusValue(selectedPitch?.pitch_stuff_plus) }}</dd></div>
              <div><dt>Location+</dt><dd>{{ plusValue(selectedPitch?.location_plus_pitch) }}</dd></div>
              <div><dt>Velocity</dt><dd>{{ numberValue(selectedPitch?.release_speed, ' mph') }}</dd></div>
              <div><dt>Count</dt><dd>{{ selectedPitch ? String(selectedPitch.count || `${selectedPitch.balls ?? '—'}-${selectedPitch.strikes ?? '—'}`) : '—' }}</dd></div>
            </dl>
            <a v-if="selectedPitchVideoUrl" :href="selectedPitchVideoUrl" target="_blank" rel="noreferrer">Open in Baseball Savant</a>
          </footer>
        </section>
      </div>
    </Teleport>
  </main>
</template>

<script setup lang="ts">
import { LayoutDashboard, ScanSearch, SlidersHorizontal, Timer } from '@lucide/vue'
import type { AnalysisResponse, BatterOption, SwingTimingPlayerDetailResponse, TablePayload } from '~/types/api'
import type {
  DisciplinePanel,
  DisciplinePanelMetric,
  DisciplinePitchMixItem
} from '~/components/discipline/DisciplineZonePanel.vue'

const route = useRoute()
const router = useRouter()
const api = useApi()

const yearOptions = [2026, 2025, 2024, 2023, 2022, 2021]
const emptyTable: TablePayload = { columns: [], rows: [] }

const year = ref(toNumber(route.query.year, 2026))
const team = ref(queryString(route.query.team, 'All'))
const selectedBatterId = ref<number | null>(toNumber(route.query.batter_id, 0) || null)
const batterOptions = ref<BatterOption[]>([])
const overview = ref<AnalysisResponse | null>(null)
const discipline = ref<AnalysisResponse | null>(null)
const timing = ref<SwingTimingPlayerDetailResponse | null>(null)
const pending = ref(false)
const disciplinePending = ref(false)
const timingPending = ref(false)
const timingError = ref(false)
const selectedPitch = ref<Record<string, unknown> | null>(null)
const videoModalOpen = ref(false)
const activeTab = ref<'overview' | 'timing' | 'discipline'>('overview')
let timingRequestId = 0

const stand = ref('All')
const count = ref('All')
const pitch = ref('All')
const pitchResult = ref('All')
const startDate = ref('')
const endDate = ref('')
const disciplineHeatmapBlend = ref(0)
const timingPitchGroup = ref(queryString(route.query.timing_pitch_group, 'all'))
const timingPitchType = ref(queryString(route.query.timing_pitch_type, 'All'))
const timingPitcherHand = ref<'All' | 'L' | 'R'>(['L', 'R'].includes(queryString(route.query.timing_pitcher_hand, 'All')) ? queryString(route.query.timing_pitcher_hand, 'All') as 'L' | 'R' : 'All')
const timingPitchTypeGroups = [
  { key: 'fastball', label: 'Fastball', options: [{ value: 'FF', label: 'Four-Seam Fastball' }, { value: 'SI', label: 'Sinker' }, { value: 'FC', label: 'Cutter' }] },
  { key: 'breaking', label: 'Breaking Ball', options: [{ value: 'SL', label: 'Slider' }, { value: 'ST', label: 'Sweeper' }, { value: 'CU', label: 'Curveball' }, { value: 'KC', label: 'Knuckle Curve' }, { value: 'SV', label: 'Slurve' }] },
  { key: 'offspeed', label: 'Offspeed', options: [{ value: 'CH', label: 'Changeup' }, { value: 'FS', label: 'Splitter' }, { value: 'FO', label: 'Forkball' }] },
  { key: 'other', label: 'Other', options: [{ value: 'KN', label: 'Knuckleball' }, { value: 'EP', label: 'Eephus' }, { value: 'CS', label: 'Slow Curve' }] }
]
const timingPitchGroups = [{ value: 'all', label: 'All pitch types' }, ...timingPitchTypeGroups.map(group => ({ value: group.key, label: group.label }))]

const selectedBatter = computed(
  () => batterOptions.value.find((batter) => batter.value === selectedBatterId.value) || null
)
const selectedName = computed(() => {
  const selected = overview.value?.charts?.selected_batter as Record<string, unknown> | undefined
  return selected?.name ? String(selected.name) : selectedBatter.value?.name || 'Select Batter'
})
const selectedTeam = computed(() => selectedBatter.value?.team || String((overview.value?.charts?.selected_batter as Record<string, unknown> | undefined)?.team || team.value))
const dataThrough = computed(() => {
  const value = overview.value?.meta?.data_updated_at
  if (!value) return '-'
  const date = new Date(String(value))
  return Number.isNaN(date.getTime()) ? String(value).slice(0, 10) : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
})
const teamOptions = computed(() =>
  Array.from(
    new Set(
      batterOptions.value
        .map((batter) => batter.team)
        .filter((value) => value && value !== '-')
    )
  ).sort()
)
const disciplineFilters = computed(
  () => (discipline.value?.charts?.filters || {}) as Record<string, string[]>
)
const standOptions = computed(() => disciplineFilters.value.stand || ['All'])
const countOptions = computed(() => disciplineFilters.value.count || ['All'])
const pitchOptions = computed(() => disciplineFilters.value.pitch || ['All'])
const pitchResultOptions = computed(() => disciplineFilters.value.pitch_result || ['All'])
const locationPoints = computed(() => disciplineTable('location_points').rows)
const selectedPitchKey = computed(() => selectedPitch.value ? pitchPointKey(selectedPitch.value) : null)
const selectedPitchVideoUrl = computed(() => {
  const pitchRow = selectedPitch.value
  if (!pitchRow) return ''
  const videoUrl = String(pitchRow.video_url || '').trim()
  if (videoUrl && !['None', 'nan', 'NaN'].includes(videoUrl)) return videoUrl
  const playId = String(pitchRow.play_id || '').trim()
  return playId && !['None', 'nan', 'NaN'].includes(playId)
    ? `https://baseballsavant.mlb.com/sporty-videos?playId=${encodeURIComponent(playId)}`
    : ''
})
const selectedPitchLabel = computed(() => {
  const pitchRow = selectedPitch.value
  if (!pitchRow) return ''
  return [String(pitchRow.game_date || '').slice(0, 10), String(pitchRow.pitch_name || 'Pitch'), String(pitchRow.description || pitchRow.events || '')].filter(Boolean).join(' · ')
})
const resultPanels = computed(() => panelsFromGroup('result', 'pitch_result'))
const paResultPanels = computed(() => panelsFromGroup('result', 'pa_result'))
const battedBallPanels = computed(() => panelsFromGroup('result', 'batted_ball'))
const countSituationPanels = computed(() => panelsFromGroup('discipline', 'count_situation'))
const countSwingPanels = computed(() => panelsFromGroup('discipline', 'count_swing'))
const exactCountPanels = computed(() => panelsFromGroup('situation', 'exact_count'))
const visibleTimingPitchTypes = computed(() => timingPitchGroup.value === 'all' ? timingPitchTypeGroups.flatMap(group => group.options) : timingPitchTypeGroups.find(group => group.key === timingPitchGroup.value)?.options || [])
const timingLabLink = computed(() => ({ path: '/batters/lab/swing-timing', query: { year: year.value, batter_id: selectedBatterId.value || undefined, find: selectedName.value, timing_pitch_group: timingPitchGroup.value, timing_pitch_type: timingPitchType.value, timing_pitcher_hand: timingPitcherHand.value } }))

watch([year, team], loadBatters, { immediate: true })
watch(selectedBatterId, async () => {
  syncRoute()
  await loadPayloads()
})
watch(
  () => [route.query.year, route.query.team, route.query.batter_id] as const,
  ([yearValue, teamValue, batterValue]) => {
    const nextYear = Number(yearValue)
    const nextBatterId = Number(batterValue)
    if (Number.isFinite(nextYear) && nextYear !== year.value) year.value = nextYear
    if (typeof teamValue === 'string' && teamValue !== team.value) team.value = teamValue
    if (Number.isFinite(nextBatterId) && nextBatterId !== selectedBatterId.value) selectedBatterId.value = nextBatterId
  }
)
watch(activeTab, (tab) => {
  if (tab === 'discipline' && !discipline.value) loadDiscipline()
  if (tab === 'timing' && !timing.value && !timingPending.value) loadTiming()
})
watch([stand, count, pitch, pitchResult, startDate, endDate], () => {
  if (activeTab.value === 'discipline') loadDiscipline()
})
watch(timingPitchGroup, () => {
  const allowed = new Set(visibleTimingPitchTypes.value.map(option => option.value))
  if (timingPitchType.value !== 'All' && !allowed.has(timingPitchType.value)) timingPitchType.value = 'All'
})
watch([timingPitchGroup, timingPitchType, timingPitcherHand], () => {
  syncRoute()
  if (selectedBatterId.value) loadTiming()
})

useAutoRefresh(loadPayloads)

async function loadBatters() {
  pending.value = true
  try {
    batterOptions.value = await api.batters({ year: year.value, team: team.value })
    if (!selectedBatterId.value || !batterOptions.value.some((batter) => batter.value === selectedBatterId.value)) {
      selectedBatterId.value = batterOptions.value[0]?.value ?? null
    } else {
      await loadPayloads()
    }
    syncRoute()
  } finally {
    pending.value = false
  }
}

async function loadPayloads() {
  if (!selectedBatterId.value) {
    overview.value = null
    discipline.value = null
    timing.value = null
    return
  }
  discipline.value = null
  timing.value = null
  await loadOverview()
  void loadTiming()
  if (activeTab.value === 'discipline') await loadDiscipline()
}

async function loadOverview() {
  if (!selectedBatterId.value) return
  overview.value = await api.batterPersonalOverview({
    year: year.value,
    batterId: selectedBatterId.value
  })
}

async function loadDiscipline() {
  if (!selectedBatterId.value) return
  disciplinePending.value = true
  try {
    discipline.value = await api.batterPersonalDiscipline({
      year: year.value,
      batterId: selectedBatterId.value,
      stand: stand.value,
      count: count.value,
      pitch: pitch.value,
      pitchResult: pitchResult.value,
      startDate: startDate.value,
      endDate: endDate.value
    })
  } finally {
    disciplinePending.value = false
  }
}

async function loadTiming() {
  if (!selectedBatterId.value) return
  const requestId = ++timingRequestId
  timingPending.value = true
  timingError.value = false
  try {
    const result = await api.batterSwingTimingPlayer({
      year: year.value,
      batterId: selectedBatterId.value,
      pitchGroup: timingPitchGroup.value,
      pitchType: timingPitchType.value,
      pitcherHand: timingPitcherHand.value
    })
    if (requestId === timingRequestId) timing.value = result
  } catch {
    if (requestId === timingRequestId) { timing.value = null; timingError.value = true }
  } finally {
    if (requestId === timingRequestId) timingPending.value = false
  }
}

function disciplineTable(key: string): TablePayload {
  return discipline.value?.tables?.[key] || emptyTable
}

function panelsFromGroup(groupKey: string, sectionKey: string): DisciplinePanel[] {
  const groups = asRecord(discipline.value?.charts?.panel_groups)
  const group = asRecord(groups[groupKey])
  return toRows(group[sectionKey]).map(normalizeDisciplinePanel)
}

function normalizeDisciplinePanel(panel: Record<string, unknown>): DisciplinePanel {
  const rawPitches = Number(panel.pitches)
  return {
    key: String(panel.key || ''),
    label: String(panel.label || panel.key || ''),
    rows: toRows(panel.rows),
    pitches: Number.isFinite(rawPitches) ? rawPitches : undefined,
    metrics: toRows(panel.metrics).map(normalizeMetric),
    pitchMix: toRows(panel.pitch_mix).map(normalizePitchMix)
  }
}

function normalizeMetric(metric: Record<string, unknown>): DisciplinePanelMetric {
  const rawValue = metric.value
  return {
    label: String(metric.label || ''),
    value:
      typeof rawValue === 'number' || typeof rawValue === 'string' || rawValue === null
        ? rawValue
        : rawValue === undefined
          ? null
          : String(rawValue),
    unit: typeof metric.unit === 'string' ? metric.unit : null
  }
}

function normalizePitchMix(item: Record<string, unknown>): DisciplinePitchMixItem {
  const rawCount = Number(item.count ?? item.pitches)
  const rawPitches = Number(item.pitches ?? item.count)
  const rawRate = Number(item.rate)
  return {
    pitch: String(item.pitch || item.Pitch || 'Unknown'),
    count: Number.isFinite(rawCount) ? rawCount : undefined,
    pitches: Number.isFinite(rawPitches) ? rawPitches : undefined,
    rate: Number.isFinite(rawRate) ? rawRate : undefined
  }
}

function toRows(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return []
  return value.filter(
    (row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object' && !Array.isArray(row)
  )
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function clearDates() {
  startDate.value = ''
  endDate.value = ''
}

function openPitchVideo(point: Record<string, unknown>) {
  selectedPitch.value = point
  videoModalOpen.value = true
}

function pitchPointKey(point: Record<string, unknown>) {
  return [point.game_pk, point.at_bat_number, point.pitch_number, point.plate_x, point.plate_z, point.pitch_name]
    .map(value => String(value ?? ''))
    .join('|')
}

function plusValue(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric.toFixed(1) : '—'
}

function numberValue(value: unknown, suffix = '') {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${numeric.toFixed(1)}${suffix}` : '—'
}

function syncRoute() {
  router.replace({
    query: {
      ...route.query,
      year: String(year.value),
      team: team.value,
      batter_id: selectedBatterId.value ? String(selectedBatterId.value) : undefined,
      timing_pitch_group: timingPitchGroup.value,
      timing_pitch_type: timingPitchType.value,
      timing_pitcher_hand: timingPitcherHand.value
    }
  })
}

function queryString(value: unknown, fallback: string) {
  return typeof value === 'string' && value ? value : fallback
}

function toNumber(value: unknown, fallback: number) {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}
</script>

<style scoped>
.batter-personal-page {
  --radius-sm: 0px;
  --radius-md: 0px;
  --radius-lg: 0px;
  display: grid;
  gap: 16px;
  min-height: 100vh;
  padding: 76px clamp(16px, 3vw, 44px) 60px;
  color: var(--color-text);
}
.batter-personal-page :deep(.player-hero),
.batter-personal-page :deep(.player-hero dl div),
.batter-personal-page :deep(.status),
.batter-personal-page :deep(.player-hero__actions a),
.batter-personal-page :deep(.summary-card),
.batter-personal-page :deep(.discipline-board),
.batter-personal-page :deep(.discipline-zone-panel),
.batter-personal-page :deep(.data-table) { border-radius: 0; }
.selector-panel {
  display: grid;
  grid-template-columns: minmax(190px, .65fr) 130px 170px minmax(220px, 1fr);
  align-items: end;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: 0;
  padding: 14px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}
.selector-panel__title { align-self: center; display: flex; align-items: center; gap: 10px; color: var(--color-primary); }
.selector-panel__title span { display: grid; gap: 2px; }
.selector-panel__title strong { color: var(--color-foreground); font-size: 20px; }
.selector-panel__title small { color: var(--color-muted-text); font-size: 15px; }
label {
  display: grid;
  gap: 6px;
}
label > span { color: var(--color-muted-text); font-size: 15px; font-weight: 900; letter-spacing: .06em; text-transform: uppercase; }
select,
input {
  width: 100%;
  min-height: 44px;
  border: 1px solid var(--color-border);
  border-radius: 0;
  padding: 0 12px;
  color: var(--color-text);
  background: var(--color-background);
  font-size: 17px;
  font-weight: 700;
}
.tabs {
  display: flex;
  gap: 5px;
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: 0;
  padding: 5px;
  background: var(--color-surface);
}
.tabs button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  border: 1px solid transparent;
  border-radius: 0;
  padding: 8px 16px;
  background: transparent;
  color: var(--color-muted-text);
  cursor: pointer;
  font-size: 18px;
  font-weight: 850;
}
.tabs button.active {
  color: #111;
  background: var(--color-primary);
  box-shadow: var(--shadow-sm);
}
.discipline-visual-section,
.discipline-table-section,
.timing-section {
  display: grid;
  gap: 16px;
  border: 1px solid var(--color-border);
  border-radius: 0;
  padding: 18px;
  background: color-mix(in srgb, var(--color-surface) 94%, transparent);
  box-shadow: var(--shadow-sm);
}
.timing-section { align-content: start; }.timing-section .section-heading a { border-radius: 0; padding: 10px 14px; color: #111; background: var(--color-primary); font-size: 14px; font-weight: 850; text-decoration: none; }.timing-filters { display: grid; grid-template-columns: repeat(3,minmax(180px,1fr)); gap: 12px; }.timing-error { color: var(--color-destructive); }.timing-section :deep(.dimension-chart),.timing-section :deep(.matrix),.timing-section :deep(.gear) { margin-top: 0; }.timing-section :deep(.matrix th),.timing-section :deep(.matrix td) { padding: 11px 10px; font-size: 14px; }.timing-section :deep(.matrix td:first-child small) { font-size: 12px; }
.discipline-table-section {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.section-heading { grid-column: 1 / -1; display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; padding: 2px 2px 8px; }
.section-heading span { color: var(--color-primary); font-size: 12px; font-weight: 850; letter-spacing: .06em; text-transform: uppercase; }
.section-heading h2 { margin: 4px 0 0; color: var(--color-foreground); font-size: 21px; }
.section-heading p { margin: 0; color: var(--color-muted-text); font-size: 13px; }
.location-workspace { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(280px, .55fr); gap: 16px; align-items: start; }
.location-left, .location-side { min-width: 0; display: grid; gap: 16px; align-content: start; }
.location-side :deep(.summary-grid) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.location-side :deep(.discipline-filters-bar) { grid-template-columns: 1fr; }
.location-side :deep(.filter-status) { justify-self: start; }
.full-width { grid-column: 1 / -1; }
.state-card { color: var(--color-muted-text); }
.discipline-table--wide { grid-column: 1 / -1; }
.discipline-table :deep(.table-header) { padding: 13px 15px; }
.discipline-table :deep(.table-header h2) { font-size: 17px; }
.discipline-table :deep(.table-header span),
.discipline-table :deep(.empty) { font-size: 12px; }
.discipline-table :deep(.table-scroll) { max-width: 100%; overflow-x: auto; }
.discipline-table :deep(table) { width: max-content; min-width: 1120px; font-size: 14px; }
.discipline-table :deep(th),
.discipline-table :deep(td) { min-width: 105px; height: 48px; padding: 10px 12px; }
.discipline-table :deep(th:first-child),
.discipline-table :deep(td:first-child) { position: sticky; left: 0; z-index: 2; min-width: 190px; background: var(--color-surface); }
.discipline-table :deep(th:first-child) { z-index: 3; background: var(--color-muted); }
.discipline-table :deep(.sort-button) { font-size: 13px; }
.state-card { margin: 0; border: 1px solid var(--color-border); border-radius: 0; padding: 24px; background: var(--color-surface); }
.video-modal-backdrop { position: fixed; z-index: 1000; inset: 0; display: grid; place-items: center; padding: 24px; background: rgb(2 6 23 / 78%); backdrop-filter: blur(5px); }.video-modal { display: grid; grid-template-rows: auto minmax(360px,70vh) auto; width: min(980px,96vw); max-height: 94vh; overflow: hidden; border: 1px solid var(--color-border); border-radius: 0; background: var(--color-surface); box-shadow: 0 24px 70px rgb(0 0 0 / 50%); }.video-modal header,.video-modal footer { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 14px 18px; }.video-modal header { border-bottom: 1px solid var(--color-border); }.video-modal h2 { margin: 0; color: var(--color-foreground); font-size: 22px; }.video-modal header p { margin: 3px 0 0; color: var(--color-muted-text); }.video-modal button { border: 1px solid var(--color-border); border-radius: 0; width: 38px; height: 38px; color: var(--color-foreground); background: var(--color-background); cursor: pointer; font-size: 24px; }.video-modal iframe { width: 100%; height: 100%; border: 0; background: #000; }.video-unavailable { display: grid; place-items: center; margin: 0; color: var(--color-muted-text); }.video-modal footer { align-items: end; border-top: 1px solid var(--color-border); }.video-modal footer dl { display: flex; flex-wrap: wrap; gap: 18px; margin: 0; }.video-modal footer dl div { display: grid; gap: 2px; }.video-modal footer dt { color: var(--color-muted-text); font-size: 11px; font-weight: 850; text-transform: uppercase; }.video-modal footer dd { margin: 0; color: var(--color-foreground); font: 750 16px "Fira Code",monospace; }.video-modal footer a { border-radius: 0; padding: 9px 13px; color: #111; background: var(--color-primary); font-weight: 850; text-decoration: none; }
.loading-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.loading-grid span { height: 110px; border-radius: 0; background: linear-gradient(90deg, var(--color-surface), var(--color-muted), var(--color-surface)); background-size: 200% 100%; animation: shimmer 1.4s infinite; }
@keyframes shimmer { to { background-position: -200% 0; } }
@media (max-width: 1100px) {
  .selector-panel { grid-template-columns: 1fr 130px 170px; }
  .selector-panel__title { grid-column: 1 / -1; }
  .discipline-table-section {
    grid-template-columns: 1fr;
  }
  .discipline-table--wide { grid-column: auto; }
  .location-workspace { grid-template-columns: 1fr; }
}
@media (max-width: 700px) { .batter-personal-page { padding-top: 24px; } .selector-panel { grid-template-columns: 1fr; } .loading-grid { grid-template-columns: 1fr 1fr; } .section-heading { align-items: flex-start; flex-direction: column; }.timing-filters { grid-template-columns: 1fr; } .discipline-visual-section, .discipline-table-section, .timing-section { padding: 12px; } }
@media (prefers-reduced-motion: reduce) { .loading-grid span { animation: none; } }
</style>
