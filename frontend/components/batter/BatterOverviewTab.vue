<template>
  <div class="overview-layout">
    <div class="overview-right">
      <section class="kpi-grid">
        <article v-for="metric in featuredMetrics" :key="metric.label"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><small>{{ metric.note }}</small></article>
      </section>
      <BatterTimingFingerprint class="compact-fingerprint" :timing="timing" :loading="timingLoading" />
      <BatterTrendChart class="compact-trend" :rows="gameLog.rows" />
    </div>
    <BatterPercentileProfile class="percentile-panel" :year="overview?.meta.year || 0" :metrics="percentileMetrics" />
    <section class="panel pitch-panel">
      <header><div><span>Attack map</span><h2>Performance by pitch type</h2></div><small>{{ pitchMix.rows.length }} pitch types</small></header>
      <div class="pitch-list">
        <div class="pitch-head"><span>Pitch</span><span>Usage</span><span>AVG</span><span>Whiff</span><span>Hard hit</span></div>
        <div v-for="pitchRow in pitchMix.rows.slice(0, 8)" :key="String(pitchRow.Pitch)">
          <strong><i :style="{ background: pitchColor(String(pitchRow.Pitch)) }" />{{ pitchRow.Pitch }}</strong>
          <span>{{ percentValue(pitchRow['Usage%']) }}</span><span>{{ pitchRow.AVG ?? '-' }}</span><span>{{ percentValue(pitchRow['Whiff%']) }}</span><span>{{ percentValue(pitchRow['HH%']) }}</span>
        </div>
      </div>
    </section>
    <section class="panel recent-panel">
      <header><div><span>Latest games</span><h2>Recent results</h2></div><small>{{ gameLog.rows.length }} games</small></header>
      <div class="game-list">
        <article v-for="game in gameLog.rows.slice(0, 7)" :key="String(game.Date)"><time>{{ formatDate(game.Date) }}</time><strong>vs {{ game.Opponent }}</strong><span>{{ game.H }}-for-{{ game.AB }}</span><b :class="{ positive: Number(game.HR) > 0 }">{{ Number(game.HR) > 0 ? `${game.HR} HR` : `${game.SO} K` }}</b></article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { AnalysisResponse, SwingTimingPlayerDetailResponse, TablePayload } from '~/types/api'
import type { BatterPercentileMetric } from './BatterPercentileProfile.vue'

const props = withDefaults(defineProps<{ overview: AnalysisResponse | null; timing?: SwingTimingPlayerDetailResponse | null; timingLoading?: boolean }>(), { timing: null, timingLoading: false })
const empty: TablePayload = { columns: [], rows: [] }
const dashboard = computed(() => props.overview?.tables?.dashboard || empty)
const gameLog = computed(() => props.overview?.tables?.season_game_log || empty)
const pitchMix = computed(() => props.overview?.tables?.pitch_mix || empty)
const dashboardRow = computed(() => dashboard.value.rows[0] || {})
const percentileMetrics = computed(() => { const metrics = props.overview?.charts?.percentile_profile; return Array.isArray(metrics) ? metrics as BatterPercentileMetric[] : [] })
const featuredMetrics = computed(() => [
  { label: 'OPS', value: rate(dashboardRow.value.OPS), note: `${rate(dashboardRow.value.OBP)} OBP · ${rate(dashboardRow.value.SLG)} SLG` },
  { label: 'wOBA', value: rate(dashboardRow.value.wOBA), note: `${signedGap(dashboardRow.value.wOBA, dashboardRow.value.xwOBA)} vs expected` },
  { label: 'xwOBA', value: rate(dashboardRow.value.xwOBA), note: `${rate(dashboardRow.value.xBA)} xBA · ${rate(dashboardRow.value.xSLG)} xSLG` },
  { label: 'Barrel%', value: percentValue(dashboardRow.value['Barrel%']), note: `${percentValue(dashboardRow.value['HH%'])} hard hit` },
  { label: 'K − BB', value: percentageGap(dashboardRow.value['K%'], dashboardRow.value['BB%']), note: `${percentValue(dashboardRow.value['K%'])} K · ${percentValue(dashboardRow.value['BB%'])} BB` }
])

function rate(value: unknown) { const number = Number(value); return Number.isFinite(number) ? number.toFixed(3) : '-' }
function percentValue(value: unknown) { const number = parsePercent(value); return number === null ? '-' : `${number.toFixed(1)}%` }
function signedGap(actual: unknown, expected: unknown) { const gap = Number(actual) - Number(expected); return Number.isFinite(gap) ? `${gap >= 0 ? '+' : ''}${gap.toFixed(3)}` : '-' }
function percentageGap(strikeout: unknown, walk: unknown) { const strikeoutRate = parsePercent(strikeout); const walkRate = parsePercent(walk); return strikeoutRate === null || walkRate === null ? '-' : `${(strikeoutRate - walkRate).toFixed(1)}%` }
function parsePercent(value: unknown) { if (value === null || value === undefined || value === '-') return null; const number = Number(String(value).replace('%', '').trim()); return Number.isFinite(number) ? number : null }
function formatDate(value: unknown) { const text = String(value || ''); const parts = text.split('-'); return parts.length === 3 ? `${parts[1]}/${parts[2]}` : text }
function pitchColor(pitch: string) { const colors: Record<string, string> = { '4-Seam Fastball': '#ef4444', Changeup: '#22c55e', Sinker: '#f97316', Cutter: '#8b6b4a', Sweeper: '#b58b2a', Slider: '#eab308', Curveball: '#3b82f6', 'Split-Finger': '#14b8a6' }; return colors[pitch] || '#94a3b8' }
</script>

<style scoped>
.overview-layout { display: grid; grid-template-columns: minmax(0, 1.22fr) minmax(340px, .78fr); align-items: stretch; gap: 16px; }
.overview-right { min-width: 0; display: grid; grid-template-rows: auto auto minmax(0, 1fr); gap: 12px; }
.percentile-panel { height: 100%; }
.kpi-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.kpi-grid article, .panel { border: 1px solid var(--color-border); border-radius: 0; background: var(--color-surface); box-shadow: var(--shadow-sm); }
.kpi-grid article { display: grid; gap: 3px; min-height: 92px; padding: 11px 12px; }
.kpi-grid span, .panel header span { color: var(--color-muted-text); font-size: 11px; font-weight: 850; letter-spacing: .05em; text-transform: uppercase; }
.kpi-grid strong { color: var(--color-foreground); font: 700 clamp(21px, 1.8vw, 30px) "Fira Code", monospace; }
.kpi-grid small { color: var(--color-muted-text); font-size: 11px; }
.compact-fingerprint { grid-column: auto; }
.compact-fingerprint :deep(.fingerprint > header) { padding: 11px 13px; }
.compact-fingerprint :deep(.fingerprint h2) { font-size: 18px; }
.compact-fingerprint :deep(.fingerprint header p) { font-size: 11px; }
.compact-fingerprint :deep(.metrics article) { padding: 10px 11px; }
.compact-fingerprint :deep(.metrics strong) { font-size: 20px; }
.compact-trend :deep(.trend-card > header) { padding: 11px 13px; }
.compact-trend :deep(.trend-card h2) { font-size: 18px; }
.compact-trend :deep(.trend-card header span), .compact-trend :deep(.metric-switch button) { font-size: 11px; }
.compact-trend :deep(.metric-switch button) { min-height: 32px; padding: 5px 9px; }
.compact-trend :deep(.chart-wrap) { min-height: 260px; padding: 8px 10px 2px; }
.compact-trend, .compact-trend :deep(.trend-card) { height: 100%; }
.panel { min-width: 0; overflow: hidden; }
.panel > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 13px 15px; border-bottom: 1px solid var(--color-border); }
.panel h2 { margin: 3px 0 0; color: var(--color-foreground); font-size: 20px; }
.panel header small { color: var(--color-muted-text); font-size: 12px; }
.pitch-list { display: grid; padding: 4px 13px 10px; }
.pitch-list > div { display: grid; grid-template-columns: minmax(150px, 1.4fr) repeat(4, minmax(64px, .7fr)); align-items: center; gap: 8px; min-height: 48px; border-bottom: 1px solid var(--color-border); font: 600 14px "Fira Code", monospace; }
.pitch-list > div > span { text-align: right; }
.pitch-list strong { display: flex; align-items: center; gap: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: "Fira Sans", sans-serif; }
.pitch-list i { width: 8px; height: 8px; flex: 0 0 auto; border-radius: 50%; }
.pitch-head { color: var(--color-muted-text); font-size: 12px !important; font-weight: 850 !important; text-transform: uppercase; }
.game-list { display: grid; }
.game-list article { display: grid; grid-template-columns: 54px minmax(80px, 1fr) 66px 66px; align-items: center; gap: 8px; min-height: 54px; padding: 8px 14px; border-bottom: 1px solid var(--color-border); font-size: 14px; }
.game-list time, .game-list span { color: var(--color-muted-text); font-family: "Fira Code", monospace; }
.game-list b { border-radius: 0; padding: 5px 7px; color: var(--color-muted-text); background: var(--color-muted); font-size: 12px; text-align: center; }
.game-list b.positive { color: #111; background: var(--color-primary); }
@media (max-width: 1100px) { .overview-layout { grid-template-columns: 1fr; } .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 620px) { .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .kpi-grid article:first-child { grid-column: 1 / -1; } .pitch-list { overflow-x: auto; } .pitch-list > div { min-width: 520px; } }
</style>
