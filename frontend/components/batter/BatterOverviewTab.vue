<template>
  <div class="overview-layout">
    <section class="kpi-grid">
      <article v-for="metric in featuredMetrics" :key="metric.label">
        <span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><small>{{ metric.note }}</small>
      </article>
    </section>

    <BatterTrendChart class="wide" :rows="gameLog.rows" />

    <section class="panel pitch-panel">
      <header><div><span>Attack map</span><h2>Performance by pitch type</h2></div><small>{{ pitchMix.rows.length }} pitch types</small></header>
      <div class="pitch-list">
        <div class="pitch-head"><span>Pitch</span><span>Usage</span><span>AVG</span><span>Whiff</span><span>Hard hit</span></div>
        <div v-for="row in pitchMix.rows.slice(0, 8)" :key="String(row.Pitch)">
          <strong><i :style="{ background: pitchColor(String(row.Pitch)) }" />{{ row.Pitch }}</strong>
          <span>{{ percentValue(row['Usage%']) }}</span><span>{{ row.AVG ?? '-' }}</span><span>{{ percentValue(row['Whiff%']) }}</span><span>{{ percentValue(row['HH%']) }}</span>
        </div>
      </div>
    </section>

    <section class="panel recent-panel">
      <header><div><span>Latest games</span><h2>Recent results</h2></div><small>{{ gameLog.rows.length }} games</small></header>
      <div class="game-list">
        <article v-for="row in gameLog.rows.slice(0, 7)" :key="String(row.Date)">
          <time>{{ formatDate(row.Date) }}</time><strong>vs {{ row.Opponent }}</strong>
          <span>{{ row.H }}-for-{{ row.AB }}</span><b :class="{ positive: Number(row.HR) > 0 }">{{ Number(row.HR) > 0 ? `${row.HR} HR` : `${row.SO} K` }}</b>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { AnalysisResponse, TablePayload } from '~/types/api'

const props = defineProps<{ overview: AnalysisResponse | null }>()
const empty: TablePayload = { columns: [], rows: [] }
const dashboard = computed(() => props.overview?.tables?.dashboard || empty)
const gameLog = computed(() => props.overview?.tables?.season_game_log || empty)
const pitchMix = computed(() => props.overview?.tables?.pitch_mix || empty)
const row = computed(() => dashboard.value.rows[0] || {})
const featuredMetrics = computed(() => [
  { label: 'OPS', value: rate(row.value.OPS), note: `${rate(row.value.OBP)} OBP · ${rate(row.value.SLG)} SLG` },
  { label: 'wOBA', value: rate(row.value.wOBA), note: `${signedGap(row.value.wOBA, row.value.xwOBA)} vs expected` },
  { label: 'xwOBA', value: rate(row.value.xwOBA), note: `${rate(row.value.xBA)} xBA · ${rate(row.value.xSLG)} xSLG` },
  { label: 'Barrel%', value: percentValue(row.value['Barrel%']), note: `${percentValue(row.value['HH%'])} hard hit` },
  { label: 'K − BB', value: percentagePointGap(row.value['K%'], row.value['BB%']), note: `${percentValue(row.value['K%'])} K · ${percentValue(row.value['BB%'])} BB` }
])

function rate(value: unknown) { const number = Number(value); return Number.isFinite(number) ? number.toFixed(3) : '-' }
function percentValue(value: unknown) { const number = parsePercent(value); return number === null ? '-' : `${number.toFixed(1)}%` }
function signedGap(actual: unknown, expected: unknown) { const gap = Number(actual) - Number(expected); return Number.isFinite(gap) ? `${gap >= 0 ? '+' : ''}${gap.toFixed(3)}` : '-' }
function percentagePointGap(strikeout: unknown, walk: unknown) { const strikeoutRate = parsePercent(strikeout); const walkRate = parsePercent(walk); return strikeoutRate === null || walkRate === null ? '-' : `${(strikeoutRate - walkRate).toFixed(1)} pp` }
function parsePercent(value: unknown) { if (value === null || value === undefined || value === '-') return null; const number = Number(String(value).replace('%', '').trim()); return Number.isFinite(number) ? number : null }
function formatDate(value: unknown) { const text = String(value || ''); const parts = text.split('-'); return parts.length === 3 ? `${parts[1]}/${parts[2]}` : text }
function pitchColor(pitch: string) { const colors: Record<string, string> = { '4-Seam Fastball': '#ef4444', Changeup: '#22c55e', Sinker: '#f97316', Cutter: '#8b6b4a', Sweeper: '#b58b2a', Slider: '#eab308', Curveball: '#3b82f6', 'Split-Finger': '#14b8a6' }; return colors[pitch] || '#94a3b8' }
</script>

<style scoped>
.overview-layout { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(330px, .65fr); gap: 16px; }
.wide, .kpi-grid { grid-column: 1 / -1; }
.kpi-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.kpi-grid article, .panel { border: 1px solid var(--color-border); border-radius: 16px; background: var(--color-surface); box-shadow: var(--shadow-sm); }
.kpi-grid article { display: grid; gap: 5px; padding: 18px; }
.kpi-grid span, .panel header span { color: var(--color-muted-text); font-size: 16px; font-weight: 900; letter-spacing: .06em; text-transform: uppercase; }
.kpi-grid strong { color: var(--color-foreground); font: 700 clamp(34px, 3vw, 48px) "Fira Code", monospace; }
.kpi-grid small { color: var(--color-muted-text); font-size: 15px; }
.panel { min-width: 0; overflow: hidden; }
.panel > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 18px; border-bottom: 1px solid var(--color-border); }
.panel h2 { margin: 4px 0 0; color: var(--color-foreground); font-size: 26px; }
.panel header small { color: var(--color-muted-text); font-size: 15px; }
.pitch-list { display: grid; padding: 4px 16px 12px; }
.pitch-list > div { display: grid; grid-template-columns: minmax(180px, 1.4fr) repeat(4, minmax(72px, .7fr)); align-items: center; gap: 10px; min-height: 58px; border-bottom: 1px solid var(--color-border); font: 600 17px "Fira Code", monospace; }
.pitch-list > div > span { text-align: right; }
.pitch-list strong { display: flex; align-items: center; gap: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: "Fira Sans", sans-serif; }
.pitch-list i { width: 8px; height: 8px; flex: 0 0 auto; border-radius: 50%; }
.pitch-head { color: var(--color-muted-text); font-size: 15px !important; font-weight: 900 !important; text-transform: uppercase; }
.game-list { display: grid; }
.game-list article { display: grid; grid-template-columns: 62px minmax(92px, 1fr) 76px 76px; align-items: center; gap: 10px; min-height: 66px; padding: 10px 17px; border-bottom: 1px solid var(--color-border); font-size: 17px; }
.game-list time, .game-list span { color: var(--color-muted-text); font-family: "Fira Code", monospace; }
.game-list b { border-radius: 999px; padding: 6px 8px; color: var(--color-muted-text); background: var(--color-muted); font-size: 15px; text-align: center; }
.game-list b.positive { color: #111; background: var(--color-primary); }
@media (max-width: 1000px) { .overview-layout { grid-template-columns: 1fr; } .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 620px) { .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .kpi-grid article:first-child { grid-column: 1 / -1; } .pitch-list { overflow-x: auto; } .pitch-list > div { min-width: 550px; } }
</style>
