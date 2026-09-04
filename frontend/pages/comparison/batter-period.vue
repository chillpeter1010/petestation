<template>
  <main class="batter-period-page">
    <ComparisonPageHeader
      eyebrow="Batter comparison"
      title="Batter Period Comparison"
      description="One hitter, two date windows, one shared context. Period B minus Period A is shown in the delta column."
      back-to="/batters/comparison"
      back-label="Batter comparison"
    />

    <section class="selector-panel">
      <label>
        Directory year
        <select v-model.number="directoryYear">
          <option v-for="year in yearOptions" :key="year" :value="year">{{ year }}</option>
        </select>
      </label>
      <label>
        Team
        <select v-model="team">
          <option value="All">All teams</option>
          <option v-for="value in teamOptions" :key="value" :value="value">{{ value }}</option>
        </select>
      </label>
      <label>
        Batter
        <select v-model.number="batterId">
          <option :value="null">Select batter</option>
          <option v-for="batter in batterOptions" :key="batter.value" :value="batter.value">{{ batter.label }}</option>
        </select>
      </label>
    </section>

    <section class="period-panel">
      <div class="period-group">
        <h2>Period A</h2>
        <label>Year<select v-model.number="leftYear"><option v-for="year in yearOptions" :key="year" :value="year">{{ year }}</option></select></label>
        <label>Start<input v-model="leftStart" type="date"></label>
        <label>End<input v-model="leftEnd" type="date"></label>
      </div>
      <div class="period-group">
        <h2>Period B</h2>
        <label>Year<select v-model.number="rightYear"><option v-for="year in yearOptions" :key="year" :value="year">{{ year }}</option></select></label>
        <label>Start<input v-model="rightStart" type="date"></label>
        <label>End<input v-model="rightEnd" type="date"></label>
      </div>
    </section>

    <section class="filter-panel">
      <label>Batter side<select v-model="batterSide"><option v-for="value in filterOptions.batter_side" :key="value" :value="value">{{ value }}</option></select></label>
      <label>Pitcher hand<select v-model="pitcherHand"><option v-for="value in filterOptions.pitcher_hand" :key="value" :value="value">{{ value }}</option></select></label>
      <label>Pitch family<select v-model="pitchFamily"><option v-for="value in filterOptions.pitch_family" :key="value" :value="value">{{ value }}</option></select></label>
      <label>Count<select v-model="count"><option v-for="value in filterOptions.count" :key="value" :value="value">{{ value }}</option></select></label>
      <label>Pitch<select v-model="pitch"><option v-for="value in filterOptions.pitch" :key="value" :value="value">{{ value }}</option></select></label>
      <label>Pitch result<select v-model="pitchResult"><option v-for="value in filterOptions.pitch_result" :key="value" :value="value">{{ displayFilter(value) }}</option></select></label>
      <button type="button" :disabled="!canApply || pending" @click="loadComparison">{{ pending ? 'Loading…' : 'Apply comparison' }}</button>
    </section>

    <ComparisonStatus :pending="pending" :error="errorMessage" label="Recalculating both batter periods…" />

    <template v-if="comparison">
      <section class="period-summary" aria-label="Selected periods">
        <article><span>Period A</span><strong>{{ leftStart }} – {{ leftEnd }}</strong><small>{{ comparison.periods.left.pitches.toLocaleString() }} pitches</small></article>
        <article><span>Period B</span><strong>{{ rightStart }} – {{ rightEnd }}</strong><small>{{ comparison.periods.right.pitches.toLocaleString() }} pitches</small></article>
      </section>

      <section v-for="group in metricGroups" :key="group.key" class="metrics-panel">
        <header><span>{{ group.eyebrow }}</span><h2>{{ group.title }}</h2></header>
        <div class="metrics-table" role="table" :aria-label="group.title">
          <div class="metric-row metric-head" role="row">
            <b>Metric</b><b>Period A</b><b>Period B</b><b>Δ B − A</b><b>Denominator A / B</b>
          </div>
          <div v-for="metric in metricsByGroup(group.key)" :key="metric.key" class="metric-row" role="row">
            <strong>{{ metric.label }}</strong>
            <span>{{ formatValue(metric.period_a, metric.unit) }}</span>
            <span>{{ formatValue(metric.period_b, metric.unit) }}</span>
            <span class="delta-value">{{ formatDelta(metric.delta, metric.delta_unit) }}</span>
            <small>{{ metric.denominator_label }} · {{ metric.period_a_denominator.toLocaleString() }} / {{ metric.period_b_denominator.toLocaleString() }}</small>
          </div>
        </div>
      </section>

      <BatterPeriodHeatmaps
        :left-points="comparison.heatmaps.left"
        :right-points="comparison.heatmaps.right"
        :bat-speed-domain="comparison.bat_speed_domain"
      />

      <section class="timing-reference">
        <header><span>Slice 5 · Summary boundary</span><h2>Season timing reference</h2><p>These X/Y/Z values come from full-season Savant summaries. They are intentionally separate from arbitrary-period deltas.</p></header>
        <div class="timing-grid">
          <article v-for="side in (['left', 'right'] as const)" :key="side">
            <strong>{{ side === 'left' ? 'Period A season' : 'Period B season' }} · {{ comparison.timing_reference[side].year }}</strong>
            <small>{{ comparison.timing_reference[side].n_swings.toLocaleString() }} summary swings · {{ comparison.timing_reference[side].mode }}</small>
            <div><span v-for="(value, key) in comparison.timing_reference[side].metrics" :key="key"><b>{{ timingLabel(key) }}</b>{{ timingValue(key, value) }}</span></div>
          </article>
        </div>
      </section>

      <section class="source-audit">
        <header><span>Slice 6 · Source audit</span><h2>Exact visuals & batting stance coverage</h2></header>
        <div class="audit-grid">
          <article><strong>Exact X/Y/Z distributions</strong><p>{{ auditReason('exact_timing_distributions') }}</p></article>
          <article><strong>Batting stance / foot positions</strong><p>{{ auditReason('batting_stance') }}</p></article>
          <article><strong>Squared-Up / Blast</strong><p>{{ auditReason('squared_up_and_blast') }}</p></article>
          <article><strong>Intercept geometry</strong><p>Available as swing geometry only; it is not labeled as stance.</p><small>A · {{ interceptValue('left', 'intercept_x_inches') }} x / {{ interceptValue('left', 'intercept_y_inches') }} y<br>B · {{ interceptValue('right', 'intercept_x_inches') }} x / {{ interceptValue('right', 'intercept_y_inches') }} y</small></article>
        </div>
      </section>

      <ComparisonNotes :notes="comparison.meta.warnings" />
    </template>
  </main>
</template>

<script setup lang="ts">
import type { BatterOption, BatterPeriodComparisonResponse, BatterPeriodMetric } from '~/types/api'

const activeRoute = useRoute()
if (activeRoute.path === '/comparison/batter-period') {
  await navigateTo('/batters/comparison/period', { redirectCode: 301 })
}

const api = useApi()
const directoryYear = ref(2026)
const leftYear = ref(2026)
const rightYear = ref(2026)
const team = ref('All')
const batterId = ref<number | null>(null)
const leftStart = ref('2026-03-01')
const leftEnd = ref('2026-05-31')
const rightStart = ref('2026-06-01')
const rightEnd = ref('2026-07-31')
const batterSide = ref('All')
const pitcherHand = ref('All')
const pitchFamily = ref('All')
const count = ref('All')
const pitch = ref('All')
const pitchResult = ref('All')
const comparison = ref<BatterPeriodComparisonResponse | null>(null)
const pending = ref(false)
const errorMessage = ref('')

const { data: options, refresh: refreshOptions } = await useAsyncData(
  () => `batter-period-options-${directoryYear.value}`,
  () => api.batterPeriodOptions(directoryYear.value),
  { default: () => ({ meta: { year: directoryYear.value, data_updated_at: null, warnings: [] }, years: [directoryYear.value], batters: [] }) }
)

const yearOptions = computed(() => options.value.years.length ? options.value.years : [directoryYear.value])
const allBatters = computed<BatterOption[]>(() => options.value.batters)
const teamOptions = computed(() => [...new Set(allBatters.value.map((batter) => batter.team).filter(Boolean))].sort())
const batterOptions = computed(() => team.value === 'All' ? allBatters.value : allBatters.value.filter((batter) => batter.team === team.value))
const canApply = computed(() => Boolean(batterId.value && leftStart.value && leftEnd.value && rightStart.value && rightEnd.value))
const filterOptions = computed(() => comparison.value?.filters || {
  batter_side: ['All', 'L', 'R'], pitcher_hand: ['All', 'L', 'R'], pitch_family: ['All', 'Fastball', 'Breaking', 'Offspeed', 'Other'], count: ['All'], pitch: ['All'], pitch_result: ['All', 'Swing', 'Whiff', 'In Play']
})
const metricGroups = [
  { key: 'sample', eyebrow: 'Sample', title: 'Opportunities' },
  { key: 'production', eyebrow: 'Output', title: 'Production' },
  { key: 'contact', eyebrow: 'Batted ball', title: 'Contact quality' },
  { key: 'discipline', eyebrow: 'Decision & contact', title: 'Plate discipline' },
  { key: 'tracking', eyebrow: 'Slice 4', title: 'Bat Tracking' },
  { key: 'timing', eyebrow: 'Slice 5', title: 'Miss Distance' }
] as const

function metricsByGroup(group: BatterPeriodMetric['group']) {
  return comparison.value?.metrics.filter((metric) => metric.group === group) || []
}

async function loadDateRanges() {
  if (!batterId.value) return
  errorMessage.value = ''
  try {
    const [leftRange, rightRange] = await Promise.all([
      api.batterPeriodDateRange({ year: leftYear.value, batterId: batterId.value }),
      api.batterPeriodDateRange({ year: rightYear.value, batterId: batterId.value })
    ])
    if (leftYear.value === rightYear.value && leftRange.start_date && leftRange.end_date) {
      const start = new Date(`${leftRange.start_date}T00:00:00Z`)
      const end = new Date(`${leftRange.end_date}T00:00:00Z`)
      const midpoint = new Date((start.getTime() + end.getTime()) / 2)
      const nextDay = new Date(midpoint.getTime() + 86400000)
      leftStart.value = leftRange.start_date
      leftEnd.value = midpoint.toISOString().slice(0, 10)
      rightStart.value = nextDay.toISOString().slice(0, 10)
      rightEnd.value = leftRange.end_date
    } else {
      if (leftRange.start_date) leftStart.value = leftRange.start_date
      if (leftRange.end_date) leftEnd.value = leftRange.end_date
      if (rightRange.start_date) rightStart.value = rightRange.start_date
      if (rightRange.end_date) rightEnd.value = rightRange.end_date
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load batter date range.'
  }
}

async function loadComparison() {
  if (!canApply.value || !batterId.value) return
  pending.value = true
  errorMessage.value = ''
  try {
    comparison.value = await api.batterPeriodOverview({
      batterId: batterId.value, leftYear: leftYear.value, rightYear: rightYear.value,
      leftStart: leftStart.value, leftEnd: leftEnd.value, rightStart: rightStart.value, rightEnd: rightEnd.value,
      batterSide: filterParam(batterSide.value), pitcherHand: filterParam(pitcherHand.value), pitchFamily: filterParam(pitchFamily.value), count: filterParam(count.value),
      pitch: filterParam(pitch.value), pitchResult: filterParam(pitchResult.value)
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load batter period comparison.'
  } finally {
    pending.value = false
  }
}

function filterParam(value: string) { return value && value !== 'All' ? value : undefined }
function displayFilter(value: string) { return value.includes('_') ? value.replaceAll('_', ' ') : value }
function timingLabel(key: string) { return key.replaceAll('_pct', '%').replaceAll('_', ' ') }
function timingValue(key: string, value: number | null) { return value === null ? '—' : key.includes('pct') ? `${value.toFixed(1)}%` : `${value.toFixed(2)} in` }
function auditReason(key: string) { return String((comparison.value?.source_audit[key] as { reason?: string } | undefined)?.reason || 'Coverage details unavailable.') }
function interceptValue(side: 'left' | 'right', key: string) { const audit = comparison.value?.source_audit.intercept_geometry as { left?: Record<string, number | null>; right?: Record<string, number | null> } | undefined; const value = Number(audit?.[side]?.[key]); return Number.isFinite(value) ? `${value.toFixed(2)} in` : '—' }

function formatValue(value: number | null, unit: BatterPeriodMetric['unit']) {
  if (value === null || !Number.isFinite(value)) return '—'
  if (unit === 'count') return Math.round(value).toLocaleString()
  if (unit === 'pct') return `${value.toFixed(1)}%`
  if (unit === 'mph') return `${value.toFixed(1)} mph`
  if (unit === 'ft') return `${value.toFixed(2)} ft`
  if (unit === 'in') return `${value.toFixed(2)} in`
  return value.toFixed(3).replace(/^0/, '')
}

function formatDelta(value: number | null, unit: BatterPeriodMetric['delta_unit']) {
  if (value === null || !Number.isFinite(value)) return '—'
  const sign = value > 0 ? '+' : ''
  if (unit === 'count') return `${sign}${Math.round(value).toLocaleString()}`
  if (unit === 'pp') return `${sign}${value.toFixed(1)} pp`
  if (unit === 'mph') return `${sign}${value.toFixed(1)} mph`
  if (unit === 'ft') return `${sign}${value.toFixed(2)} ft`
  if (unit === 'in') return `${sign}${value.toFixed(2)} in`
  return `${sign}${value.toFixed(3)}`
}

watch(directoryYear, async (year) => {
  team.value = 'All'
  batterId.value = null
  comparison.value = null
  leftYear.value = year
  rightYear.value = year
  await refreshOptions()
})

watch(batterOptions, (batters) => {
  if (batterId.value && !batters.some((batter) => batter.value === batterId.value)) batterId.value = null
}, { immediate: true })

watch([batterId, leftYear, rightYear], async () => {
  comparison.value = null
  await loadDateRanges()
})
</script>

<style scoped>
.batter-period-page { max-width: 1280px; margin: 0 auto; padding: 104px 20px 56px; }
.selector-panel, .period-panel, .filter-panel, .period-summary, .metrics-panel { margin-top: 16px; border: 1px solid var(--color-border); border-radius: 0; background: var(--color-surface); box-shadow: var(--shadow-sm); }
.selector-panel { display: grid; grid-template-columns: 140px 180px minmax(260px, 1fr); gap: 14px; padding: 18px; }
.period-panel { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; padding: 18px; }
.period-group { display: grid; grid-template-columns: 90px repeat(2, minmax(0, 1fr)); gap: 12px; align-items: end; }
.period-group h2 { grid-column: 1 / -1; margin: 0; color: var(--color-foreground); font-size: 15px; }
.filter-panel { display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 12px; align-items: end; padding: 16px; }
label { display: grid; gap: 7px; color: var(--color-foreground); font-size: 11px; font-weight: 850; text-transform: uppercase; }
select, input { width: 100%; min-height: 42px; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 10px; color: var(--color-text); background: var(--color-surface); }
.filter-panel button { min-height: 42px; border: 1px solid var(--color-primary); border-radius: 0; padding: 0 16px; color: var(--color-on-primary); background: var(--color-primary); cursor: pointer; font-weight: 850; }
.filter-panel button:disabled { cursor: not-allowed; opacity: .55; }
.period-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.period-summary article { display: grid; gap: 4px; padding: 14px 16px; }
.period-summary article + article { border-left: 1px solid var(--color-border); }
.period-summary span, .metrics-panel header span { color: var(--color-primary); font-size: 11px; font-weight: 850; text-transform: uppercase; }
.period-summary strong { color: var(--color-foreground); }
.period-summary small { color: var(--color-muted-text); }
.metrics-panel header { padding: 14px 16px; border-bottom: 1px solid var(--color-border); }
.metrics-panel h2 { margin: 3px 0 0; color: var(--color-foreground); font-size: 19px; }
.metric-row { display: grid; grid-template-columns: minmax(120px, .8fr) repeat(3, minmax(100px, .65fr)) minmax(210px, 1.1fr); gap: 12px; align-items: center; min-height: 44px; padding: 8px 16px; border-bottom: 1px solid var(--color-border); color: var(--color-text); }
.metric-row:last-child { border-bottom: 0; }
.metric-head { min-height: 36px; color: var(--color-muted-text); background: var(--color-plot-bg); font-size: 11px; text-transform: uppercase; }
.metric-row small { color: var(--color-muted-text); }
.delta-value { color: var(--color-primary); font-weight: 800; }
.timing-reference, .source-audit { margin-top: 18px; border: 1px solid var(--color-border); background: var(--color-surface); }
.timing-reference > header, .source-audit > header { padding: 14px 16px; border-bottom: 1px solid var(--color-border); }
.timing-reference header span, .source-audit header span { color: var(--color-primary); font-size: 11px; font-weight: 850; text-transform: uppercase; }
.timing-reference h2, .source-audit h2 { margin: 3px 0 0; color: var(--color-foreground); }
.timing-reference header p { margin: 4px 0 0; color: var(--color-muted-text); }
.timing-grid, .audit-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: var(--color-border); }
.timing-grid article, .audit-grid article { padding: 14px 16px; background: var(--color-surface); }
.timing-grid article > strong, .timing-grid article > small { display: block; }
.timing-grid small, .audit-grid p { margin-top: 4px; color: var(--color-muted-text); font-size: 12px; }
.timing-grid article > div { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.timing-grid span { display: grid; gap: 3px; padding: 8px; border: 1px solid var(--color-border); font-size: 12px; }
.timing-grid b { color: var(--color-muted-text); font-size: 10px; text-transform: uppercase; }

@media (max-width: 980px) {
  .selector-panel, .period-panel, .filter-panel { grid-template-columns: 1fr 1fr; }
  .metric-row { grid-template-columns: minmax(100px, 1fr) repeat(3, minmax(82px, .7fr)); }
  .metric-row > small { grid-column: 1 / -1; }
}

@media (max-width: 680px) {
  .selector-panel, .period-panel, .period-group, .filter-panel, .period-summary { grid-template-columns: 1fr; }
  .period-summary article + article { border-left: 0; border-top: 1px solid var(--color-border); }
  .metrics-table { overflow-x: auto; }
  .metric-row { min-width: 720px; }
}
</style>
