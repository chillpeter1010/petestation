<template>
  <section class="outing-card">
    <header>
      <div>
        <span><ClipboardList :size="15" /> Previous start</span>
        <h3>Outing report</h3>
      </div>
      <NuxtLink v-if="report && gamePk" :to="reportLink">Full report <ArrowUpRight :size="14" /></NuxtLink>
    </header>

    <nav v-if="report" class="outing-card__tabs" aria-label="Outing report views">
      <button v-for="view in views" :key="view.value" type="button" :aria-pressed="activeView === view.value" @click="activeView = view.value">
        {{ view.label }}
      </button>
    </nav>

    <p v-if="loading" class="outing-card__empty">Loading previous outing…</p>
    <p v-else-if="!report" class="outing-card__empty">No previous start is available yet.</p>
    <template v-else>
      <template v-if="activeView === 'summary'">
        <div class="outing-card__hero">
          <div class="outing-card__hero-copy">
            <span>{{ metric('date') }} · {{ metric('opponent') }}</span>
            <h4>{{ pitcherName }}</h4>
            <p>{{ line }}</p>
          </div>
          <MlbPlayerHeadshot
            v-if="pitcherId"
            class="outing-card__headshot"
            :player-id="pitcherId"
            :name="pitcherName"
            :size="150"
            :source-width="320"
            priority
            decorative
            shape="circle"
          />
        </div>

        <div class="outing-card__scores">
          <article><span>Game score</span><strong>{{ metric('game_score') }}</strong></article>
          <article><span>CSW%</span><strong>{{ formatMetric('csw_pct', '%') }}</strong></article>
          <article><span>Zone%</span><strong>{{ formatMetric('zone_pct', '%') }}</strong></article>
          <article><span>Whiffs</span><strong>{{ metric('whiffs') }}</strong></article>
        </div>

        <div class="outing-card__context">
          <span>Catcher</span><strong>{{ metric('catcher_name') }}</strong>
        </div>

        <div v-if="pitchRows.length" class="outing-card__pitches">
          <div v-for="row in pitchRows" :key="String(row.Pitch)">
            <strong>{{ row.Pitch }}</strong>
            <span>{{ row['#'] }} pitches</span>
            <i><b :style="{ width: `${Number(row['Usage%']) || 0}%` }" /></i>
            <small>{{ formatValue(row['Usage%']) }}% usage · {{ formatValue(row.Velo) }} mph</small>
          </div>
        </div>
      </template>

      <div v-else-if="activeView === 'movement'" class="outing-card__visual">
        <MovementChart
          v-model:mode="movementMode"
          title="Movement profile"
          :scatter-rows="movementScatterRows"
          :summary-rows="movementSummaryRows"
          :league-rows="movementLeagueRows"
          :pitcher-hand="pitcherHand"
          :show-profile-info="false"
        />
      </div>

      <div v-else class="outing-card__locations">
        <StrikeZoneScatter title="Locations vs LHB" :points="locationByStand.L" :total-pitches="locationByStand.L.length" compact />
        <StrikeZoneScatter title="Locations vs RHB" :points="locationByStand.R" :total-pitches="locationByStand.R.length" compact />
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ArrowUpRight, ClipboardList } from '@lucide/vue'
import type { AnalysisResponse } from '~/types/api'

const props = defineProps<{
  report: AnalysisResponse | null
  loading: boolean
  pitcherName: string
  pitcherId: number | null
  gamePk: number | null
  year: number
}>()

type OutingView = 'summary' | 'movement' | 'locations'
const views: Array<{ value: OutingView; label: string }> = [
  { value: 'summary', label: 'Summary' },
  { value: 'movement', label: 'Movement' },
  { value: 'locations', label: 'Locations' }
]
const activeView = ref<OutingView>('summary')
const movementMode = ref<'scatter' | 'average'>('average')
const summary = computed(() => new Map((props.report?.summary || []).map(item => [item.key, item.value])))
const pitchRows = computed(() => (props.report?.tables.pitch_type_metrics?.rows || []).slice(0, 5))
const movementScatterRows = computed(() => rowsFrom(props.report?.charts.movement_scatter))
const movementSummaryRows = computed(() => props.report?.tables.movement_summary?.rows || [])
const movementLeagueRows = computed(() => props.report?.tables.movement_league_comparison?.rows || [])
const pitcherHand = computed(() => typeof props.report?.charts.pitcher_hand === 'string' ? props.report.charts.pitcher_hand : 'Unknown')
const locationByStand = computed(() => {
  const value = props.report?.charts.location_by_stand
  const record = value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
  return { L: rowsFrom(record.L), R: rowsFrom(record.R) }
})
const line = computed(() => `${metric('ip')} IP · ${metric('earned_runs')} ER · ${metric('hits')} H · ${metric('walks')} BB · ${metric('strikeouts')} K · ${metric('pitches')} P`)
const reportLink = computed(() => ({
  path: '/pitcher-personal',
  query: { year: props.year, pitcher_id: props.pitcherId, role: 'SP', tab: 'outing', game_pk: props.gamePk }
}))

function metric(key: string) { const value = summary.value.get(key); return value === null || value === undefined || value === '' ? '—' : String(value) }
function formatMetric(key: string, suffix = '') { const value = Number(summary.value.get(key)); return Number.isFinite(value) ? `${value.toFixed(1)}${suffix}` : '—' }
function formatValue(value: unknown) { const number = Number(value); return Number.isFinite(number) ? number.toFixed(1) : '—' }
function rowsFrom(value: unknown) { return Array.isArray(value) ? value.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object' && !Array.isArray(row)) : [] }

watch(() => props.gamePk, () => { activeView.value = 'summary' })
</script>

<style scoped>
.outing-card { min-width: 0; min-height: 100%; overflow: hidden; border: 1px solid var(--team-panel-border); border-radius: 14px; background: var(--color-surface); }
.outing-card > header { display: flex; justify-content: space-between; gap: 14px; border-bottom: 1px solid var(--team-panel-border); padding: 16px 18px; }
.outing-card > header span, .outing-card > header a { display: inline-flex; align-items: center; gap: 6px; color: var(--team-accent); font-size: 10px; font-weight: 900; letter-spacing: .07em; text-transform: uppercase; }
.outing-card > header h3 { margin: 4px 0 0; color: var(--color-text); font-size: 19px; }
.outing-card > header a { align-self: center; color: var(--color-muted-text); letter-spacing: 0; text-decoration: none; text-transform: none; }
.outing-card__tabs { display: flex; gap: 5px; border-bottom: 1px solid var(--team-panel-border); padding: 7px 10px; }
.outing-card__tabs button { min-height: 32px; border: 0; border-radius: 7px; padding: 6px 11px; color: var(--color-muted-text); background: transparent; font-size: 10px; font-weight: 900; cursor: pointer; }
.outing-card__tabs button[aria-pressed="true"] { color: #fff; background: var(--team-primary); }
.outing-card__hero { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 24px; min-height: 178px; padding: 20px 28px; color: #fff; background: radial-gradient(circle at 85% 0, color-mix(in srgb, var(--team-primary) 46%, transparent), transparent 48%), linear-gradient(135deg, color-mix(in srgb, var(--team-secondary) 50%, #090b10), #090b10); }
.outing-card__hero-copy { min-width: 0; }
.outing-card__hero span { color: color-mix(in srgb, var(--team-primary) 56%, #fff); font-size: 10px; font-weight: 900; text-transform: uppercase; }
.outing-card__hero h4 { margin: 8px 0 10px; font-size: clamp(25px, 3vw, 38px); line-height: 1; }
.outing-card__hero p { margin: 0; color: #cbd5e1; font: 700 12px "Fira Code", monospace; }
.outing-card__headshot { border: 2px solid color-mix(in srgb, var(--team-primary) 72%, #fff); color: var(--team-primary); background: color-mix(in srgb, var(--team-secondary) 55%, #0b0d13); box-shadow: 0 14px 34px rgb(0 0 0 / 32%); }
.outing-card__scores { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; border-bottom: 1px solid var(--team-panel-border); background: var(--team-panel-border); }
.outing-card__scores article { padding: 15px; background: var(--color-surface); }
.outing-card__scores span, .outing-card__context span { display: block; color: var(--color-muted-text); font-size: 9px; font-weight: 900; text-transform: uppercase; }
.outing-card__scores strong { display: block; margin-top: 7px; color: var(--color-text); font: 900 20px "Fira Code", monospace; }
.outing-card__context { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; }
.outing-card__context strong { color: var(--color-text); font-size: 12px; }
.outing-card__pitches { display: grid; gap: 11px; border-top: 1px solid var(--team-panel-border); padding: 18px; }
.outing-card__pitches > div { display: grid; grid-template-columns: minmax(100px, .7fr) auto; gap: 4px 12px; }
.outing-card__pitches strong { color: var(--color-text); font-size: 12px; }
.outing-card__pitches span, .outing-card__pitches small { color: var(--color-muted-text); font-size: 9px; text-align: right; }
.outing-card__pitches i { grid-column: 1 / -1; height: 7px; overflow: hidden; border-radius: 999px; background: var(--color-muted); }
.outing-card__pitches b { display: block; height: 100%; border-radius: inherit; background: var(--team-primary); }
.outing-card__pitches small { grid-column: 1 / -1; }
.outing-card__empty { padding: 32px 20px; color: var(--color-muted-text); }
.outing-card__visual { padding: 12px; }
.outing-card__visual :deep(.movement-chart) { border: 0; background: transparent; }
.outing-card__visual :deep(.plot-wrap), .outing-card__visual :deep(.profile-wrap) { display: grid; place-items: center; overflow: hidden; }
.outing-card__visual :deep(.scatter-svg), .outing-card__visual :deep(.profile-svg) { width: 100%; height: 390px; max-height: 42vh; }
.outing-card__locations { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; padding: 10px; }
.outing-card__locations :deep(.zone-chart) { min-width: 0; border-color: var(--team-panel-border); background: transparent; }
@media (max-width: 560px) {
  .outing-card__hero { gap: 14px; min-height: 144px; padding: 18px; }
  .outing-card__headshot { --headshot-size: 104px !important; }
  .outing-card__hero h4 { font-size: clamp(22px, 8vw, 31px); }
  .outing-card__hero p { font-size: 10px; }
  .outing-card__scores { grid-template-columns: 1fr 1fr; }
}
</style>
