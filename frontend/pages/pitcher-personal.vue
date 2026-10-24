<template>
  <main class="analysis-page">
    <header class="page-header">
      <div class="page-header__identity">
        <MlbPlayerHeadshot
          v-if="filters.pitcherId"
          class="page-header__photo"
          :player-id="filters.pitcherId"
          :name="selectedName"
          :size="118"
          :source-width="320"
          priority
          shape="circle"
        />
        <div>
          <span class="eyebrow">Pitcher Analysis</span>
          <h1>Pitcher Personal</h1>
          <p>{{ selectedName || 'Select a pitcher to load the dashboard.' }}</p>
          <dl class="player-meta">
            <div>
              <dt>Year</dt>
              <dd>{{ filters.year }}</dd>
            </div>
            <div>
              <dt>Role</dt>
              <dd>{{ filters.role }}</dd>
            </div>
            <div>
              <dt>Team</dt>
              <dd>{{ selectedTeam || filters.team || '-' }}</dd>
            </div>
          </dl>
        </div>
      </div>
      <div class="page-status">
        <span v-if="loading" class="status">Loading data</span>
        <span v-else-if="errorMessage" class="status error">{{ errorMessage }}</span>
        <span v-else class="status ready">Ready</span>
      </div>
    </header>

    <FiltersPanel />

    <p v-if="activeWarnings.length" class="warning-strip">{{ activeWarnings.join(' ') }}</p>

    <SummaryCards :metrics="overviewSummaryMetrics" />

    <nav class="tabs" aria-label="Pitcher Personal sections">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <PitcherOverviewTab
      v-if="activeTab === 'overview'"
      :overview="overview"
    />

    <PitcherRotationTab
      v-else-if="activeTab === 'rotation'"
      v-model:selected-game-pk="selectedRotationGamePk"
      :rotation="rotation"
      :wpa-game-rows="wpaGameRows"
      :fatigue-metrics="fatigueMetrics"
      :fatigue-rows="fatigueRows"
      :wpa-games-table="wpaGamesTable"
    />

    <PitcherOutingReportTab
      v-else-if="activeTab === 'outing'"
      v-model:selected-game-pk="selectedOutingGamePk"
      :outings="outings"
      :report="outingReport"
      :loading="outingReportLoading"
      :pitcher-name="selectedName"
      :year="filters.year"
      :pitcher-id="filters.pitcherId"
      @select-pitch="openSelectedPitch"
    />

    <PitcherStuffTab
      v-else-if="activeTab === 'movement'"
      v-model:stand="stuffStand"
      v-model:count="stuffCount"
      v-model:pitch="stuffPitch"
      v-model:pitch-result="stuffPitchResult"
      v-model:in-play-result="stuffInPlayResult"
      v-model:pa-result="stuffPaResult"
      v-model:catcher="stuffCatcher"
      v-model:movement-chart-mode="movementChartMode"
      v-model:heatmap-blend="stuffHeatmapBlend"
      v-model:selected-pitch="selectedStuffPitch"
      v-model:show-timing="showStuffTiming"
      :movement="movement"
      :stuff-score="stuffScore"
      :stuff-score-loading="stuffScoreLoading"
      :timing="timing"
      :stand-options="standOptions"
      :count-options="countOptions"
      :pitch-options="pitchOptions"
      :pitch-result-options="pitchResultOptions"
      :in-play-result-options="inPlayResultOptions"
      :pa-result-options="paResultOptions"
      :catcher-options="catcherOptions"
      :loading="stuffLoading"
      :timing-loading="timingLoading"
      :filtered-total="stuffFilteredTotal"
      :snapshot-metrics="stuffSnapshotMetrics"
      :pitch-distribution="pitchDistribution"
      :movement-usage-rows="movementUsageRows"
      :movement-scatter-rows="movementScatterRows"
      :pitch-location-points="pitchLocationPoints"
      :selected-pitch-key="selectedStuffPitchKey"
      :selected-pitch-label="selectedPitchLabel"
      :selected-pitch-video-url="selectedPitchVideoUrl"
      :selected-pitch-fields="selectedPitchFields"
      @open-video="videoModalOpen = true"
      @load-pitch-stuff="enablePitchStuffColors"
    />

    <PitcherSequenceTab
      v-else-if="activeTab === 'sequence'"
      v-model:year="sequenceYear"
      v-model:stand="sequenceStand"
      v-model:count="sequenceCount"
      v-model:pitch="sequencePitch"
      v-model:pitch-result="sequencePitchResult"
      v-model:catcher="sequenceCatcher"
      v-model:use-custom-dates="sequenceUseCustomDates"
      v-model:start-date="sequenceStartDate"
      v-model:end-date="sequenceEndDate"
      v-model:condition-count="sequenceConditionCount"
      v-model:condition-pitch="sequenceConditionPitch"
      v-model:detail-count="sequenceDetailCount"
      v-model:followup-pitch="sequenceFollowupPitch"
      :sequence="sequence"
      :year-options="sequenceYearOptions"
      :stand-options="sequenceStandOptions"
      :count-options="countOptions"
      :exact-count-options="exactCountOptions"
      :pitch-options="sequencePitchOptions"
      :pitch-result-options="pitchResultOptions"
      :catcher-options="catcherOptions"
      :loading="sequenceLoading"
      :filtered-total="sequenceFilteredTotal"
      :snapshot-metrics="sequenceSnapshotMetrics"
      :count-pitch-mix-rows="countPitchMixRows"
      :conditioned-count-pitch-mix-rows="conditionedCountPitchMixRows"
      :condition-pitch-options="sequenceConditionPitchOptions"
      :detail-pitch-options="sequenceDetailPitchOptions"
      :condition-metrics="sequenceConditionMetrics"
      :condition-label="sequenceConditionLabel"
    />

    <StaminaTimeline
      v-else-if="activeTab === 'stamina'"
      :response="staminaDetail"
      :physical-response="staminaPhysicalDetail"
      :command-response="staminaCommandDetail"
      :loading="staminaLoading"
      :error="staminaError"
      :errors="staminaSignalErrors"
      three-signal
    />

    <PitcherDisciplineTab
      v-else-if="activeTab === 'discipline'"
      v-model:stand="disciplineStand"
      v-model:count="disciplineCount"
      v-model:pitch="disciplinePitch"
      v-model:catcher="disciplineCatcher"
      v-model:heatmap-blend="disciplineHeatmapBlend"
      :discipline="discipline"
      :stand-options="standOptions"
      :count-options="countOptions"
      :pitch-options="pitchOptions"
      :catcher-options="catcherOptions"
      :loading="disciplineLoading"
      :filtered-total="disciplineFilteredTotal"
      :snapshot-metrics="disciplineSnapshotMetrics"
      :result-panels="disciplineResultPanels"
      :pa-result-panels="disciplinePaResultPanels"
      :batted-ball-panels="disciplineBattedBallPanels"
      :count-panels="disciplineCountPanels"
      :count-swing-panels="disciplineCountSwingPanels"
      :exact-count-panels="disciplineExactCountPanels"
    />

    <Teleport to="body">
      <div v-if="videoModalOpen" class="video-modal-backdrop" @click.self="videoModalOpen = false">
        <section class="video-modal" role="dialog" aria-modal="true" aria-label="Selected pitch video">
          <header>
            <div>
              <h2>Selected Pitch Video</h2>
              <p>{{ selectedPitchLabel }}</p>
            </div>
            <button type="button" aria-label="Close video" @click="videoModalOpen = false">x</button>
          </header>
          <iframe v-if="selectedPitchVideoUrl" :src="selectedPitchVideoUrl" title="Selected pitch video" />
          <footer>
            <a :href="selectedPitchVideoUrl" target="_blank" rel="noreferrer">Open in Baseball Savant</a>
          </footer>
        </section>
      </div>
    </Teleport>
  </main>
</template>

<script setup lang="ts">
import type { AnalysisResponse, PersonalOverviewResponse, StaminaCommandRetentionResponse, StaminaGameStatesResponse, StaminaPhysicalStabilityResponse, TablePayload } from '~/types/api'

const filters = useAnalysisFilters()
const api = useApi()
const route = useRoute()

const routeYear = Number(route.query.year)
const routePitcherId = Number(route.query.pitcher_id || route.query.pitcherId)
const routeGamePk = Number(route.query.game_pk || route.query.gamePk)
if (Number.isFinite(routeYear)) {
  filters.year = routeYear
}
if (typeof route.query.role === 'string' && ['SP', 'RP'].includes(route.query.role)) {
  filters.role = route.query.role
}
if (typeof route.query.team === 'string') {
  filters.team = route.query.team
}
if (Number.isFinite(routePitcherId)) {
  filters.pitcherId = routePitcherId
}

const tabs = [
  { key: 'overview', label: 'Overview' },
  { key: 'rotation', label: 'Rotation' },
  { key: 'outing', label: 'Outing Report' },
  { key: 'movement', label: 'Stuff' },
  { key: 'sequence', label: 'Sequence' },
  { key: 'stamina', label: 'Stamina' },
  { key: 'discipline', label: 'Discipline' }
] as const

type TabKey = typeof tabs[number]['key']

const routeTab = typeof route.query.tab === 'string' && tabs.some((tab) => tab.key === route.query.tab)
  ? route.query.tab as TabKey
  : 'overview'

const activeTab = ref<TabKey>(routeTab)
const loading = ref(false)
const errorMessage = ref('')
const overview = ref<PersonalOverviewResponse | null>(null)
const pitches = ref<AnalysisResponse | null>(null)
const movement = ref<AnalysisResponse | null>(null)
const stuffScore = ref<AnalysisResponse | null>(null)
const discipline = ref<AnalysisResponse | null>(null)
const sequence = ref<AnalysisResponse | null>(null)
const rotation = ref<AnalysisResponse | null>(null)
const outings = ref<AnalysisResponse | null>(null)
const outingReport = ref<AnalysisResponse | null>(null)
const timing = ref<AnalysisResponse | null>(null)
const staminaDetail = ref<StaminaGameStatesResponse | null>(null)
const staminaPhysicalDetail = ref<StaminaPhysicalStabilityResponse | null>(null)
const staminaCommandDetail = ref<StaminaCommandRetentionResponse | null>(null)
const staminaLoading = ref(false)
const staminaError = ref('')
const staminaSignalErrors = ref<string[]>([])
const selectedRotationGamePk = ref<number | null>(null)
const selectedOutingGamePk = ref<number | null>(Number.isFinite(routeGamePk) ? routeGamePk : null)
const selectedStuffPitch = ref<Record<string, unknown> | null>(null)
const showStuffTiming = ref(false)
const timingLoading = ref(false)
const videoModalOpen = ref(false)
const movementChartMode = ref<'scatter' | 'average'>('scatter')
const stuffHeatmapBlend = ref(0)
const stuffStand = ref('All')
const stuffCount = ref('All')
const stuffPitch = ref('All')
const stuffPitchResult = ref('All')
const stuffInPlayResult = ref('All')
const stuffPaResult = ref('All')
const stuffCatcher = ref('All')
const stuffLoading = ref(false)
const stuffScoreLoading = ref(false)
const pitchStuffColorsEnabled = ref(false)
const sequenceYear = ref(filters.year)
const sequenceStand = ref('All')
const sequenceCount = ref('All')
const sequencePitch = ref('All')
const sequencePitchResult = ref('All')
const sequenceCatcher = ref('All')
const sequenceUseCustomDates = ref(false)
const sequenceStartDate = ref('')
const sequenceEndDate = ref('')
const sequenceConditionCount = ref('0-0')
const sequenceConditionPitch = ref('All')
const sequenceDetailCount = ref('0-0')
const sequenceFollowupPitch = ref('All')
const sequenceLoading = ref(false)
const disciplineStand = ref('All')
const disciplineCount = ref('All')
const disciplinePitch = ref('All')
const disciplineCatcher = ref('All')
const disciplineHeatmapBlend = ref(0)
const disciplineLoading = ref(false)
const outingReportLoading = ref(false)
let personalRequestVersion = 0
const dataRefreshToken = ref(0)
let outingReportRequestVersion = 0
let staminaRequestVersion = 0
let sequenceRequestVersion = 0
let personalSelectionKey = ''
let suppressNextRotationReload = false
let suppressNextOutingReportReload = false
const tabLoadKeys: Partial<Record<TabKey, string>> = {}

const standOptions = ['All', 'L', 'R']
const sequenceStandOptions = [
  { value: 'All', label: 'All Batters' },
  { value: 'L', label: 'vs LHB' },
  { value: 'R', label: 'vs RHB' }
]
const sequenceYearOptions = computed(() => [...new Set([filters.year, 2026, 2025, 2024, 2023, 2022, 2021])].sort((a, b) => b - a))
const countOptions = ['All', '0-0', '0-1', '0-2', '1-0', '1-1', '1-2', '2-0', '2-1', '2-2', '3-0', '3-1', '3-2', 'Pitcher Ahead', 'Hitter Ahead', 'Two Strikes']
const exactCountOptions = ['0-0', '0-1', '0-2', '1-0', '1-1', '1-2', '2-0', '2-1', '2-2', '3-0', '3-1', '3-2']
const pitchResultOptions = [
  { value: 'All', label: 'All' },
  { value: 'called_strike', label: 'Called Strike' },
  { value: 'swing', label: 'Swing' },
  { value: 'swinging_strike', label: 'Swinging Strike' },
  { value: 'foul', label: 'Foul' },
  { value: 'ball', label: 'Ball' },
  { value: 'in_play', label: 'In Play' }
]
const inPlayResultOptions = [
  { value: 'All', label: 'All' },
  { value: 'hard_hit', label: 'Hard Hit' },
  { value: 'barrel', label: 'Barrel' },
  { value: 'solid_contact', label: 'Solid Contact' },
  { value: 'flare_burner', label: 'Flare/Burner' },
  { value: 'poorly_under', label: 'Poorly Under' },
  { value: 'poorly_topped', label: 'Poorly Topped' },
  { value: 'poorly_weak', label: 'Poorly Weak' },
  { value: 'unclassified', label: 'Unclassified' },
  { value: 'not_in_play', label: 'Not In Play' }
]
const paResultOptions = [
  { value: 'All', label: 'All' },
  { value: 'pa_no_result', label: 'No Result' },
  { value: 'pa_single', label: 'Single' },
  { value: 'pa_double', label: 'Double' },
  { value: 'pa_triple', label: 'Triple' },
  { value: 'pa_home_run', label: 'Home Run' },
  { value: 'pa_strikeout', label: 'Strikeout' },
  { value: 'pa_walk', label: 'Walk' },
  { value: 'pa_out', label: 'Out' },
  { value: 'pa_error', label: 'Error' },
  { value: 'pa_sacrifice', label: 'Sacrifice' },
  { value: 'pa_advance_on_throw', label: 'Advance on Throw' },
  { value: 'pa_fielders_choice', label: "Fielder's Choice" },
  { value: 'pa_other', label: 'Other' }
]

const selectedName = computed(() => {
  const selected = overview.value?.selected_pitcher
  return String(selected?.label || selected?.name || '')
})

const selectedTeam = computed(() => {
  const selected = overview.value?.selected_pitcher
  return String(selected?.team || '')
})

const overviewSummaryMetrics = computed(() => {
  const metrics = [...(overview.value?.summary || [])]
  const stuffValue = stuffScore.value?.summary.find((metric) => metric.key === 'stuff_plus')?.value ?? null
  if (stuffValue === null) return metrics
  const index = metrics.findIndex((metric) => metric.key === 'stuff_plus' || metric.label === 'Stuff+')
  const metric = { key: 'stuff_plus', label: 'Stuff+', value: stuffValue }
  if (index >= 0) metrics[index] = metric
  else metrics.splice(Math.max(0, metrics.length - 1), 0, metric)
  return metrics
})

const activeWarnings = computed(() => {
  const warnings = [...(overview.value?.meta.warnings || [])]
  return [...new Set(warnings)]
})

const pitchDistribution = computed(() => {
  return toRows(pitches.value?.charts.pitch_type_distribution).filter(row => !isPitchOutRow(row))
})

const pitchLocationPoints = computed(() => {
  return toRows(movement.value?.charts.pitch_location_scatter).filter(row => !isPitchOutRow(row))
})

const selectedStuffPitchKey = computed(() => selectedStuffPitch.value ? pitchPointKey(selectedStuffPitch.value) : null)

const selectedPitchLabel = computed(() => {
  const pitch = selectedStuffPitch.value
  if (!pitch) {
    return ''
  }
  const date = String(pitch.game_date || '').slice(0, 10)
  const name = String(pitch.pitch_name || pitch.Pitch || 'Pitch')
  const description = String(pitch.description || pitch.events || '')
  return [date, name, description].filter(Boolean).join(' | ')
})

const selectedPitchVideoUrl = computed(() => {
  const pitch = selectedStuffPitch.value
  if (!pitch) {
    return ''
  }
  const videoUrl = String(pitch.video_url || '').trim()
  if (videoUrl && videoUrl !== 'None' && videoUrl !== 'nan') {
    return videoUrl
  }
  const playId = String(pitch.play_id || '').trim()
  return playId && playId !== 'None' && playId !== 'nan' ? `https://baseballsavant.mlb.com/sporty-videos?playId=${encodeURIComponent(playId)}` : ''
})

const selectedPitchFields = computed(() => {
  const pitch = selectedStuffPitch.value
  const fields = [
    'game_date', 'game_pk', 'at_bat_number', 'pitch_number', 'pitch_name', 'description', 'events',
    'balls', 'strikes', 'plate_x', 'plate_z', 'release_speed', 'pitch_stuff_plus', 'location_plus_pitch',
    'stamina_plus_trait', 'stamina_expected_retention_delta', 'stamina_expected_stuff_plus',
    'stamina_reliability', 'stamina_sample_label', 'play_id'
  ]
  const labels: Record<string, string> = {
    pitch_stuff_plus: 'Observed Stuff+',
    location_plus_pitch: 'Observed Location+',
    stamina_plus_trait: 'Stamina+ trait',
    stamina_expected_retention_delta: 'Expected retention Δ',
    stamina_expected_stuff_plus: 'Expected Stuff+',
    stamina_reliability: 'Stamina reliability',
    stamina_sample_label: 'Stamina sample'
  }
  return fields.map((key) => ({
    key,
    label: labels[key] || key,
    value: pitch ? formatFieldValue(pitch[key]) : '-'
  }))
})

const pitchTotal = computed(() => {
  const metric = pitches.value?.summary.find((item) => item.key === 'pitches')
  return typeof metric?.value === 'number' ? metric.value : null
})

const pitchOptions = computed(() => {
  const options = pitchDistribution.value.map((row) => String(row.pitch || row.Pitch || '')).filter(Boolean)
  return ['All', ...new Set(options)]
})

const sequencePitchOptions = computed(() => {
  const options = toRows(sequence.value?.charts.pitch_location_scatter)
    .map((row) => String(row.pitch_name || row.Pitch || ''))
    .filter(Boolean)
  return ['All', ...new Set(options)]
})

const catcherOptions = computed(() => {
  const sources = [
    movement.value?.charts.catcher_options,
    sequence.value?.charts.catcher_options,
    discipline.value?.charts.catcher_options
  ]
  const values = sources.flatMap((source) => Array.isArray(source) ? source.map(String) : [])
  return ['All', ...new Set(values.filter(Boolean))]
})

const stuffSnapshot = computed(() => {
  return asRecord(movement.value?.charts.filter_snapshot)
})

const stuffFilteredTotal = computed(() => {
  const filtered = Number(stuffSnapshot.value.pitches)
  return Number.isFinite(filtered) && filtered > 0 ? filtered : pitchTotal.value
})

const stuffSnapshotMetrics = computed(() => {
  return snapshotMetrics(stuffSnapshot.value)
})

const movementUsageRows = computed(() => {
  return movement.value?.tables.movement_summary?.rows || []
})

const movementScatterRows = computed(() => {
  return toRows(movement.value?.charts.movement_scatter)
})

const countPitchMixRows = computed(() => {
  return toRows(sequence.value?.charts.count_pitch_mix)
})

const conditionedCountPitchMixRows = computed(() => {
  return toRows(sequence.value?.charts.conditioned_count_pitch_mix)
})

const sequenceConditionPitchOptions = computed(() => {
  const options = countPitchMixRows.value
    .filter((row) => String(row.count || '') === sequenceConditionCount.value)
    .map((row) => String(row.Pitch || row.pitch_name || ''))
    .filter(Boolean)
  return [...new Set(options)]
})

const sequenceDetailPitchOptions = computed(() => {
  const rows = sequence.value?.tables.count_detail_current?.rows || []
  const options = rows.map((row) => String(row.Pitch || '')).filter(Boolean)
  return [...new Set(options)]
})

const sequenceConditionSummary = computed(() => asRecord(sequence.value?.charts.conditioned_summary))

const sequenceConditionMetrics = computed(() => {
  const summary = sequenceConditionSummary.value
  return [
    { key: 'downstream_pitches', label: 'Downstream Pitches', value: metricValue(summary.downstream_pitches, 0) },
    { key: 'downstream_pas', label: 'Downstream PA', value: metricValue(summary.downstream_pas, 0) },
    { key: 'downstream_wpa_sum', label: 'Downstream WPA', value: metricValue(summary.downstream_wpa_sum, '-') },
    { key: 'wpa_per_100', label: 'WPA / 100', value: metricValue(summary.wpa_per_100, '-') }
  ]
})

const sequenceConditionLabel = computed(() => {
  return sequenceConditionPitch.value === 'All'
    ? 'Select a pitch branch'
    : `${sequenceConditionCount.value} -> ${sequenceConditionPitch.value}`
})

const sequenceSnapshot = computed(() => asRecord(sequence.value?.charts.filter_snapshot))

const sequenceFilteredTotal = computed(() => {
  const filtered = Number(sequenceSnapshot.value.pitches)
  return Number.isFinite(filtered) ? filtered : pitchTotal.value
})

const sequenceSnapshotMetrics = computed(() => snapshotMetrics(sequenceSnapshot.value))

const disciplineSnapshot = computed(() => asRecord(discipline.value?.charts.filter_snapshot))

const disciplineFilteredTotal = computed(() => {
  const filtered = Number(disciplineSnapshot.value.pitches)
  return Number.isFinite(filtered) ? filtered : pitchTotal.value
})

const disciplineSnapshotMetrics = computed(() => snapshotMetrics(disciplineSnapshot.value))

const disciplineResultPanels = computed(() => {
  const richPanels = panelsFromGroup('result', 'pitch_result')
  if (richPanels.length) {
    return richPanels
  }
  const panels = asRecord(discipline.value?.charts.result_panels)
  const labels: Record<string, string> = {
    called_strike: 'Called Strike',
    swing: 'Swing',
    swinging_strike: 'Swinging Strike',
    in_play: 'In Play',
    foul: 'Foul'
  }
  return Object.entries(labels).map(([key, label]) => ({ key, label, rows: toRows(panels[key]) }))
})

const disciplinePaResultPanels = computed(() => {
  const directPanels = panelsFromChart('pa_result_panels')
  const richPanels = directPanels.length ? directPanels : panelsFromGroup('result', 'pa_result')
  return richPanels.length ? richPanels : buildPanelsFromRows(paResultPanelSpecs, disciplineLocationRows.value)
})

const disciplineBattedBallPanels = computed(() => {
  const directPanels = panelsFromChart('batted_ball_panels')
  const richPanels = directPanels.length ? directPanels : panelsFromGroup('result', 'batted_ball')
  const fallbackPanels = buildPanelsFromRows(battedBallPanelSpecs, disciplineBattedBallSourceRows.value)
  const richTotal = richPanels.reduce((sum, panel) => sum + (panel.pitches ?? panel.rows.length), 0)
  const fallbackTotal = fallbackPanels.reduce((sum, panel) => sum + (panel.pitches ?? panel.rows.length), 0)
  return richPanels.length && (richTotal > 0 || fallbackTotal === 0) ? richPanels : fallbackPanels
})

const disciplineCountPanels = computed(() => {
  const richPanels = panelsFromGroup('discipline', 'count_situation')
  if (richPanels.length) {
    return richPanels
  }
  const panels = asRecord(discipline.value?.charts.count_panels)
  const labels: Record<string, string> = {
    '0-0': '0-0',
    hitter_ahead: 'Hitter Ahead',
    pitcher_ahead: 'Pitcher Ahead',
    two_strikes: 'Two Strikes'
  }
  return Object.entries(labels).map(([key, label]) => ({ key, label, rows: toRows(panels[key]) }))
})

const disciplineCountSwingPanels = computed(() => panelsFromGroup('discipline', 'count_swing'))

const disciplineExactCountPanels = computed(() => {
  const richPanels = panelsFromGroup('situation', 'exact_count')
  if (richPanels.length) {
    return richPanels
  }
  const panels = asRecord(discipline.value?.charts.count_panels)
  return exactCountOptions.map((count) => ({ key: count, label: count, rows: toRows(panels[count]) }))
})

const wpaGameRows = computed(() => toRows(rotation.value?.charts.wpa_games))

const wpaGamesTable = computed<TablePayload>(() => {
  const rows = wpaGameRows.value
  return {
    columns: rows.length ? Object.keys(rows[0]).map((key) => ({ key, label: key })) : [],
    rows
  }
})

const fatigueRows = computed(() => rotation.value?.tables.fatigue_by_inning?.rows || [])

const fatigueMetrics = computed(() => {
  const rows = fatigueRows.value
  const last = rows.at(-1)
  if (!last) {
    return []
  }
  return [
    { key: 'pregame_readiness', label: 'Pregame Readiness', value: toRounded(last['Pregame Readiness']) },
    { key: 'final_fatigue_score', label: 'Final Fatigue Score', value: toRounded(last['Fatigue Score']) },
    { key: 'cumulative_pitches', label: 'Cumulative Pitches', value: toRounded(last['Cumulative Pitches']) },
    { key: 'innings_tracked', label: 'Innings Tracked', value: rows.length }
  ]
})

const outingRows = computed(() => outings.value?.tables.outings?.rows || [])

watch(
  () => [filters.year, filters.role, filters.pitcherId, dataRefreshToken.value] as const,
  async ([year, role, pitcherId]) => {
    if (!filters.pitcherId) {
      clearResponses()
      return
    }

    const nextSelectionKey = `${year}:${pitcherId}`
    const hasLoadedResponses = Boolean(overview.value || pitches.value || movement.value || discipline.value || sequence.value || rotation.value || outings.value || stuffScore.value)
    if (personalSelectionKey && personalSelectionKey !== nextSelectionKey && hasLoadedResponses) clearResponses()
    personalSelectionKey = nextSelectionKey
    const requestVersion = ++personalRequestVersion
    loading.value = true
    errorMessage.value = ''

    try {
      const overviewResult = await api.personalOverview({ year, role, pitcherId: Number(pitcherId) })

      if (requestVersion !== personalRequestVersion) {
        return
      }

      overview.value = overviewResult
    } catch (error) {
      if (requestVersion !== personalRequestVersion) {
        return
      }
      overview.value = null
      errorMessage.value = error instanceof Error ? error.message : 'Request failed'
    } finally {
      if (requestVersion === personalRequestVersion) {
        loading.value = false
      }
    }
  },
  { immediate: true }
)

watch(
  () => [activeTab.value, filters.year, filters.pitcherId, dataRefreshToken.value] as const,
  async ([tab, year, pitcherId, refreshToken]) => {
    if (!pitcherId || tab === 'overview' || tab === 'stamina') return
    const loadKey = `${year}:${pitcherId}:${refreshToken}`
    if (tabLoadKeys[tab] === loadKey) return
    tabLoadKeys[tab] = loadKey
    const params = { year: Number(year), pitcherId: Number(pitcherId) }

    try {
      if (tab === 'movement') {
        stuffLoading.value = true
        stuffScoreLoading.value = true
        const [pitchesResult, movementResult, stuffScoreResult] = await Promise.all([
          api.personalPitches({ ...params, limit: 1000 }),
          api.personalMovement(buildMovementParams()),
          api.stuffScore(params)
        ])
        if (filters.year !== year || filters.pitcherId !== pitcherId) return
        pitches.value = pitchesResult
        movement.value = movementResult
        stuffScore.value = stuffScoreResult
        selectedStuffPitch.value = null
        videoModalOpen.value = false
        timing.value = null
        if (showStuffTiming.value) await reloadTiming()
      } else if (tab === 'sequence') {
        await reloadSequence()
      } else if (tab === 'discipline') {
        disciplineLoading.value = true
        const result = await api.personalDiscipline(buildDisciplineParams())
        if (filters.year === year && filters.pitcherId === pitcherId) discipline.value = result
      } else if (tab === 'rotation') {
        const result = await api.personalRotation({ ...params, gamePk: selectedRotationGamePk.value || undefined })
        if (filters.year !== year || filters.pitcherId !== pitcherId) return
        rotation.value = result
        syncSelectedRotationGame()
      } else if (tab === 'outing') {
        const result = await api.personalOutings(params)
        if (filters.year !== year || filters.pitcherId !== pitcherId) return
        outings.value = result
        syncSelectedOutingGame()
        await reloadOutingReport()
      }
    } catch (error) {
      if (filters.year === year && filters.pitcherId === pitcherId) {
        delete tabLoadKeys[tab]
        errorMessage.value = error instanceof Error ? error.message : `${tab} request failed`
      }
    } finally {
      if (tab === 'movement') {
        stuffLoading.value = false
        stuffScoreLoading.value = false
      } else if (tab === 'discipline') {
        disciplineLoading.value = false
      }
    }
  },
  { immediate: true }
)

watch(
  () => [activeTab.value, filters.year, filters.pitcherId, dataRefreshToken.value] as const,
  async ([tab, year, pitcherId]) => {
    if (tab !== 'stamina') return
    if (!pitcherId) {
      staminaDetail.value = null
      staminaPhysicalDetail.value = null
      staminaCommandDetail.value = null
      staminaError.value = 'Select a pitcher to load Stamina+.'
      staminaSignalErrors.value = []
      staminaLoading.value = false
      return
    }
    if (![2025, 2026].includes(Number(year))) {
      staminaDetail.value = null
      staminaPhysicalDetail.value = null
      staminaCommandDetail.value = null
      staminaError.value = 'Observed Game Stamina+ is currently available for 2025 and 2026.'
      staminaSignalErrors.value = []
      staminaLoading.value = false
      return
    }
    const requestVersion = ++staminaRequestVersion
    staminaLoading.value = true
    staminaError.value = ''
    staminaSignalErrors.value = []
    try {
      const [quality, physical, command] = await Promise.allSettled([
        api.staminaGameStates(Number(year), Number(pitcherId)),
        api.staminaPhysicalStability(Number(year), Number(pitcherId)),
        api.staminaCommandRetention(Number(year), Number(pitcherId))
      ])
      if (requestVersion !== staminaRequestVersion) return
      staminaDetail.value = quality.status === 'fulfilled' ? quality.value : null
      staminaPhysicalDetail.value = physical.status === 'fulfilled' ? physical.value : null
      staminaCommandDetail.value = command.status === 'fulfilled' ? command.value : null
      staminaError.value = quality.status === 'rejected' ? 'Quality Stamina+ could not be loaded.' : ''
      staminaSignalErrors.value = [
        physical.status === 'rejected' ? 'Physical Stability+ could not be loaded.' : '',
        command.status === 'rejected' ? 'Command Retention+ could not be loaded.' : ''
      ].filter(Boolean)
    } catch (error) {
      if (requestVersion === staminaRequestVersion) {
        staminaDetail.value = null
        staminaPhysicalDetail.value = null
        staminaCommandDetail.value = null
        staminaError.value = error instanceof Error ? error.message : 'Could not load Stamina+.'
      }
    } finally {
      if (requestVersion === staminaRequestVersion) staminaLoading.value = false
    }
  },
  { immediate: true }
)

useAutoRefresh(() => {
  dataRefreshToken.value += 1
})

watch(
  () => [
    route.query.year,
    route.query.role,
    route.query.team,
    route.query.pitcher_id ?? route.query.pitcherId,
    route.query.game_pk ?? route.query.gamePk,
    route.query.tab
  ] as const,
  ([yearValue, roleValue, teamValue, pitcherValue, gameValue, tabValue]) => {
    const nextYear = Number(yearValue)
    const nextPitcherId = Number(pitcherValue)
    const nextGamePk = Number(gameValue)
    const pitcherChanged = Number.isFinite(nextPitcherId) && nextPitcherId !== filters.pitcherId

    if (Number.isFinite(nextYear)) filters.year = nextYear
    if (typeof roleValue === 'string' && ['SP', 'RP'].includes(roleValue)) filters.role = roleValue
    if (typeof teamValue === 'string') filters.team = teamValue

    if (pitcherChanged) {
      personalRequestVersion += 1
      clearResponses()
      selectedOutingGamePk.value = Number.isFinite(nextGamePk) ? nextGamePk : null
      filters.pitcherId = nextPitcherId
    } else if (Number.isFinite(nextGamePk) && nextGamePk !== selectedOutingGamePk.value) {
      selectedOutingGamePk.value = nextGamePk
    }

    if (typeof tabValue === 'string' && tabs.some((tab) => tab.key === tabValue)) {
      activeTab.value = tabValue as TabKey
    }
  }
)

watch(
  () => [stuffStand.value, stuffCount.value, stuffPitch.value, stuffPitchResult.value, stuffInPlayResult.value, stuffPaResult.value, stuffCatcher.value] as const,
  () => {
    selectedStuffPitch.value = null
    videoModalOpen.value = false
    if (filters.pitcherId) {
      void reloadMovement()
    }
  }
)

watch(
  () => catcherOptions.value,
  (options) => {
    if (!hasValidFilterSelection(stuffCatcher.value, options)) {
      stuffCatcher.value = 'All'
    }
    if (!hasValidFilterSelection(sequenceCatcher.value, options)) {
      sequenceCatcher.value = 'All'
    }
    if (!hasValidFilterSelection(disciplineCatcher.value, options)) {
      disciplineCatcher.value = 'All'
    }
  }
)

watch(
  () => showStuffTiming.value,
  (enabled) => {
    if (enabled && filters.pitcherId && !timing.value) {
      void reloadTiming()
    }
  }
)

watch(
  () => [
    sequenceYear.value,
    sequenceStand.value,
    sequenceCount.value,
    sequencePitch.value,
    sequencePitchResult.value,
    sequenceCatcher.value,
    sequenceUseCustomDates.value,
    sequenceStartDate.value,
    sequenceEndDate.value,
    sequenceConditionCount.value,
    sequenceConditionPitch.value,
    sequenceDetailCount.value,
    sequenceFollowupPitch.value
  ] as const,
  () => {
    if (filters.pitcherId) {
      void reloadSequence()
    }
  }
)

watch(
  () => [filters.year, filters.pitcherId] as const,
  ([year, pitcherId], [previousYear, previousPitcherId]) => {
    if (year === previousYear && pitcherId === previousPitcherId) return
    sequenceYear.value = Number(year)
    sequenceUseCustomDates.value = false
    sequenceStartDate.value = ''
    sequenceEndDate.value = ''
  }
)

watch(
  () => sequenceConditionCount.value,
  () => {
    if (sequenceConditionPitch.value !== 'All' && !sequenceConditionPitchOptions.value.includes(sequenceConditionPitch.value)) {
      sequenceConditionPitch.value = 'All'
    }
  }
)

watch(
  () => sequenceConditionPitchOptions.value,
  (options) => {
    if (sequenceConditionPitch.value !== 'All' && !options.includes(sequenceConditionPitch.value)) {
      sequenceConditionPitch.value = 'All'
    }
  }
)

watch(
  () => sequenceDetailPitchOptions.value,
  (options) => {
    if (sequenceFollowupPitch.value !== 'All' && !options.includes(sequenceFollowupPitch.value)) {
      sequenceFollowupPitch.value = 'All'
    }
  }
)

watch(
  () => [disciplineStand.value, disciplineCount.value, disciplinePitch.value, disciplineCatcher.value] as const,
  () => {
    if (filters.pitcherId) {
      void reloadDiscipline()
    }
  }
)

watch(
  () => selectedRotationGamePk.value,
  async (gamePk, previousGamePk) => {
    if (suppressNextRotationReload) {
      suppressNextRotationReload = false
      return
    }
    if (activeTab.value !== 'rotation' || !rotation.value || !gamePk || !filters.pitcherId || gamePk === previousGamePk) {
      return
    }
    try {
      rotation.value = await api.personalRotation({ year: filters.year, pitcherId: filters.pitcherId, gamePk })
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : 'Rotation request failed'
    }
  }
)

watch(
  () => selectedOutingGamePk.value,
  async (gamePk, previousGamePk) => {
    if (suppressNextOutingReportReload) {
      suppressNextOutingReportReload = false
      return
    }
    if (activeTab.value !== 'outing' || !outings.value || !gamePk || !filters.pitcherId || gamePk === previousGamePk) {
      return
    }
    await reloadOutingReport()
  }
)

function toRows(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((row): row is Record<string, unknown> => row && typeof row === 'object' && !Array.isArray(row)) : []
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function panelsFromGroup(groupKey: string, sectionKey: string) {
  const panelGroups = asRecord(discipline.value?.charts.panel_groups)
  const group = asRecord(panelGroups[groupKey])
  return toRows(group[sectionKey]).map(normalizeDisciplinePanel)
}

function panelsFromChart(chartKey: string) {
  return toRows(discipline.value?.charts[chartKey]).map(normalizeDisciplinePanel)
}

function normalizeDisciplinePanel(panel: Record<string, unknown>) {
  return {
    key: String(panel.key || ''),
    label: String(panel.label || panel.key || ''),
    rows: toRows(panel.rows),
    pitches: Number.isFinite(Number(panel.pitches)) ? Number(panel.pitches) : undefined,
    metrics: toRows(panel.metrics),
    pitchMix: toRows(panel.pitch_mix).map((pitch) => ({
      pitch: String(pitch.pitch || 'Unknown'),
      pitches: Number.isFinite(Number(pitch.pitches)) ? Number(pitch.pitches) : undefined,
      count: Number.isFinite(Number(pitch.count)) ? Number(pitch.count) : undefined,
      rate: Number.isFinite(Number(pitch.rate)) ? Number(pitch.rate) : undefined
    }))
  }
}

const disciplineLocationRows = computed(() => toRows(discipline.value?.charts.pitch_location_scatter))
const seasonPitchRows = computed(() => toRows(pitches.value?.charts.pitch_location_scatter))
const disciplineBattedBallSourceRows = computed(() => {
  if (disciplineLocationRows.value.some((row) => normalizedBattedBallType(row))) {
    return disciplineLocationRows.value
  }
  return seasonPitchRows.value.filter((row) => (
    matchesStand(row, disciplineStand.value)
    && matchesCount(row, disciplineCount.value)
    && matchesPitch(row, disciplinePitch.value)
  ))
})

const paOutEvents = new Set([
  'field_out',
  'force_out',
  'double_play',
  'triple_play',
  'grounded_into_double_play',
  'fielders_choice_out',
  'strikeout',
  'strikeout_double_play',
  'sac_bunt',
  'sac_fly',
  'sac_fly_double_play'
])
const paHitEvents = new Set(['single', 'double', 'triple', 'home_run'])

const paResultPanelSpecs = [
  { key: 'pa_out', label: 'Out', predicate: (row: Record<string, unknown>) => paOutEvents.has(normalizedCell(row.events)) },
  { key: 'pa_hit', label: 'Hit', predicate: (row: Record<string, unknown>) => paHitEvents.has(normalizedCell(row.events)) },
  { key: 'pa_home_run', label: 'Home Run', predicate: (row: Record<string, unknown>) => normalizedCell(row.events) === 'home_run' },
  { key: 'pa_strikeout', label: 'Strikeout', predicate: (row: Record<string, unknown>) => ['strikeout', 'strikeout_double_play'].includes(normalizedCell(row.events)) }
]

const battedBallPanelSpecs = [
  { key: 'ground_ball', label: 'Ground Ball', predicate: (row: Record<string, unknown>) => normalizedBattedBallType(row) === 'ground_ball' },
  { key: 'fly_ball', label: 'Fly Ball', predicate: (row: Record<string, unknown>) => normalizedBattedBallType(row) === 'fly_ball' },
  { key: 'line_drive', label: 'Line Drive', predicate: (row: Record<string, unknown>) => normalizedBattedBallType(row) === 'line_drive' },
  { key: 'popup', label: 'Popup', predicate: (row: Record<string, unknown>) => normalizedBattedBallType(row) === 'popup' }
]

function buildPanelsFromRows(
  specs: Array<{ key: string; label: string; predicate: (row: Record<string, unknown>) => boolean }>,
  rows: Record<string, unknown>[]
) {
  return specs.map((spec) => {
    const panelRows = rows.filter(spec.predicate)
    return {
      key: spec.key,
      label: spec.label,
      rows: panelRows,
      pitches: panelRows.length
    }
  })
}

function normalizedCell(value: unknown) {
  const normalized = String(value || '').toLowerCase().trim()
  return ['nan', 'none', 'null', '<na>'].includes(normalized) ? '' : normalized
}

function normalizedBattedBallType(row: Record<string, unknown>) {
  return normalizedCell(row.bb_type || row.bbType || row.batted_ball_type || row.battedBallType)
}

function matchesStand(row: Record<string, unknown>, selected: string) {
  const selections = filterSelections(selected)
  return !selections.length || selections.includes(normalizedCell(row.stand).toUpperCase())
}

function matchesPitch(row: Record<string, unknown>, selected: string) {
  const selections = filterSelections(selected)
  if (!selections.length) {
    return true
  }
  const pitchName = normalizedPitchName(String(row.pitch_name || row.Pitch || ''))
  return selections.some((selection) => pitchName === normalizedPitchName(selection))
}

function matchesCount(row: Record<string, unknown>, selected: string) {
  const selections = filterSelections(selected)
  if (!selections.length) {
    return true
  }
  const balls = Number(row.balls)
  const strikes = Number(row.strikes)
  if (!Number.isFinite(balls) || !Number.isFinite(strikes)) {
    return true
  }
  return selections.some((selection) => {
    if (selection === 'Pitcher Ahead') {
      return strikes > balls
    }
    if (selection === 'Hitter Ahead') {
      return balls > strikes
    }
    if (selection === 'Two Strikes') {
      return strikes === 2
    }
    return selection === `${Math.trunc(balls)}-${Math.trunc(strikes)}`
  })
}

function filterSelections(value: string) {
  return value && value !== 'All'
    ? value.split(',').map((item) => item.trim()).filter(Boolean)
    : []
}

function hasValidFilterSelection(value: string, options: string[]) {
  const selections = filterSelections(value)
  return !selections.length || selections.every((selection) => options.includes(selection))
}

function normalizedPitchName(value: string) {
  return value
    .replace('Four-Seam Fastball', '4-Seam')
    .replace('Four-Seam', '4-Seam')
    .replace('Split-Finger', 'Splitter')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
}

function clearResponses() {
  outingReportRequestVersion += 1
  sequenceRequestVersion += 1
  suppressNextRotationReload = false
  suppressNextOutingReportReload = false
  overview.value = null
  pitches.value = null
  movement.value = null
  stuffScore.value = null
  discipline.value = null
  sequence.value = null
  rotation.value = null
  outings.value = null
  outingReport.value = null
  timing.value = null
  staminaRequestVersion += 1
  staminaDetail.value = null
  staminaPhysicalDetail.value = null
  staminaCommandDetail.value = null
  staminaLoading.value = false
  staminaError.value = ''
  staminaSignalErrors.value = []
  selectedRotationGamePk.value = null
  selectedOutingGamePk.value = null
  selectedStuffPitch.value = null
  videoModalOpen.value = false
  pitchStuffColorsEnabled.value = false
  for (const key of Object.keys(tabLoadKeys) as TabKey[]) delete tabLoadKeys[key]
}

function buildMovementParams() {
  return {
    year: filters.year,
    pitcherId: Number(filters.pitcherId),
    stand: toFilterParam(stuffStand.value),
    count: toFilterParam(stuffCount.value),
    pitch: toFilterParam(stuffPitch.value),
    pitchResult: toFilterParam(stuffPitchResult.value),
    inPlayResult: toFilterParam(stuffInPlayResult.value),
    paResult: toFilterParam(stuffPaResult.value),
    catcher: toFilterParam(stuffCatcher.value),
    includePitchStuff: pitchStuffColorsEnabled.value
  }
}

function buildSequenceParams() {
  return {
    year: sequenceYear.value,
    pitcherId: Number(filters.pitcherId),
    stand: toFilterParam(sequenceStand.value),
    count: toFilterParam(sequenceCount.value),
    pitch: toFilterParam(sequencePitch.value),
    pitchResult: toFilterParam(sequencePitchResult.value),
    catcher: toFilterParam(sequenceCatcher.value),
    startDate: sequenceUseCustomDates.value ? sequenceStartDate.value || undefined : undefined,
    endDate: sequenceUseCustomDates.value ? sequenceEndDate.value || undefined : undefined,
    conditionCount: sequenceConditionCount.value,
    conditionPitch: toFilterParam(sequenceConditionPitch.value),
    detailCount: sequenceDetailCount.value,
    followupPitch: toFilterParam(sequenceFollowupPitch.value)
  }
}

function buildDisciplineParams() {
  return {
    year: filters.year,
    pitcherId: Number(filters.pitcherId),
    stand: toFilterParam(disciplineStand.value),
    count: toFilterParam(disciplineCount.value),
    pitch: toFilterParam(disciplinePitch.value),
    catcher: toFilterParam(disciplineCatcher.value)
  }
}

async function reloadMovement() {
  if (!filters.pitcherId) {
    return
  }

  stuffLoading.value = true
  try {
    movement.value = await api.personalMovement(buildMovementParams())
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Stuff request failed'
  } finally {
    stuffLoading.value = false
  }
}

async function enablePitchStuffColors() {
  if (pitchStuffColorsEnabled.value) return
  pitchStuffColorsEnabled.value = true
  await reloadMovement()
}

async function reloadSequence() {
  if (!filters.pitcherId) {
    return
  }

  const requestVersion = ++sequenceRequestVersion
  const pitcherId = Number(filters.pitcherId)
  const params = buildSequenceParams()
  sequenceLoading.value = true
  try {
    const result = await api.personalSequence(params)
    if (requestVersion !== sequenceRequestVersion || Number(filters.pitcherId) !== pitcherId) return
    sequence.value = result
  } catch (error) {
    if (requestVersion === sequenceRequestVersion) {
      errorMessage.value = error instanceof Error ? error.message : 'Sequence request failed'
    }
  } finally {
    if (requestVersion === sequenceRequestVersion) sequenceLoading.value = false
  }
}

async function reloadDiscipline() {
  if (!filters.pitcherId) {
    return
  }

  disciplineLoading.value = true
  try {
    discipline.value = await api.personalDiscipline(buildDisciplineParams())
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Discipline request failed'
  } finally {
    disciplineLoading.value = false
  }
}

async function reloadOutingReport() {
  if (!filters.pitcherId || !selectedOutingGamePk.value) {
    outingReportRequestVersion += 1
    outingReport.value = null
    return
  }
  const requestVersion = ++outingReportRequestVersion
  const pitcherId = Number(filters.pitcherId)
  const gamePk = selectedOutingGamePk.value
  outingReportLoading.value = true
  try {
    const response = await api.personalOutingReport({
      year: filters.year,
      pitcherId,
      gamePk
    })
    if (requestVersion === outingReportRequestVersion && pitcherId === Number(filters.pitcherId) && gamePk === selectedOutingGamePk.value) {
      outingReport.value = response
    }
  } catch (error) {
    if (requestVersion === outingReportRequestVersion) {
      errorMessage.value = error instanceof Error ? error.message : 'Outing report request failed'
    }
  } finally {
    if (requestVersion === outingReportRequestVersion) {
      outingReportLoading.value = false
    }
  }
}

async function reloadTiming() {
  if (!filters.pitcherId) {
    return
  }

  timingLoading.value = true
  try {
    timing.value = await api.personalTiming({ year: filters.year, pitcherId: filters.pitcherId })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Timing request failed'
  } finally {
    timingLoading.value = false
  }
}

function toFilterParam(value: string) {
  return value === 'All' ? undefined : value
}

function pitchPointKey(point: Record<string, unknown>) {
  if (point._movement_point_key) {
    return String(point._movement_point_key)
  }
  return [
    point.game_pk,
    point.at_bat_number,
    point.pitch_number,
    point.plate_x,
    point.plate_z,
    point.pitch_name
  ].map((value) => String(value ?? '')).join('|')
}

function isPitchOutRow(row: Record<string, unknown>) {
  const value = String(row.pitch_name ?? row.Pitch ?? row.pitch ?? row.pitch_type ?? '').trim().toLowerCase()
  return value === 'pitch out' || value === 'pitchout' || value === 'po'
}

function openSelectedPitch(pitch: Record<string, unknown>) {
  selectedStuffPitch.value = pitch
  if (selectedPitchVideoUrl.value) {
    videoModalOpen.value = true
  }
}

function syncSelectedRotationGame() {
  const rows = wpaGameRows.value
  if (!rows.length) {
    selectedRotationGamePk.value = null
    return
  }
  const currentExists = rows.some((row) => Number(row.game_pk) === selectedRotationGamePk.value)
  if (!currentExists) {
    suppressNextRotationReload = true
    selectedRotationGamePk.value = Number(rows.at(-1)?.game_pk) || null
  }
}

function syncSelectedOutingGame() {
  const rows = outingRows.value
  if (!rows.length) {
    selectedOutingGamePk.value = null
    return
  }
  const currentExists = rows.some((row) => Number(row['Game PK']) === selectedOutingGamePk.value)
  if (!currentExists) {
    suppressNextOutingReportReload = true
    selectedOutingGamePk.value = Number(rows[0]?.['Game PK']) || null
  }
}

function toRounded(value: unknown) {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? Math.round(numberValue) : null
}

function snapshotMetrics(snapshot: Record<string, unknown>) {
  return [
    { key: 'pitches', label: 'Filtered Pitches', value: toRounded(snapshot.pitches) },
    { key: 'zone_pct', label: 'Zone%', value: formatPercent(snapshot.zone_pct) },
    { key: 'swing_pct', label: 'Swing%', value: formatPercent(snapshot.swing_pct) },
    { key: 'o_swing_pct', label: 'O-Swing%', value: formatPercent(snapshot.o_swing_pct) },
    { key: 'whiff_pct', label: 'Whiff%', value: formatPercent(snapshot.whiff_pct) },
    { key: 'avg', label: 'AVG', value: formatDecimal(snapshot.avg) }
  ]
}

function metricValue(value: unknown, fallback: number | string | null) {
  return typeof value === 'number' || typeof value === 'string' || value === null ? value : fallback
}

function formatPercent(value: unknown) {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? `${numberValue.toFixed(1)}%` : null
}

function formatDecimal(value: unknown) {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue.toFixed(3) : null
}

function formatFieldValue(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(3)
  }
  return String(value)
}
</script>

<style>
.analysis-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 22px 20px 48px;
}

.page-header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  padding: 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background:
    linear-gradient(135deg, rgba(30, 64, 175, 0.09), rgba(217, 119, 6, 0.08)),
    var(--color-surface);
  box-shadow: var(--shadow-md);
}

.page-header__identity {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 18px;
}

.page-header__photo {
  color: var(--color-primary);
  box-shadow: 0 12px 32px color-mix(in srgb, var(--color-primary) 18%, transparent);
}

.eyebrow {
  display: block;
  margin-bottom: 6px;
  color: var(--color-accent);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.page-header h1 {
  margin: 0;
  color: var(--color-foreground);
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 28px;
  letter-spacing: 0;
}

.page-header p {
  margin: 6px 0 0;
  color: var(--color-muted-text);
}

.player-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 14px 0 0;
}

.player-meta div {
  min-width: 84px;
  border: 1px solid rgba(30, 64, 175, 0.15);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  background: color-mix(in srgb, var(--color-surface) 78%, transparent);
}

.player-meta dt {
  color: var(--color-muted-text);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.player-meta dd {
  margin: 3px 0 0;
  color: var(--color-text);
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 14px;
  font-weight: 700;
}

.page-status {
  display: flex;
  justify-content: flex-end;
  min-width: 132px;
}

.status {
  border: 1px solid var(--color-border-strong);
  border-radius: 999px;
  padding: 6px 11px;
  color: var(--color-text);
  background: var(--color-surface);
  font-size: 13px;
  font-weight: 650;
}

.status.ready {
  border-color: #bbf7d0;
  color: #166534;
  background: #f0fdf4;
}

.status.error {
  border-color: #fecaca;
  color: var(--color-destructive);
  background: #fef2f2;
}

.warning-strip {
  margin: 12px 0;
  border: 1px solid #fde68a;
  border-radius: var(--radius-md);
  padding: 10px 12px;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
}

.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 18px 0;
  border-bottom: 1px solid var(--color-border);
}

.tabs button {
  min-height: 40px;
  border: 1px solid transparent;
  border-bottom: 2px solid transparent;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  padding: 9px 12px;
  background: transparent;
  color: var(--color-muted-text);
  cursor: pointer;
  transition: background-color 180ms ease, border-color 180ms ease, color 180ms ease;
}

.tabs button:hover {
  background: color-mix(in srgb, var(--color-surface) 72%, transparent);
  color: var(--color-primary);
}

.tabs button.active {
  border-color: var(--color-border);
  border-bottom-color: var(--color-primary);
  background: var(--color-surface);
  color: var(--color-foreground);
  font-weight: 650;
}

.panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}

.panel-grid > :first-child {
  grid-column: 1 / -1;
}

.panel-grid > .wide-panel {
  grid-column: 1 / -1;
}

.rotation-control {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px;
  background: color-mix(in srgb, var(--color-surface) 86%, transparent);
  box-shadow: var(--shadow-sm);
}

.rotation-control label {
  display: grid;
  gap: 7px;
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.rotation-control select {
  width: min(520px, 100%);
  min-height: 38px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  background: var(--color-plot-bg);
  color: var(--color-text);
  font-size: 14px;
  text-transform: none;
}

.stuff-filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(126px, 1fr));
  gap: 12px;
  align-items: end;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px;
  background: color-mix(in srgb, var(--color-surface) 88%, transparent);
  box-shadow: var(--shadow-sm);
}

.stuff-filters label {
  display: grid;
  gap: 7px;
  min-width: 0;
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.stuff-filters select,
.stuff-filters input[type="date"] {
  width: 100%;
  min-width: 0;
  min-height: 38px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  background: var(--color-plot-bg);
  color: var(--color-text);
  font-size: 14px;
  text-transform: none;
  color-scheme: dark;
}

:root[data-theme="light"] .stuff-filters input[type="date"] {
  color-scheme: light;
}

.stuff-filters .range-filter {
  grid-template-columns: 1fr;
}

.stuff-filters .range-filter input {
  width: 100%;
}

.stuff-filters .range-filter span {
  color: var(--color-foreground);
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 13px;
  text-transform: none;
}

.filter-status {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  min-height: 38px;
  align-self: end;
  color: var(--color-muted-text);
  font-size: 13px;
  font-weight: 650;
  white-space: nowrap;
}

.condition-controls {
  display: grid;
  grid-template-columns: repeat(2, minmax(160px, 1fr)) auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 12px;
}

.condition-controls label {
  display: grid;
  gap: 7px;
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.condition-controls select {
  min-height: 38px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  background: var(--color-plot-bg);
  color: var(--color-text);
  font-size: 14px;
  text-transform: none;
}

.detail-table-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.followup-table {
  margin-top: 12px;
}

.stuff-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}

.stuff-column {
  min-width: 0;
  display: grid;
  gap: 16px;
  align-content: start;
}

.panel-section {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px;
  background: color-mix(in srgb, var(--color-surface) 88%, transparent);
  box-shadow: var(--shadow-sm);
}

.panel-section header {
  margin-bottom: 12px;
}

.panel-section h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

.location-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.location-controls header {
  margin-bottom: 0;
}

.location-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(280px, 0.55fr);
  gap: 16px;
  align-items: start;
}

.location-left,
.location-side {
  min-width: 0;
  display: grid;
  gap: 16px;
  align-content: start;
}

.location-side .summary-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.location-filters {
  grid-template-columns: 1fr;
}

.location-filters .filter-status {
  justify-content: flex-start;
}

.range-control {
  display: grid;
  grid-template-columns: auto minmax(180px, 280px) 44px;
  gap: 10px;
  align-items: center;
  color: var(--color-muted-text);
  font-size: 13px;
  font-weight: 700;
}

.range-control input {
  width: 100%;
}

.range-control span {
  color: var(--color-foreground);
  font-family: "Fira Code", "Consolas", monospace;
  text-align: right;
}

.location-main {
  width: 70%;
  justify-self: start;
}

.location-workspace .location-main {
  width: 100%;
}

.selected-pitch-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px;
  background: color-mix(in srgb, var(--color-surface) 88%, transparent);
  box-shadow: var(--shadow-sm);
}

.selected-pitch-panel header,
.toggle-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.selected-pitch-panel h2,
.toggle-header h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

.selected-pitch-panel p,
.muted-note {
  margin: 4px 0 0;
  color: var(--color-muted-text);
  font-size: 13px;
}

.video-button {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 7px 11px;
  color: var(--color-primary);
  background: var(--color-surface);
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
}

.pitch-detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.pitch-detail-grid div {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 9px 10px;
  background: var(--color-surface);
}

.pitch-detail-grid dt {
  color: var(--color-muted-text);
  font-size: 11px;
  font-weight: 750;
  text-transform: uppercase;
}

.pitch-detail-grid dd {
  overflow-wrap: anywhere;
  margin: 4px 0 0;
  color: var(--color-text);
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 13px;
}

.toggle-control {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  color: var(--color-muted-text);
  font-size: 13px;
  font-weight: 700;
}

.video-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.62);
}

.video-modal {
  width: min(960px, 100%);
  max-height: min(760px, calc(100vh - 48px));
  display: grid;
  grid-template-rows: auto minmax(360px, 1fr) auto;
  overflow: hidden;
  border: 1px solid rgba(226, 232, 240, 0.42);
  border-radius: var(--radius-md);
  background: #0f172a;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.45);
}

.video-modal header,
.video-modal footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  background: #111827;
}

.video-modal h2 {
  margin: 0;
  color: #f8fafc;
  font-size: 16px;
}

.video-modal p {
  margin: 4px 0 0;
  color: #cbd5e1;
  font-size: 13px;
}

.video-modal button {
  width: 34px;
  height: 34px;
  border: 1px solid rgba(226, 232, 240, 0.28);
  border-radius: var(--radius-sm);
  color: #f8fafc;
  background: transparent;
  cursor: pointer;
  font-size: 16px;
  font-weight: 800;
}

.video-modal iframe {
  width: 100%;
  height: 100%;
  min-height: 360px;
  border: 0;
  background: #020617;
}

.video-modal footer {
  justify-content: flex-end;
}

.video-modal a {
  color: #bfdbfe;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}

.mini-chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.exact-count-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 860px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }

  .stuff-filters {
    grid-template-columns: 1fr;
  }

  .stuff-columns {
    grid-template-columns: 1fr;
  }

  .location-workspace {
    grid-template-columns: 1fr;
  }

  .condition-controls {
    grid-template-columns: 1fr;
  }

  .detail-table-grid {
    grid-template-columns: 1fr;
  }

  .location-controls {
    display: grid;
  }

  .location-main {
    width: 100%;
  }

  .range-control {
    grid-template-columns: 1fr;
  }

  .range-control span {
    text-align: left;
  }

  .mini-chart-grid {
    grid-template-columns: 1fr;
  }

  .exact-count-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .pitch-detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .page-header {
    display: grid;
  }

  .page-header__identity {
    align-items: flex-start;
  }

  .page-header__photo {
    --headshot-size: 88px !important;
  }

  .page-status {
    justify-content: flex-start;
  }
}
</style>
