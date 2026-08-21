<template>
  <main class="comparison-page">
    <ComparisonPageHeader
      eyebrow="Personal Comparison"
      title="Pitcher vs Pitcher"
      description="First migration slice from legacy 24 Pitcher Comparison: season options and percentile cards."
      back-to="/comparison"
      back-label="Comparison Hub"
    />

    <section class="selector-panel">
      <label>
        Left Year
        <select v-model.number="leftYear">
          <option v-for="yearOption in yearOptions" :key="`left-year-${yearOption}`" :value="yearOption">{{ yearOption }}</option>
        </select>
      </label>
      <label>
        Left Team
        <select v-model="leftTeam">
          <option value="All">All</option>
          <option v-for="team in leftTeamOptions" :key="`left-team-${team}`" :value="team">{{ team }}</option>
        </select>
      </label>
      <label>
        Left Pitcher
        <select v-model.number="leftPitcherId">
          <option v-for="pitcher in leftPitcherOptions" :key="`left-${pitcher.player_id}`" :value="pitcher.player_id">
            {{ pitcher.display_label }}
          </option>
        </select>
      </label>
      <div class="selector-spacer" aria-hidden="true" />
      <label>
        Right Year
        <select v-model.number="rightYear">
          <option v-for="yearOption in yearOptions" :key="`right-year-${yearOption}`" :value="yearOption">{{ yearOption }}</option>
        </select>
      </label>
      <label>
        Right Team
        <select v-model="rightTeam">
          <option value="All">All</option>
          <option v-for="team in rightTeamOptions" :key="`right-team-${team}`" :value="team">{{ team }}</option>
        </select>
      </label>
      <label>
        Right Pitcher
        <select v-model.number="rightPitcherId">
          <option v-for="pitcher in rightPitcherOptions" :key="`right-${pitcher.player_id}`" :value="pitcher.player_id">
            {{ pitcher.display_label }}
          </option>
        </select>
      </label>
    </section>

    <ComparisonStatus :pending="pending" :error="errorMessage" label="Loading comparison..." />

    <ComparisonCardsGrid
      v-if="overview"
      :left-player="overview.players.left"
      :right-player="overview.players.right"
      :left-metrics="overview.percentile_cards.left"
      :right-metrics="overview.percentile_cards.right"
    />

    <ComparisonMetricDetails
      v-if="overview"
      table-title="Metric Comparison"
      :table="overview.tables.metric_comparison"
      summary-title="Advantage Summary"
      summary-subtitle="Largest percentile gaps from the shared metric set."
      :left-rows="leftAdvantages"
      :right-rows="rightAdvantages"
    />

    <ComparisonPeriodLocation
      v-if="overview"
      :left-points="comparisonLocationPoints.left"
      :right-points="comparisonLocationPoints.right"
      :left-selected-key="selectedLeftLocationKey"
      :right-selected-key="selectedRightLocationKey"
      @select-left-point="selectComparisonPitch('A', $event)"
      @select-right-point="selectComparisonPitch('B', $event)"
    />

    <ComparisonPeriodVideos
      v-if="overview"
      :left="comparisonVideos.left"
      :right="comparisonVideos.right"
      :selected-left-point="selectedLeftPitch"
      :selected-right-point="selectedRightPitch"
    />

    <div v-if="overview" class="comparison-workspace" :class="{ 'filters-open': filterRailOpen }">
      <div class="comparison-main">
        <ComparisonPeriodMovement
          :left="comparisonMovement.left"
          :right="comparisonMovement.right"
        />

        <ComparisonPeriodPitchMix
          :left="comparisonPitchMix.left"
          :right="comparisonPitchMix.right"
        />

        <ComparisonPeriodDiscipline
          :left="comparisonDiscipline.left"
          :right="comparisonDiscipline.right"
          :pitch-filter="comparisonPitchFilter"
          :group-filter="comparisonSituationFilter"
        />
      </div>
      <aside class="comparison-filter-rail" :class="{ open: filterRailOpen }">
        <button
          class="filter-rail-toggle"
          type="button"
          :aria-expanded="filterRailOpen"
          aria-label="Toggle comparison filters"
          @click="filterRailOpen = !filterRailOpen"
        >
          <span>{{ filterRailOpen ? '›' : '‹' }}</span>
          <em>Filters</em>
        </button>
        <div class="filter-fields">
          <h2>Comparison Filters</h2>
          <label>
            Stand
            <CheckboxDropdown v-model="comparisonStandFilter" :options="standOptions" />
          </label>
          <label>
            Count
            <CheckboxDropdown v-model="comparisonCountFilter" :options="countOptions" />
          </label>
          <label>
            Pitch
            <CheckboxDropdown v-model="comparisonPitchFilter" :options="comparisonPitchOptions" />
          </label>
          <label>
            Pitch Result
            <CheckboxDropdown v-model="comparisonPitchResultFilter" :options="pitchResultOptions" />
          </label>
          <label>
            In Play Result
            <CheckboxDropdown v-model="comparisonInPlayResultFilter" :options="inPlayResultOptions" />
          </label>
          <label>
            PA Result
            <CheckboxDropdown v-model="comparisonPaResultFilter" :options="paResultOptions" />
          </label>
          <label>
            Panel Group
            <select v-model="comparisonSituationFilter">
              <option value="All">All</option>
              <option value="result">Result</option>
              <option value="discipline">Discipline</option>
              <option value="situation">Situation</option>
            </select>
          </label>
        </div>
      </aside>
    </div>

    <ComparisonNotes :notes="overview?.notes || []" />
  </main>
</template>

<script setup lang="ts">
import type { ComparisonOverviewResponse, ComparisonPlayer } from '~/types/api'

const api = useApi()
const leftYear = ref(2026)
const rightYear = ref(2026)
const leftTeam = ref('All')
const rightTeam = ref('All')
const leftPitcherId = ref<number | null>(null)
const rightPitcherId = ref<number | null>(null)
const comparisonStandFilter = ref('All')
const comparisonCountFilter = ref('All')
const comparisonPitchFilter = ref('All')
const comparisonPitchResultFilter = ref('All')
const comparisonInPlayResultFilter = ref('All')
const comparisonPaResultFilter = ref('All')
const comparisonSituationFilter = ref('All')
const filterRailOpen = ref(false)
const selectedLeftPitch = ref<Record<string, unknown> | null>(null)
const selectedRightPitch = ref<Record<string, unknown> | null>(null)
const overview = ref<ComparisonOverviewResponse | null>(null)
const pending = ref(false)
const errorMessage = ref('')

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

const { data: leftOptions, refresh: refreshLeftOptions } = await useAsyncData(
  () => `comparison-personal-left-options-${leftYear.value}`,
  () => api.comparisonPersonalOptions(leftYear.value),
  { default: () => ({ meta: { year: leftYear.value, data_updated_at: null, warnings: [] }, years: [leftYear.value], pitchers: [] }) }
)

const { data: rightOptions, refresh: refreshRightOptions } = await useAsyncData(
  () => `comparison-personal-right-options-${rightYear.value}`,
  () => api.comparisonPersonalOptions(rightYear.value),
  { default: () => ({ meta: { year: rightYear.value, data_updated_at: null, warnings: [] }, years: [rightYear.value], pitchers: [] }) }
)

const yearOptions = computed(() => {
  const years = [...leftOptions.value.years, ...rightOptions.value.years]
  return years.length ? [...new Set(years)].sort((a, b) => b - a) : [leftYear.value, rightYear.value]
})
const leftAllPitchers = computed<ComparisonPlayer[]>(() => leftOptions.value.pitchers)
const rightAllPitchers = computed<ComparisonPlayer[]>(() => rightOptions.value.pitchers)
const leftTeamOptions = computed(() => [...new Set(leftAllPitchers.value.map((pitcher) => pitcher.team).filter(Boolean))].sort())
const rightTeamOptions = computed(() => [...new Set(rightAllPitchers.value.map((pitcher) => pitcher.team).filter(Boolean))].sort())

function filterPitchersByTeam(team: string, side: 'left' | 'right' = 'left') {
  const pool = side === 'left' ? leftAllPitchers.value : rightAllPitchers.value
  if (team === 'All') {
    return pool
  }
  return pool.filter((pitcher) => pitcher.team === team)
}

const leftPitcherOptions = computed(() => filterPitchersByTeam(leftTeam.value, 'left'))
const rightPitcherOptions = computed(() => filterPitchersByTeam(rightTeam.value, 'right'))
const { leftAdvantages, rightAdvantages } = useComparisonAdvantages(overview)
const comparisonLocationPoints = computed(() => {
  const locations = overview.value?.charts?.period_locations as {
    left?: Record<string, unknown>[]
    right?: Record<string, unknown>[]
  } | undefined
  return { left: locations?.left || [], right: locations?.right || [] }
})
const comparisonMovement = computed(() => {
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
const comparisonPitchMix = computed(() => {
  const pitchMix = overview.value?.charts?.period_pitch_mix as {
    left?: { rows?: Record<string, unknown>[]; total?: number }
    right?: { rows?: Record<string, unknown>[]; total?: number }
  } | undefined
  return {
    left: { rows: pitchMix?.left?.rows || [], total: Number(pitchMix?.left?.total || 0) },
    right: { rows: pitchMix?.right?.rows || [], total: Number(pitchMix?.right?.total || 0) }
  }
})
const comparisonPitchOptions = computed(() => {
  const rows = [...comparisonPitchMix.value.left.rows, ...comparisonPitchMix.value.right.rows]
  return [...new Set(rows.map((row) => String(row.pitch || row.pitch_name || row.Pitch || '')).filter(Boolean))].sort()
})
const comparisonDiscipline = computed(() => {
  const discipline = overview.value?.charts?.period_discipline as {
    left?: { panel_groups?: Record<string, unknown>; total?: number }
    right?: { panel_groups?: Record<string, unknown>; total?: number }
  } | undefined
  return {
    left: { panel_groups: discipline?.left?.panel_groups || {}, total: Number(discipline?.left?.total || 0) },
    right: { panel_groups: discipline?.right?.panel_groups || {}, total: Number(discipline?.right?.total || 0) }
  }
})
const comparisonVideos = computed(() => {
  const videos = overview.value?.charts?.period_videos as {
    left?: { rows?: Record<string, unknown>[]; total?: number }
    right?: { rows?: Record<string, unknown>[]; total?: number }
  } | undefined
  return {
    left: { rows: videos?.left?.rows || [], total: Number(videos?.left?.total || 0) },
    right: { rows: videos?.right?.rows || [], total: Number(videos?.right?.total || 0) }
  }
})
const selectedLeftLocationKey = computed(() => selectedLeftPitch.value ? pitchPointKey(selectedLeftPitch.value) : null)
const selectedRightLocationKey = computed(() => selectedRightPitch.value ? pitchPointKey(selectedRightPitch.value) : null)

watch(leftAllPitchers, (pitchers) => {
  if (!pitchers.length) {
    leftPitcherId.value = null
    return
  }
  if (!leftPitcherId.value || !pitchers.some((pitcher) => pitcher.player_id === leftPitcherId.value)) {
    leftPitcherId.value = pitchers[0]?.player_id ?? null
  }
}, { immediate: true })

watch(rightAllPitchers, (pitchers) => {
  if (!pitchers.length) {
    rightPitcherId.value = null
    return
  }
  if (!rightPitcherId.value || !pitchers.some((pitcher) => pitcher.player_id === rightPitcherId.value)) {
    rightPitcherId.value = pitchers[1]?.player_id ?? pitchers[0]?.player_id ?? null
  }
}, { immediate: true })

watch([leftTeam, leftPitcherOptions], ([, pitchers]) => {
  if (!pitchers.length) {
    leftPitcherId.value = null
    return
  }
  if (!leftPitcherId.value || !pitchers.some((pitcher) => pitcher.player_id === leftPitcherId.value)) {
    leftPitcherId.value = pitchers[0]?.player_id ?? null
  }
})

watch([rightTeam, rightPitcherOptions], ([, pitchers]) => {
  if (!pitchers.length) {
    rightPitcherId.value = null
    return
  }
  if (!rightPitcherId.value || !pitchers.some((pitcher) => pitcher.player_id === rightPitcherId.value)) {
    rightPitcherId.value = pitchers[0]?.player_id ?? null
  }
})

watch(leftYear, async () => {
  overview.value = null
  leftTeam.value = 'All'
  await refreshLeftOptions()
})

watch(rightYear, async () => {
  overview.value = null
  rightTeam.value = 'All'
  await refreshRightOptions()
})

watch([
  leftYear,
  rightYear,
  leftPitcherId,
  rightPitcherId,
  comparisonStandFilter,
  comparisonCountFilter,
  comparisonPitchFilter,
  comparisonPitchResultFilter,
  comparisonInPlayResultFilter,
  comparisonPaResultFilter
], async () => {
  if (!leftPitcherId.value || !rightPitcherId.value) {
    overview.value = null
    return
  }
  pending.value = true
  errorMessage.value = ''
  try {
    overview.value = await api.comparisonPersonalOverview({
      leftYear: leftYear.value,
      rightYear: rightYear.value,
      leftPitcherId: leftPitcherId.value,
      rightPitcherId: rightPitcherId.value,
      stand: toFilterParam(comparisonStandFilter.value),
      count: toFilterParam(comparisonCountFilter.value),
      pitch: toFilterParam(comparisonPitchFilter.value),
      pitchResult: toFilterParam(comparisonPitchResultFilter.value),
      inPlayResult: toFilterParam(comparisonInPlayResultFilter.value),
      paResult: toFilterParam(comparisonPaResultFilter.value)
    })
    selectedLeftPitch.value = null
    selectedRightPitch.value = null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load comparison.'
  } finally {
    pending.value = false
  }
}, { immediate: true })

function toFilterParam(value: string) {
  return value && value !== 'All' ? value : undefined
}

function selectComparisonPitch(side: 'A' | 'B', point: Record<string, unknown>) {
  if (side === 'A') {
    selectedLeftPitch.value = point
    return
  }
  selectedRightPitch.value = point
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
</script>

<style scoped>
.comparison-page {
  max-width: 1360px;
  margin: 0 auto;
  padding: 104px 20px 56px;
}

.selector-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.selector-panel {
  display: grid;
  grid-template-columns: 112px 150px 330px 32px 112px 150px 330px;
  gap: 14px;
  align-items: end;
  justify-content: space-between;
  margin-top: 16px;
  padding: 18px;
}

.selector-spacer {
  min-width: 0;
}

label {
  display: grid;
  gap: 7px;
  color: var(--color-foreground);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

select {
  width: 100%;
  min-height: 42px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 0 12px;
  color: var(--color-text);
  background: var(--color-surface);
}

.selector-panel strong {
  padding-bottom: 10px;
  color: var(--color-muted-text);
  font-size: 13px;
}

.comparison-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 44px;
  gap: 18px;
  align-items: start;
  transition: grid-template-columns 160ms ease;
}

.comparison-workspace.filters-open {
  grid-template-columns: minmax(0, 1fr) 300px;
}

.comparison-main {
  min-width: 0;
}

.comparison-filter-rail {
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

.comparison-filter-rail.open {
  padding: 14px;
}

.comparison-filter-rail h2 {
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

.comparison-filter-rail.open .filter-fields {
  display: grid;
}

@media (max-width: 940px) {
  .selector-panel,
  .comparison-workspace {
    grid-template-columns: 1fr;
  }

  .comparison-filter-rail {
    position: static;
  }

  .filter-fields,
  .comparison-filter-rail.open .filter-fields {
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
