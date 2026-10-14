<template>
  <main class="comparison-page">
    <ComparisonPageHeader
      eyebrow="Period Comparison"
      title="Pitcher Period Split"
      description="First migration slice from legacy 25 Pitcher Period Comparison: period selectors and percentile cards."
      back-to="/comparison"
      back-label="Comparison Hub"
    />

    <ComparisonPeriodSetup
      v-model:left-year="leftYear" v-model:right-year="rightYear"
      v-model:left-start="leftStart" v-model:left-end="leftEnd"
      v-model:right-start="rightStart" v-model:right-end="rightEnd"
      :years="yearOptions" :can-apply="canApplyPeriods" :pending="pending" @apply="applyPeriods"
    >
      <template #directory>
        <label>Player Year<select v-model.number="directoryYear"><option v-for="yearOption in yearOptions" :key="`directory-${yearOption}`" :value="yearOption">{{ yearOption }}</option></select></label>
        <label>Team<select v-model="team"><option value="All">All</option><option v-for="teamOption in teamOptions" :key="teamOption" :value="teamOption">{{ teamOption }}</option></select></label>
        <label>Pitcher<select v-model.number="pitcherId"><option :value="null" disabled>Select pitcher</option><option v-for="pitcher in pitcherOptions" :key="pitcher.player_id" :value="pitcher.player_id">{{ pitcher.display_label }}</option></select></label>
      </template>
      <template #between>
        <ComparisonTransferPanel v-if="teamStints.length > 1" v-model:left-index="leftStintIndex" v-model:right-index="rightStintIndex" :stints="teamStints" :pending="pending" @compare="applyStintComparison" />
      </template>
    </ComparisonPeriodSetup>

    <ComparisonStatus :pending="pending" :error="errorMessage" label="Loading period comparison..." />

    <p v-if="canApplyPeriods && !hasAppliedOverview && !pending" class="apply-hint">
      Select pitcher and date windows, then apply to load period comparison.
    </p>

    <ComparisonCardsGrid
      v-if="hasAppliedOverview && overview"
      :left-player="overview.players.left"
      :right-player="overview.players.right"
      :left-metrics="overview.percentile_cards.left"
      :right-metrics="overview.percentile_cards.right"
    />

    <ComparisonMetricDetails
      v-if="hasAppliedOverview && overview"
      table-title="Period Metric Comparison"
      :table="overview.tables.metric_comparison"
      summary-title="Period Snapshot"
      :summary-subtitle="`${periodCounts.left.toLocaleString()} pitches vs ${periodCounts.right.toLocaleString()} pitches`"
      left-title="Period A Edge"
      right-title="Period B Edge"
      :left-rows="leftAdvantages"
      :right-rows="rightAdvantages"
    />

    <ComparisonStandardComparison
      v-if="hasAppliedOverview && overview"
      :table="overview.tables.standard_comparison"
    />

    <ComparisonPeriodLocation
      v-if="hasAppliedOverview && overview"
      :left-points="periodLocationPoints.left"
      :right-points="periodLocationPoints.right"
      :left-selected-key="selectedLeftLocationKey"
      :right-selected-key="selectedRightLocationKey"
      @select-left-point="selectPeriodPitch('A', $event)"
      @select-right-point="selectPeriodPitch('B', $event)"
    />

    <ComparisonPeriodVideos
      v-if="hasAppliedOverview && overview"
      :left="periodVideos.left"
      :right="periodVideos.right"
      :selected-left-point="selectedLeftPeriodPitch"
      :selected-right-point="selectedRightPeriodPitch"
    />

    <ComparisonPeriodSequence
      v-if="hasAppliedOverview && periodSequence"
      :left="periodSequence.left"
      :right="periodSequence.right"
    />

    <ComparisonPeriodWorkspace v-if="hasAppliedOverview && overview" v-model:open="filterRailOpen">
        <ComparisonPeriodMovement
          :left="periodMovement.left"
          :right="periodMovement.right"
          :stuff-color-loading="periodStuffLoading"
          @request-stuff-colors="loadPeriodStuffColors"
        />

        <ComparisonPeriodPitchMix
          :left="periodPitchMix.left"
          :right="periodPitchMix.right"
        />

        <ComparisonPeriodDiscipline
          :left="periodDiscipline.left"
          :right="periodDiscipline.right"
          :pitch-filter="periodPitchFilter"
          :group-filter="periodSituationFilter"
        />
      <template #filters>
          <label>
            Stand
            <CheckboxDropdown v-model="periodStandFilter" :options="standOptions" />
          </label>
          <label>
            Count
            <CheckboxDropdown v-model="periodCountFilter" :options="countOptions" />
          </label>
          <label>
            Pitch
            <CheckboxDropdown v-model="periodPitchFilter" :options="periodPitchOptions" />
          </label>
          <label>
            Pitch Result
            <CheckboxDropdown v-model="periodPitchResultFilter" :options="pitchResultOptions" />
          </label>
          <label>
            In Play Result
            <CheckboxDropdown v-model="periodInPlayResultFilter" :options="inPlayResultOptions" />
          </label>
          <label>
            PA Result
            <CheckboxDropdown v-model="periodPaResultFilter" :options="paResultOptions" />
          </label>
          <label>
            Panel Group
            <select v-model="periodSituationFilter">
              <option value="All">All</option>
              <option value="result">Result</option>
              <option value="discipline">Discipline</option>
              <option value="situation">Situation</option>
            </select>
          </label>
      </template>
    </ComparisonPeriodWorkspace>

    <ComparisonNotes v-if="hasAppliedOverview" :notes="overview?.notes || []" />
  </main>
</template>

<script setup lang="ts">
import type { AnalysisResponse, ComparisonOverviewResponse, ComparisonPlayer, PitcherTeamStint } from '~/types/api'

const api = useApi()
const directoryYear = ref(2026)
const leftYear = ref(2026)
const rightYear = ref(2026)
const team = ref('All')
const pitcherId = ref<number | null>(null)
const leftStart = ref('2026-03-01')
const leftEnd = ref('2026-05-31')
const rightStart = ref('2026-06-01')
const rightEnd = ref('2026-07-31')
const periodStandFilter = ref('All')
const periodCountFilter = ref('All')
const periodPitchFilter = ref('All')
const periodPitchResultFilter = ref('All')
const periodInPlayResultFilter = ref('All')
const periodPaResultFilter = ref('All')
const periodSituationFilter = ref('All')
const filterRailOpen = ref(false)
const selectedLeftPeriodPitch = ref<Record<string, unknown> | null>(null)
const selectedRightPeriodPitch = ref<Record<string, unknown> | null>(null)
const overview = ref<ComparisonOverviewResponse | null>(null)
const periodSequence = ref<{ left: AnalysisResponse; right: AnalysisResponse } | null>(null)
const pending = ref(false)
const errorMessage = ref('')
const periodStuffLoading = ref(false)
const teamStints = ref<PitcherTeamStint[]>([])
const leftStintIndex = ref<number | null>(null)
const rightStintIndex = ref<number | null>(null)
const applyingTeamStints = ref(false)

const standOptions = ['All', 'L', 'R']
const countOptions = ['All', '0-0', '0-1', '0-2', '1-0', '1-1', '1-2', '2-0', '2-1', '2-2', '3-0', '3-1', '3-2', 'Pitcher Ahead', 'Hitter Ahead', 'Two Strikes']
const pitchResultOptions = [
  { label: 'All', value: 'All' },
  { label: 'Called Strike', value: 'called_strike' },
  { label: 'Swing', value: 'swing' },
  { label: 'Swinging Strike', value: 'swinging_strike' },
  { label: 'Foul', value: 'foul' },
  { label: 'Ball', value: 'ball' },
  { label: 'In Play', value: 'in_play' }
]
const inPlayResultOptions = [
  { label: 'All', value: 'All' },
  { label: 'Hard Hit', value: 'hard_hit' },
  { label: 'Barrel', value: 'barrel' },
  { label: 'Solid Contact', value: 'solid_contact' },
  { label: 'Flare/Burner', value: 'flare_burner' },
  { label: 'Poorly Under', value: 'poorly_under' },
  { label: 'Poorly Topped', value: 'poorly_topped' },
  { label: 'Poorly Weak', value: 'poorly_weak' },
  { label: 'Unclassified', value: 'unclassified' },
  { label: 'Not In Play', value: 'not_in_play' }
]
const paResultOptions = [
  { label: 'All', value: 'All' },
  { label: 'No Result', value: 'pa_no_result' },
  { label: 'Single', value: 'pa_single' },
  { label: 'Double', value: 'pa_double' },
  { label: 'Triple', value: 'pa_triple' },
  { label: 'Home Run', value: 'pa_home_run' },
  { label: 'Strikeout', value: 'pa_strikeout' },
  { label: 'Walk', value: 'pa_walk' },
  { label: 'Out', value: 'pa_out' },
  { label: 'Error', value: 'pa_error' },
  { label: 'Sacrifice', value: 'pa_sacrifice' },
  { label: 'Advance On Throw', value: 'pa_advance_on_throw' },
  { label: 'Fielder Choice', value: 'pa_fielders_choice' },
  { label: 'Other', value: 'pa_other' }
]

const { data: options, refresh: refreshOptions } = await useAsyncData(
  () => `comparison-period-options-${directoryYear.value}`,
  () => api.comparisonPeriodOptions(directoryYear.value),
  { default: () => ({ meta: { year: directoryYear.value, data_updated_at: null, warnings: [] }, years: [directoryYear.value], pitchers: [] }) }
)

const yearOptions = computed(() => options.value.years.length ? options.value.years : [directoryYear.value])
const allPitchers = computed<ComparisonPlayer[]>(() => options.value.pitchers)
const teamOptions = computed(() => [...new Set(allPitchers.value.map((pitcher) => pitcher.team).filter(Boolean))].sort())
const pitcherOptions = computed(() => {
  if (team.value === 'All') {
    return allPitchers.value
  }
  return allPitchers.value.filter((pitcher) => pitcher.team === team.value)
})
const periodCounts = computed(() => {
  const counts = overview.value?.charts?.period_counts as { left?: number; right?: number } | undefined
  return { left: counts?.left || 0, right: counts?.right || 0 }
})
const periodLocationPoints = computed(() => {
  const locations = overview.value?.charts?.period_locations as {
    left?: Record<string, unknown>[]
    right?: Record<string, unknown>[]
  } | undefined
  return {
    left: locations?.left || [],
    right: locations?.right || []
  }
})
const periodMovement = computed(() => {
  const movement = overview.value?.charts?.period_movement as {
    left?: { scatter?: Record<string, unknown>[]; summary?: Record<string, unknown>[]; league?: Record<string, unknown>[]; pitcher_hand?: string }
    right?: { scatter?: Record<string, unknown>[]; summary?: Record<string, unknown>[]; league?: Record<string, unknown>[]; pitcher_hand?: string }
  } | undefined
  return {
    left: {
      scatter: movement?.left?.scatter || [],
      summary: movement?.left?.summary || [],
      league: movement?.left?.league || [],
      pitcher_hand: movement?.left?.pitcher_hand || 'Unknown'
    },
    right: {
      scatter: movement?.right?.scatter || [],
      summary: movement?.right?.summary || [],
      league: movement?.right?.league || [],
      pitcher_hand: movement?.right?.pitcher_hand || 'Unknown'
    }
  }
})
const periodPitchMix = computed(() => {
  const pitchMix = overview.value?.charts?.period_pitch_mix as {
    left?: { rows?: Record<string, unknown>[]; total?: number }
    right?: { rows?: Record<string, unknown>[]; total?: number }
  } | undefined
  return {
    left: {
      rows: pitchMix?.left?.rows || [],
      total: Number(pitchMix?.left?.total || 0)
    },
    right: {
      rows: pitchMix?.right?.rows || [],
      total: Number(pitchMix?.right?.total || 0)
    }
  }
})
const periodPitchOptions = computed(() => {
  const rows = [...periodPitchMix.value.left.rows, ...periodPitchMix.value.right.rows]
  return [...new Set(rows.map((row) => String(row.pitch || row.pitch_name || row.Pitch || '')).filter(Boolean))].sort()
})
const periodDiscipline = computed(() => {
  const discipline = overview.value?.charts?.period_discipline as {
    left?: { panel_groups?: Record<string, unknown>; total?: number }
    right?: { panel_groups?: Record<string, unknown>; total?: number }
  } | undefined
  return {
    left: {
      panel_groups: discipline?.left?.panel_groups || {},
      total: Number(discipline?.left?.total || 0)
    },
    right: {
      panel_groups: discipline?.right?.panel_groups || {},
      total: Number(discipline?.right?.total || 0)
    }
  }
})
const periodVideos = computed(() => {
  const videos = overview.value?.charts?.period_videos as {
    left?: { rows?: Record<string, unknown>[]; total?: number }
    right?: { rows?: Record<string, unknown>[]; total?: number }
  } | undefined
  return {
    left: {
      rows: videos?.left?.rows || [],
      total: Number(videos?.left?.total || 0)
    },
    right: {
      rows: videos?.right?.rows || [],
      total: Number(videos?.right?.total || 0)
    }
  }
})
const selectedLeftLocationKey = computed(() => selectedLeftPeriodPitch.value ? pitchPointKey(selectedLeftPeriodPitch.value) : null)
const selectedRightLocationKey = computed(() => selectedRightPeriodPitch.value ? pitchPointKey(selectedRightPeriodPitch.value) : null)
const { leftAdvantages, rightAdvantages } = useComparisonAdvantages(overview)
const canApplyPeriods = computed(() => {
  return Boolean(pitcherId.value && leftStart.value && leftEnd.value && rightStart.value && rightEnd.value)
})
const periodRequestKey = computed(() => JSON.stringify({
  pitcherId: pitcherId.value,
  leftYear: leftYear.value,
  rightYear: rightYear.value,
  leftStart: leftStart.value,
  leftEnd: leftEnd.value,
  rightStart: rightStart.value,
  rightEnd: rightEnd.value,
  stand: periodStandFilter.value,
  count: periodCountFilter.value,
  pitch: periodPitchFilter.value,
  pitchResult: periodPitchResultFilter.value,
  inPlayResult: periodInPlayResultFilter.value,
  paResult: periodPaResultFilter.value
}))
const appliedPeriodKey = ref('')
const hasAppliedOverview = computed(() => Boolean(overview.value && appliedPeriodKey.value === periodRequestKey.value))

async function loadOverview() {
  if (!canApplyPeriods.value || !pitcherId.value) {
    overview.value = null
    periodSequence.value = null
    appliedPeriodKey.value = ''
    return
  }
  pending.value = true
  errorMessage.value = ''
  try {
    const overviewParams = {
      pitcherId: pitcherId.value,
      leftYear: leftYear.value,
      rightYear: rightYear.value,
      leftStart: leftStart.value,
      leftEnd: leftEnd.value,
      rightStart: rightStart.value,
      rightEnd: rightEnd.value,
      stand: toFilterParam(periodStandFilter.value),
      count: toFilterParam(periodCountFilter.value),
      pitch: toFilterParam(periodPitchFilter.value),
      pitchResult: toFilterParam(periodPitchResultFilter.value),
      inPlayResult: toFilterParam(periodInPlayResultFilter.value),
      paResult: toFilterParam(periodPaResultFilter.value)
    }
    const [overviewResult, sequenceResult] = await Promise.all([
      api.comparisonPeriodOverview(overviewParams),
      api.comparisonPeriodSequence(overviewParams)
    ])
    overview.value = overviewResult
    periodSequence.value = sequenceResult
    appliedPeriodKey.value = periodRequestKey.value
    selectedLeftPeriodPitch.value = null
    selectedRightPeriodPitch.value = null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load period comparison.'
  } finally {
    pending.value = false
  }
}

function applyPeriods() {
  void loadOverview()
}

async function applyStintComparison(leftStint: PitcherTeamStint, rightStint: PitcherTeamStint) {
  applyingTeamStints.value = true
  leftYear.value = directoryYear.value
  rightYear.value = directoryYear.value
  await nextTick()
  leftStart.value = leftStint.start_date
  leftEnd.value = leftStint.end_date
  rightStart.value = rightStint.start_date
  rightEnd.value = rightStint.end_date
  applyingTeamStints.value = false
  await loadOverview()
}

async function loadPeriodStuffColors() {
  if (!canApplyPeriods.value || !pitcherId.value || periodStuffLoading.value) return
  periodStuffLoading.value = true
  errorMessage.value = ''
  try {
    overview.value = await api.comparisonPeriodOverview({
      pitcherId: pitcherId.value,
      leftYear: leftYear.value,
      rightYear: rightYear.value,
      leftStart: leftStart.value,
      leftEnd: leftEnd.value,
      rightStart: rightStart.value,
      rightEnd: rightEnd.value,
      stand: toFilterParam(periodStandFilter.value),
      count: toFilterParam(periodCountFilter.value),
      pitch: toFilterParam(periodPitchFilter.value),
      pitchResult: toFilterParam(periodPitchResultFilter.value),
      inPlayResult: toFilterParam(periodInPlayResultFilter.value),
      paResult: toFilterParam(periodPaResultFilter.value),
      includePitchStuff: true
    })
    appliedPeriodKey.value = periodRequestKey.value
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to calculate pitch-level Stuff+.'
  } finally {
    periodStuffLoading.value = false
  }
}

function toFilterParam(value: string) {
  return value && value !== 'All' ? value : undefined
}

function selectPeriodPitch(side: 'A' | 'B', point: Record<string, unknown>) {
  if (side === 'A') {
    selectedLeftPeriodPitch.value = point
    return
  }
  selectedRightPeriodPitch.value = point
}

function pitchPointKey(point: Record<string, unknown>) {
  return [
    point.game_pk,
    point.at_bat_number,
    point.pitch_number,
    point.plate_x,
    point.plate_z,
    point.pitch_name
  ].map((value) => String(value ?? '')).join('|')
}

watch(allPitchers, (pitchers) => {
  if (!pitchers.length) {
    pitcherId.value = null
    return
  }
  if (pitcherId.value && !pitchers.some((pitcher) => pitcher.player_id === pitcherId.value)) {
    pitcherId.value = null
  }
}, { immediate: true })

watch([team, pitcherOptions], ([, pitchers]) => {
  if (!pitchers.length) {
    pitcherId.value = null
    return
  }
  if (pitcherId.value && !pitchers.some((pitcher) => pitcher.player_id === pitcherId.value)) {
    pitcherId.value = null
  }
})

watch(directoryYear, async (year) => {
  team.value = 'All'
  pitcherId.value = null
  overview.value = null
  periodSequence.value = null
  appliedPeriodKey.value = ''
  teamStints.value = []
  leftStintIndex.value = null
  rightStintIndex.value = null
  leftYear.value = year
  rightYear.value = year
  await refreshOptions()
})

watch([pitcherId, leftYear, rightYear], async () => {
  if (!pitcherId.value) {
    overview.value = null
    periodSequence.value = null
    appliedPeriodKey.value = ''
    teamStints.value = []
    leftStintIndex.value = null
    rightStintIndex.value = null
    return
  }
  if (applyingTeamStints.value) return
  try {
    const leftRangePromise = api.comparisonPeriodDateRange({ year: leftYear.value, pitcherId: pitcherId.value })
    const rightRangePromise = api.comparisonPeriodDateRange({ year: rightYear.value, pitcherId: pitcherId.value })
    const [leftRange, rightRange] = await Promise.all([leftRangePromise, rightRangePromise])
    const historyRange = leftYear.value === directoryYear.value
      ? leftRange
      : rightYear.value === directoryYear.value
        ? rightRange
        : await api.comparisonPeriodDateRange({ year: directoryYear.value, pitcherId: pitcherId.value })
    teamStints.value = historyRange.team_stints || []
    leftStintIndex.value = teamStints.value[0]?.stint_index ?? null
    rightStintIndex.value = teamStints.value.at(-1)?.stint_index ?? null
    if (leftRange.start_date && leftRange.end_date) {
      leftStart.value = leftRange.start_date
      leftEnd.value = leftRange.end_date
    }
    if (rightRange.start_date && rightRange.end_date) {
      rightStart.value = rightRange.start_date
      rightEnd.value = rightRange.end_date
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load period date range.'
  }
}, { immediate: true })
</script>

<style scoped>
.comparison-page {
  max-width: 1360px;
  margin: 0 auto;
  padding: 104px 20px 56px;
}

.selector-panel,
.period-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.selector-panel {
  display: grid;
  grid-template-columns: 140px 180px minmax(260px, 420px);
  gap: 14px;
  align-items: end;
  margin-top: 16px;
  padding: 18px;
}

.transfer-panel {
  display: grid;
  gap: 16px;
  margin-top: 16px;
  border: 1px solid var(--color-border);
  border-radius: 0;
  padding: 18px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.transfer-heading {
  display: flex;
  gap: 16px;
  align-items: end;
  justify-content: space-between;
}

.transfer-heading h2,
.transfer-kicker {
  margin: 0;
}

.transfer-kicker {
  color: var(--color-brand);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.transfer-heading h2 {
  margin-top: 5px;
  color: var(--color-foreground);
  font-size: 18px;
}

.transfer-heading span {
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 800;
}

.transfer-picker {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr)) auto;
  gap: 14px;
  align-items: end;
}

.transfer-apply-button {
  min-height: 42px;
  border: 1px solid color-mix(in srgb, var(--color-brand) 70%, transparent);
  border-radius: 0;
  padding: 0 18px;
  background: var(--color-brand);
  color: var(--color-brand-contrast);
  font-weight: 900;
  cursor: pointer;
}

.transfer-apply-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.period-panel {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-top: 16px;
  padding: 18px;
}

.apply-period-button {
  grid-column: 1 / -1;
  justify-self: end;
  min-height: 42px;
  border: 1px solid color-mix(in srgb, var(--color-brand) 70%, transparent);
  border-radius: var(--radius-pill);
  padding: 0 18px;
  background: var(--color-brand);
  color: var(--color-brand-contrast);
  font-weight: 900;
  cursor: pointer;
}

.apply-period-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.apply-hint {
  margin: 16px 0 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  background: var(--color-surface);
  color: var(--color-muted);
  font-weight: 800;
}

.period-group {
  display: grid;
  grid-template-columns: 110px repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-items: end;
}

.period-group h2 {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

label {
  display: grid;
  gap: 7px;
  color: var(--color-foreground);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

select,
input {
  width: 100%;
  min-height: 42px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 0 12px;
  color: var(--color-text);
  background: var(--color-surface);
}

.period-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 44px;
  gap: 18px;
  align-items: start;
  transition: grid-template-columns 160ms ease;
}

.period-workspace.filters-open {
  grid-template-columns: minmax(0, 1fr) 300px;
}

.period-main {
  min-width: 0;
}

.period-filter-rail {
  position: sticky;
  top: 86px;
  display: flex;
  gap: 10px;
  margin-top: 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 10px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
  min-height: 174px;
  overflow: hidden;
}

.period-filter-rail.open {
  padding: 14px;
}

.period-filter-rail h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

.filter-rail-toggle {
  display: grid;
  place-items: center;
  align-self: stretch;
  width: 24px;
  min-height: 150px;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--color-brand);
  background: transparent;
  cursor: pointer;
}

.filter-rail-toggle span {
  font-size: 36px;
  line-height: 1;
}

.filter-rail-toggle em {
  writing-mode: vertical-rl;
  transform: rotate(180deg);
  color: var(--color-muted-text);
  font-size: 11px;
  font-style: normal;
  font-weight: 900;
  letter-spacing: 0;
  text-transform: uppercase;
}

.filter-fields {
  display: none;
  min-width: 0;
  flex: 1;
  gap: 14px;
}

.period-filter-rail.open .filter-fields {
  display: grid;
}

@media (max-width: 940px) {
  .selector-panel,
  .period-panel,
  .transfer-picker,
  .period-group,
  .period-workspace {
    grid-template-columns: 1fr;
  }

  .transfer-heading {
    display: grid;
  }

  .period-filter-rail {
    position: static;
  }

  .filter-fields,
  .period-filter-rail.open .filter-fields {
    display: grid;
  }

  .filter-rail-toggle {
    min-height: 44px;
    width: 100%;
  }

  .filter-rail-toggle em {
    writing-mode: horizontal-tb;
    transform: none;
  }
}
</style>
