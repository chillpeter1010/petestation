<template>
  <article class="discipline-zone-panel">
    <StrikeZoneScatter
      :title="panel.label"
      :points="panel.rows"
      :total-pitches="panel.pitches ?? panel.rows.length"
      :heatmap-blend="heatmapBlend"
      compact
    />
    <div v-if="sideMode === 'info'" class="panel-side">
      <div class="info-pie-wrap">
        <div
          v-if="displayPitchMix.length"
          class="pitch-pie"
          :style="{ background: pieGradient }"
          aria-label="Pitch mix pie chart"
        />
        <div v-else class="pitch-pie empty" />
      </div>
      <dl v-if="displayMetrics.length" class="panel-metrics">
        <div v-for="metric in displayMetrics" :key="metric.label">
          <dt>{{ metric.label }}</dt>
          <dd>{{ formatMetric(metric) }}</dd>
        </div>
      </dl>
    </div>
    <div v-else-if="displayPitchMix.length" class="pitch-legend">
      <span v-for="pitch in displayPitchMix" :key="String(pitch.pitch)">
        <i :style="{ background: colorForPitch(String(pitch.pitch)) }" />
        {{ pitch.pitch }}
      </span>
    </div>
  </article>
</template>

<script setup lang="ts">
export type DisciplinePanelMetric = {
  label: string
  value: number | string | null
  unit?: string | null
}

export type DisciplinePitchMixItem = {
  pitch: string
  pitches?: number
  count?: number
  rate?: number
}

export type DisciplinePanel = {
  key: string
  label: string
  rows: Array<Record<string, unknown>>
  pitches?: number
  metrics?: DisciplinePanelMetric[]
  pitchMix?: DisciplinePitchMixItem[]
}

const props = defineProps<{
  panel: DisciplinePanel
  heatmapBlend: number
  sideMode: 'pitch' | 'info'
}>()

const displayMetrics = computed(() => props.panel.metrics || fallbackMetrics(props.panel.rows))
const displayPitchMix = computed(() => props.panel.pitchMix?.length ? props.panel.pitchMix : fallbackPitchMix(props.panel.rows))
const pieGradient = computed(() => {
  const mix = displayPitchMix.value.filter((pitch) => Number(pitch.rate) > 0)
  if (!mix.length) {
    return '#e2e8f0'
  }
  let cursor = 0
  const stops: string[] = []
  for (const pitch of mix) {
    const rate = Number(pitch.rate)
    const start = cursor
    cursor += rate * 100
    stops.push(`${colorForPitch(String(pitch.pitch))} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`)
  }
  return `conic-gradient(from -90deg, ${stops.join(', ')})`
})

function fallbackMetrics(rows: Array<Record<string, unknown>>): DisciplinePanelMetric[] {
  if (!rows.length) {
    return [
      { label: 'Str%', value: null, unit: '%' },
      { label: 'Zone%', value: null, unit: '%' },
      { label: 'Swing%', value: null, unit: '%' },
      { label: 'O-Swing%', value: null, unit: '%' },
      { label: 'Whiff%', value: null, unit: '%' },
      { label: 'AVG', value: null }
    ]
  }
  const descriptions = rows.map((row) => String(row.description || '').toLowerCase())
  const zones = rows.map((row) => Number(row.zone)).filter(Number.isFinite)
  const strikes = descriptions.filter((description) => strikeEvents.has(description)).length
  const swings = descriptions.filter((description) => isSwing(description)).length
  const whiffs = descriptions.filter((description) => isWhiff(description)).length
  const outZoneRows = rows.filter((row) => {
    const zone = Number(row.zone)
    return Number.isFinite(zone) && (zone < 1 || zone > 9)
  })
  const outZoneSwings = outZoneRows.filter((row) => isSwing(String(row.description || '').toLowerCase())).length
  const events = rows.map((row) => String(row.events || '').toLowerCase())
  const abEvents = events.filter((event) => event && !nonAbEvents.has(event))
  const hits = events.filter((event) => hitEvents.has(event)).length
  return [
    { label: 'Str%', value: rows.length ? (strikes / rows.length) * 100 : null, unit: '%' },
    { label: 'Zone%', value: zones.length ? (zones.filter((zone) => zone >= 1 && zone <= 9).length / rows.length) * 100 : null, unit: '%' },
    { label: 'Swing%', value: rows.length ? (swings / rows.length) * 100 : null, unit: '%' },
    { label: 'O-Swing%', value: outZoneRows.length ? (outZoneSwings / outZoneRows.length) * 100 : null, unit: '%' },
    { label: 'Whiff%', value: swings ? (whiffs / swings) * 100 : null, unit: '%' },
    { label: 'AVG', value: abEvents.length ? hits / abEvents.length : null }
  ]
}

function fallbackPitchMix(rows: Array<Record<string, unknown>>): DisciplinePitchMixItem[] {
  if (!rows.length) {
    return []
  }
  const counts = new Map<string, number>()
  for (const row of rows) {
    const pitch = String(row.pitch_name || row.Pitch || 'Unknown')
    counts.set(pitch, (counts.get(pitch) || 0) + 1)
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([pitch, pitches]) => ({ pitch, pitches, rate: pitches / rows.length }))
}

function isSwing(description: string) {
  return swingEvents.has(description)
}

function isWhiff(description: string) {
  return whiffEvents.has(description)
}

function formatMetric(metric: DisciplinePanelMetric) {
  if (metric.value === null || metric.value === undefined || metric.value === '') {
    return '-'
  }
  if (typeof metric.value === 'number') {
    if (metric.unit === '%') {
      return `${metric.value.toFixed(1)}%`
    }
    return metric.label === 'AVG' ? metric.value.toFixed(3) : metric.value.toFixed(1)
  }
  return String(metric.value)
}

function formatRate(value: number | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(0)}%` : '-'
}

function colorForPitch(pitch: string) {
  return pitchColors[pitch] || defaultPitchColor
}

const swingEvents = new Set([
  'swinging_strike',
  'swinging_strike_blocked',
  'foul',
  'foul_tip',
  'foul_bunt',
  'hit_into_play',
  'hit_into_play_no_out',
  'hit_into_play_score',
  'missed_bunt'
])
const strikeEvents = new Set([
  'called_strike',
  'swinging_strike',
  'swinging_strike_blocked',
  'foul',
  'foul_tip',
  'foul_bunt',
  'hit_into_play',
  'hit_into_play_no_out',
  'hit_into_play_score',
  'missed_bunt'
])
const whiffEvents = new Set(['swinging_strike', 'swinging_strike_blocked', 'foul_tip', 'missed_bunt'])
const hitEvents = new Set(['single', 'double', 'triple', 'home_run'])
const nonAbEvents = new Set(['walk', 'intent_walk', 'hit_by_pitch', 'sac_fly', 'sac_bunt', 'sac_fly_double_play', 'catcher_interf'])
const pitchColors: Record<string, string> = {
  '4-Seam Fastball': '#d62828',
  Fastball: '#d62828',
  'Four-Seam': '#d62828',
  '4-Seam': '#d62828',
  Sinker: '#f77f00',
  Cutter: '#7f5539',
  Slider: '#ffd166',
  Changeup: '#28c97b',
  'Split-Finger': '#00a6a6',
  Splitter: '#00a6a6',
  Forkball: '#00a6a6',
  Curveball: '#277da1',
  'Knuckle Curve': '#7b2cbf',
  Sweeper: '#bc8a3c',
  Slurve: '#607d8b'
}
const defaultPitchColor = '#8b949e'
</script>

<style scoped>
.discipline-zone-panel {
  min-width: 0;
  display: grid;
  gap: 8px;
  align-content: start;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 12px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.discipline-zone-panel :deep(.zone-chart) {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.discipline-zone-panel :deep(.chart-header) {
  padding: 0 0 8px;
  border-bottom: 0;
}

.discipline-zone-panel :deep(.plot-wrap) {
  padding: 0;
}

.panel-side {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  background: var(--color-surface);
}

.info-pie-wrap {
  display: grid;
  place-items: center;
}

.pitch-pie {
  width: 74px;
  height: 74px;
  border-radius: 999px;
  border: 0.75px solid rgba(255, 255, 255, 0.92);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.72);
}

.pitch-pie.empty {
  background: #e2e8f0;
}

.panel-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 10px;
  margin: 0;
}

.panel-metrics div {
  min-width: 0;
}

.panel-metrics dt {
  color: var(--color-muted-text);
  font-size: 11px;
  font-weight: 750;
}

.panel-metrics dd {
  margin: 2px 0 0;
  color: var(--color-text);
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 12px;
  font-weight: 650;
}

.pitch-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 13px;
  color: var(--color-text);
  font-size: 12px;
}

.pitch-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.pitch-legend i {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  border: 0.7px solid rgba(255, 255, 255, 0.9);
}
</style>
