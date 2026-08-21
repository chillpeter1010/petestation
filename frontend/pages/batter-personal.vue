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
      <button type="button" :class="{ active: activeTab === 'discipline' }" @click="activeTab = 'discipline'"><ScanSearch :size="17" aria-hidden="true" />Discipline & zones</button>
    </nav>

    <div v-if="pending" class="loading-grid" aria-label="Loading batter page"><span v-for="item in 5" :key="item" /></div>
    <p v-else-if="!selectedBatterId" class="state-card">Select a batter to load the page.</p>
    <BatterOverviewTab v-else-if="activeTab === 'overview'" :overview="overview" />

    <template v-else>
      <section class="discipline-filters">
        <label><span>Stand</span><select v-model="stand"><option v-for="option in standOptions" :key="option" :value="option">{{ option }}</option></select></label>
        <label><span>Count</span><select v-model="count"><option v-for="option in countOptions" :key="option" :value="option">{{ option }}</option></select></label>
        <label><span>Pitch</span><select v-model="pitch"><option v-for="option in pitchOptions" :key="option" :value="option">{{ option }}</option></select></label>
        <label><span>Pitch result</span><select v-model="pitchResult"><option v-for="option in pitchResultOptions" :key="option" :value="option">{{ option }}</option></select></label>
        <label><span>Start date</span><input v-model="startDate" type="date"></label>
        <label><span>End date</span><input v-model="endDate" type="date"></label>
        <button type="button" @click="clearDates">Clear dates</button>
      </section>

      <SummaryCards class="discipline-summary" :metrics="discipline?.summary || []" />
      <section class="discipline-visual-section">
        <header class="section-heading">
          <div><span>Visual analysis</span><h2>Location & zone views</h2></div>
          <p>Pitch-level visuals for the active filters.</p>
        </header>
        <article class="chart-card">
          <header>
            <div><span>Pitch map</span><h2>Location profile</h2><p>Batter-side view for the active filters.</p></div>
            <span>{{ locationPoints.length.toLocaleString() }} pitches</span>
          </header>
          <StrikeZoneScatter class="batter-location-chart" :points="locationPoints" title="Batter Location" />
        </article>
        <DisciplinePanelBoard
          :heatmap-blend="0"
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
  </main>
</template>

<script setup lang="ts">
import { LayoutDashboard, ScanSearch, SlidersHorizontal } from '@lucide/vue'
import type { AnalysisResponse, BatterOption, TablePayload } from '~/types/api'
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
const pending = ref(false)
const activeTab = ref<'overview' | 'discipline'>('overview')

const stand = ref('All')
const count = ref('All')
const pitch = ref('All')
const pitchResult = ref('All')
const startDate = ref('')
const endDate = ref('')

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
const resultPanels = computed(() => panelsFromGroup('result', 'pitch_result'))
const paResultPanels = computed(() => panelsFromGroup('result', 'pa_result'))
const battedBallPanels = computed(() => panelsFromGroup('result', 'batted_ball'))
const countSituationPanels = computed(() => panelsFromGroup('discipline', 'count_situation'))
const countSwingPanels = computed(() => panelsFromGroup('discipline', 'count_swing'))
const exactCountPanels = computed(() => panelsFromGroup('situation', 'exact_count'))

watch([year, team], loadBatters, { immediate: true })
watch(selectedBatterId, async () => {
  syncRoute()
  await loadPayloads()
})
watch(activeTab, (tab) => {
  if (tab === 'discipline' && !discipline.value) loadDiscipline()
})
watch([stand, count, pitch, pitchResult, startDate, endDate], () => {
  if (activeTab.value === 'discipline') loadDiscipline()
})

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
    return
  }
  discipline.value = null
  await loadOverview()
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
}

function disciplineTable(key: string): TablePayload {
  return discipline.value?.tables?.[key] || emptyTable
}

function panelsFromGroup(groupKey: string, sectionKey: string): DisciplinePanel[] {
  const groups = asRecord(discipline.value?.charts?.panel_groups)
  const group = asRecord(groups[groupKey])
  const section = asRecord(group[sectionKey])
  return toRows(section.panels).map(normalizeDisciplinePanel)
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

function syncRoute() {
  router.replace({
    query: {
      ...route.query,
      year: String(year.value),
      team: team.value,
      batter_id: selectedBatterId.value ? String(selectedBatterId.value) : undefined
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
  display: grid;
  gap: 16px;
  min-height: 100vh;
  padding: 76px clamp(16px, 3vw, 44px) 60px;
  color: var(--color-text);
}
.selector-panel {
  display: grid;
  grid-template-columns: minmax(190px, .65fr) 130px 170px minmax(220px, 1fr);
  align-items: end;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
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
  border-radius: 8px;
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
  border-radius: 12px;
  padding: 5px;
  background: var(--color-surface);
}
.tabs button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  border: 1px solid transparent;
  border-radius: 8px;
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
.discipline-table-section {
  display: grid;
  gap: 16px;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  padding: 18px;
  background: color-mix(in srgb, var(--color-surface) 94%, transparent);
  box-shadow: var(--shadow-sm);
}
.discipline-table-section {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.section-heading { grid-column: 1 / -1; display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; padding: 2px 2px 8px; }
.section-heading span { color: var(--color-primary); font-size: 16px; font-weight: 900; letter-spacing: .07em; text-transform: uppercase; }
.section-heading h2 { margin: 5px 0 0; color: var(--color-foreground); font-size: 30px; }
.section-heading p { margin: 0; color: var(--color-muted-text); font-size: 17px; }
.chart-card {
  grid-column: 1 / -1;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}
.full-width { grid-column: 1 / -1; }
.chart-card header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 16px 18px;
}
.chart-card h2 { margin: 3px 0 0; color: var(--color-foreground); font-size: 28px; }
.chart-card header div > span { color: var(--color-primary); font-size: 15px; font-weight: 900; letter-spacing: .07em; text-transform: uppercase; }
.chart-card p,
.chart-card header > span,
.state-card { color: var(--color-muted-text); }
.chart-card p, .chart-card header > span { margin: 5px 0 0; font-size: 17px; }
.batter-location-chart { width: 68%; min-width: 700px; max-width: 920px; margin: 22px auto; }
.discipline-table--wide { grid-column: 1 / -1; }
.discipline-summary :deep(.summary-card) { min-height: 122px; padding: 20px; }
.discipline-summary :deep(.summary-card span),
.discipline-summary :deep(.summary-card small) { font-size: 16px; }
.discipline-summary :deep(.summary-card strong) { font-size: 34px; }
.discipline-visual-section :deep(.board-header h2),
.discipline-visual-section :deep(.discipline-panel-section h3) { font-size: 24px; }
.discipline-visual-section :deep(.board-header p),
.discipline-visual-section :deep(.discipline-panel-section > header span),
.discipline-visual-section :deep(.segmented button) { font-size: 17px; }
.discipline-visual-section :deep(.panel-metrics dt),
.discipline-visual-section :deep(.panel-metrics dd),
.discipline-visual-section :deep(.pitch-legend) { font-size: 16px; }
.discipline-table :deep(.table-header) { padding: 18px 20px; }
.discipline-table :deep(.table-header h2) { font-size: 24px; }
.discipline-table :deep(.table-header span),
.discipline-table :deep(.empty) { font-size: 16px; }
.discipline-table :deep(.table-scroll) { max-width: 100%; overflow-x: auto; }
.discipline-table :deep(table) { width: max-content; min-width: 1350px; font-size: 18px; }
.discipline-table :deep(th),
.discipline-table :deep(td) { min-width: 120px; height: 58px; padding: 12px 16px; }
.discipline-table :deep(th:first-child),
.discipline-table :deep(td:first-child) { position: sticky; left: 0; z-index: 2; min-width: 190px; background: var(--color-surface); }
.discipline-table :deep(th:first-child) { z-index: 3; background: var(--color-muted); }
.discipline-table :deep(.sort-button) { font-size: 17px; }
.discipline-filters {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr)) repeat(2, minmax(145px, 1fr)) auto;
  align-items: end;
  gap: 10px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  padding: 14px;
  background: var(--color-surface);
}
.discipline-filters button {
  min-height: 44px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 0 14px;
  color: var(--color-foreground);
  background: var(--color-muted);
  cursor: pointer;
  font-weight: 800;
}
.state-card { margin: 0; border: 1px solid var(--color-border); border-radius: 14px; padding: 24px; background: var(--color-surface); }
.loading-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.loading-grid span { height: 110px; border-radius: 14px; background: linear-gradient(90deg, var(--color-surface), var(--color-muted), var(--color-surface)); background-size: 200% 100%; animation: shimmer 1.4s infinite; }
@keyframes shimmer { to { background-position: -200% 0; } }
@media (max-width: 1100px) {
  .selector-panel { grid-template-columns: 1fr 130px 170px; }
  .selector-panel__title { grid-column: 1 / -1; }
  .discipline-filters,
  .discipline-table-section {
    grid-template-columns: 1fr;
  }
  .discipline-table--wide { grid-column: auto; }
}
@media (max-width: 700px) { .batter-personal-page { padding-top: 24px; } .selector-panel { grid-template-columns: 1fr; } .loading-grid { grid-template-columns: 1fr 1fr; } .section-heading { align-items: flex-start; flex-direction: column; } .discipline-visual-section, .discipline-table-section { padding: 12px; } .batter-location-chart { width: 100%; min-width: 0; } }
@media (prefers-reduced-motion: reduce) { .loading-grid span { animation: none; } }
</style>
