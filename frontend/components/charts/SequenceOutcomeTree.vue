<template>
  <section class="sequence-tree">
    <header class="chart-header">
      <h2>Sequence Outcomes</h2>
      <span>Pitch mix by count</span>
    </header>
    <div class="tree-wrap">
      <svg viewBox="0 0 1100 760" role="img" aria-label="Sequence outcomes by count">
        <g class="links">
          <polyline
            v-for="link in renderedLinks"
            :key="`${link.from}-${link.to}`"
            :points="link.points"
          />
        </g>
        <g v-for="node in renderedNodes" :key="node.count" class="node">
          <text class="count-label" :x="node.x + labelOffset(node.count).x" :y="node.y + labelOffset(node.count).y">{{ node.count }}</text>
          <circle v-if="!node.slices.length" class="empty-pie" :cx="node.x" :cy="node.y" :r="pieRadius" />
          <g
            v-for="slice in node.slices"
            :key="`${node.count}-${slice.pitch}`"
            class="slice"
            role="button"
            tabindex="0"
            @mouseenter="hoveredSlice = { ...slice, count: node.count, total: node.total }"
            @mouseleave="hoveredSlice = null"
            @focus="hoveredSlice = { ...slice, count: node.count, total: node.total }"
            @blur="hoveredSlice = null"
            @click="emit('select-branch', { count: node.count, pitch: slice.pitch })"
            @keydown.enter.prevent="emit('select-branch', { count: node.count, pitch: slice.pitch })"
            @keydown.space.prevent="emit('select-branch', { count: node.count, pitch: slice.pitch })"
          >
            <circle
              v-if="slice.fullCircle"
              :cx="slice.x"
              :cy="slice.y"
              :r="pieRadius"
              :fill="slice.color"
            />
            <path v-else :d="slice.path" :fill="slice.color" />
          </g>
          <circle class="pie-ring" :cx="node.x" :cy="node.y" :r="pieRadius" />
        </g>
        <g v-if="hoveredSlice" class="hover-card">
          <rect x="704" y="32" width="248" height="212" rx="8" />
          <text x="724" y="62" class="hover-title">{{ hoveredSlice.count }} | {{ hoveredSlice.pitch }}</text>
          <text x="724" y="90">Pitches {{ hoveredSlice.pitches }} / {{ hoveredSlice.total }}</text>
          <text x="724" y="112">Usage {{ hoveredSlice.rateText }}</text>
          <text x="724" y="134">Strike% {{ formatPercent(hoveredSlice.strikePct) }}</text>
          <text x="724" y="156">Swing% {{ formatPercent(hoveredSlice.swingPct) }}</text>
          <text x="724" y="178">Whiff% {{ formatPercent(hoveredSlice.whiffPct) }}</text>
          <text x="724" y="200">Hard Hit% {{ formatPercent(hoveredSlice.hardHitPct) }}</text>
          <text x="724" y="222">AVG {{ formatDecimal(hoveredSlice.avg) }}</text>
        </g>
      </svg>
    </div>
    <div v-if="legendItems.length" class="legend">
      <span v-for="pitch in legendItems" :key="pitch">
        <i :style="{ background: colorForPitch(pitch) }" />
        {{ pitch }}
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{
  rows: Array<Record<string, unknown>>
  sourceRows?: Array<Record<string, unknown>>
}>()

const emit = defineEmits<{
  'select-branch': [branch: { count: string; pitch: string }]
}>()

const pieRadius = 38
const hoveredSlice = ref<RenderedSlice | null>(null)

type RenderedSlice = {
  count: string
  pitch: string
  pitches: number
  total: number
  rateText: string
  strikePct: number | null
  swingPct: number | null
  whiffPct: number | null
  hardHitPct: number | null
  avg: number | null
  color: string
  path: string
  x: number
  y: number
  fullCircle: boolean
}

const countPositions: Record<string, [number, number]> = {
  '0-0': [500, 90],
  '0-1': [340, 200],
  '1-0': [660, 200],
  '0-2': [190, 320],
  '1-1': [500, 320],
  '2-0': [810, 320],
  '1-2': [340, 440],
  '2-1': [660, 440],
  '3-0': [930, 440],
  '2-2': [500, 560],
  '3-1': [790, 560],
  '3-2': [660, 675]
}

const countLinks = [
  ['0-0', '0-1'],
  ['0-0', '1-0'],
  ['0-1', '0-2'],
  ['0-1', '1-1'],
  ['1-0', '1-1'],
  ['1-0', '2-0'],
  ['0-2', '1-2'],
  ['1-1', '1-2'],
  ['1-1', '2-1'],
  ['2-0', '2-1'],
  ['2-0', '3-0'],
  ['1-2', '2-2'],
  ['2-1', '2-2'],
  ['2-1', '3-1'],
  ['3-0', '3-1'],
  ['2-2', '3-2'],
  ['3-1', '3-2']
] as const

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
  Slurve: '#607d8b',
  Unknown: '#8b949e'
}

const groupedRows = computed(() => {
  const fallbackMetrics = fallbackMetricsByCountPitch.value
  const grouped = new Map<string, Array<{
    pitch: string
    pitches: number
    strikePct: number | null
    swingPct: number | null
    whiffPct: number | null
    hardHitPct: number | null
    avg: number | null
  }>>()
  for (const row of props.rows) {
    const count = String(row.count || '')
    if (!countPositions[count]) {
      continue
    }
    const pitch = String(row.Pitch || row.pitch_name || 'Unknown')
    const pitches = Number(row.pitches || 0)
    if (!Number.isFinite(pitches) || pitches <= 0) {
      continue
    }
    const rows = grouped.get(count) || []
    const fallback = fallbackMetrics.get(`${count}|${normalizePitchKey(pitch)}`)
    rows.push({
      pitch,
      pitches,
      strikePct: numberOrNull(firstDefined(row.strike_pct, row.strike_rate, row['Strike%'], row.Strike, fallback?.strikePct)),
      swingPct: numberOrNull(firstDefined(row.swing_pct, row.swing_rate, row['Swing%'], row.Swing, fallback?.swingPct)),
      whiffPct: numberOrNull(firstDefined(row.whiff_pct, row.whiff_rate, row['Whiff%'], row.Whiff, fallback?.whiffPct)),
      hardHitPct: numberOrNull(firstDefined(row.hard_hit_pct, row.hard_hit_rate, row['Hard Hit%'], row['Hard Hit %'], row.HardHit, fallback?.hardHitPct)),
      avg: numberOrNull(firstDefined(row.avg, row.AVG, row.ba, row.BA, fallback?.avg))
    })
    grouped.set(count, rows)
  }
  return grouped
})

const fallbackMetricsByCountPitch = computed(() => {
  const grouped = new Map<string, {
    pitches: number
    strikes: number
    swings: number
    whiffs: number
    hardHits: number
    hits: number
    abs: number
  }>()
  for (const row of props.sourceRows || []) {
    const balls = Number(row.balls)
    const strikes = Number(row.strikes)
    const rawPitch = String(row.pitch_name || row.Pitch || 'Unknown')
    if (!Number.isFinite(balls) || !Number.isFinite(strikes) || balls < 0 || balls > 3 || strikes < 0 || strikes > 2) {
      continue
    }
    const count = `${Math.trunc(balls)}-${Math.trunc(strikes)}`
    const key = `${count}|${normalizePitchKey(displayPitchName(rawPitch))}`
    const bucket = grouped.get(key) || { pitches: 0, strikes: 0, swings: 0, whiffs: 0, hardHits: 0, hits: 0, abs: 0 }
    const description = normalized(row.description)
    const events = normalized(row.events)
    const launchSpeed = Number(row.launch_speed)
    bucket.pitches += 1
    bucket.strikes += swingEvents.has(description) || calledStrikeEvents.has(description) ? 1 : 0
    bucket.swings += swingEvents.has(description) ? 1 : 0
    bucket.whiffs += whiffEvents.has(description) ? 1 : 0
    bucket.hardHits += Number.isFinite(launchSpeed) && launchSpeed >= 95 ? 1 : 0
    bucket.hits += hitEvents.has(events) ? 1 : 0
    bucket.abs += events && !walkEvents.has(events) && !sacrificeEvents.has(events) ? 1 : 0
    grouped.set(key, bucket)
  }
  const metrics = new Map<string, { strikePct: number | null; swingPct: number | null; whiffPct: number | null; hardHitPct: number | null; avg: number | null }>()
  for (const [key, bucket] of grouped.entries()) {
    metrics.set(key, {
      strikePct: bucket.pitches ? (bucket.strikes / bucket.pitches) * 100 : null,
      swingPct: bucket.pitches ? (bucket.swings / bucket.pitches) * 100 : null,
      whiffPct: bucket.swings ? (bucket.whiffs / bucket.swings) * 100 : null,
      hardHitPct: bucket.pitches ? (bucket.hardHits / bucket.pitches) * 100 : null,
      avg: bucket.abs ? bucket.hits / bucket.abs : null
    })
  }
  return metrics
})

const renderedNodes = computed(() => {
  return Object.entries(countPositions)
    .map(([count, [x, y]]) => {
      const rows = groupedRows.value.get(count) || []
      const total = rows.reduce((sum, row) => sum + row.pitches, 0)
      let start = -90
      const slices = rows.map((row) => {
        const sweep = total > 0 ? (row.pitches / total) * 360 : 0
        const end = start + sweep
        const slice = {
          pitch: row.pitch,
          pitches: row.pitches,
          total,
          rateText: total > 0 ? `${((row.pitches / total) * 100).toFixed(1)}%` : '-',
          strikePct: row.strikePct,
          swingPct: row.swingPct,
          whiffPct: row.whiffPct,
          hardHitPct: row.hardHitPct,
          avg: row.avg,
          color: colorForPitch(row.pitch),
          path: describeSlice(x, y, pieRadius, start, end),
          x,
          y,
          fullCircle: sweep >= 359.9
        }
        start = end
        return slice
      })
      return { count, x, y, total, slices }
    })
})

const renderedLinks = computed(() => {
  return countLinks
    .map(([from, to]) => {
      const [x1, y1] = countPositions[from]
      const [x2, y2] = countPositions[to]
      const midY = (y1 + y2) / 2
      return { from, to, points: `${x1},${y1} ${x1},${midY} ${x2},${midY} ${x2},${y2}` }
    })
})

const legendItems = computed(() => {
  return [...new Set(props.rows.map((row) => String(row.Pitch || row.pitch_name || 'Unknown')).filter(Boolean))]
})

function colorForPitch(pitch: string) {
  return pitchColors[pitch] || pitchColors.Unknown
}

function labelOffset(count: string) {
  return { x: 0, y: -52 }
}

function displayPitchName(pitch: string) {
  return pitch === 'Four-Seam' || pitch === 'Four-Seam Fastball' ? '4-Seam' : pitch
}

function normalizePitchKey(pitch: string) {
  return displayPitchName(pitch).toLowerCase().replace(/[^a-z0-9]/g, '')
}

function normalized(value: unknown) {
  return String(value || '').toLowerCase().trim()
}

function numberOrNull(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return null
  }
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

function firstDefined(...values: unknown[]) {
  return values.find((value) => value !== null && value !== undefined && value !== '')
}

function formatPercent(value: number | null) {
  return value === null ? '-' : `${value.toFixed(1)}%`
}

function formatDecimal(value: number | null) {
  return value === null ? '-' : value.toFixed(3)
}

function describeSlice(cx: number, cy: number, radius: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(cx, cy, radius, endAngle)
  const end = polarToCartesian(cx, cy, radius, startAngle)
  const largeArcFlag = endAngle - startAngle <= 180 ? 0 : 1
  return [
    `M ${cx} ${cy}`,
    `L ${start.x} ${start.y}`,
    `A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`,
    'Z'
  ].join(' ')
}

function polarToCartesian(cx: number, cy: number, radius: number, angleInDegrees: number) {
  const angleInRadians = (angleInDegrees * Math.PI) / 180
  return {
    x: cx + radius * Math.cos(angleInRadians),
    y: cy + radius * Math.sin(angleInRadians)
  }
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
const whiffEvents = new Set(['swinging_strike', 'swinging_strike_blocked', 'foul_tip', 'missed_bunt'])
const calledStrikeEvents = new Set(['called_strike'])
const hitEvents = new Set(['single', 'double', 'triple', 'home_run'])
const walkEvents = new Set(['walk', 'intent_walk'])
const sacrificeEvents = new Set(['sac_bunt', 'sac_fly', 'sac_fly_double_play'])
</script>

<style scoped>
.sequence-tree {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.chart-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}

.chart-header h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

.chart-header span {
  color: var(--color-muted-text);
  font-size: 13px;
}

.tree-wrap {
  overflow-x: auto;
  padding: 10px 12px 0;
  text-align: center;
}

svg {
  display: block;
  width: 80%;
  min-width: 672px;
  height: auto;
  margin: 0 auto;
}

.links polyline {
  fill: none;
  stroke: #cbd5e1;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 7;
  opacity: 0.72;
}

.count-label {
  fill: var(--color-foreground);
  font-size: 22px;
  font-weight: 750;
  text-anchor: middle;
}

:global(:root[data-theme="dark"]) .count-label {
  fill: #ffffff;
}

.slice path,
.slice circle {
  cursor: pointer;
  stroke: #ffffff;
  stroke-width: 1.45;
  transition: filter 150ms ease, transform 150ms ease;
}

.slice:hover path,
.slice:focus path,
.slice:hover circle,
.slice:focus circle {
  filter: brightness(1.08);
}

.pie-ring {
  fill: none;
  pointer-events: none;
  stroke: #ffffff;
  stroke-width: 2;
}

.empty-pie {
  fill: #f8fafc;
  stroke: #cbd5e1;
  stroke-width: 2;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 18px;
  padding: 4px 14px 14px;
  color: var(--color-text);
  font-size: 13px;
}

.legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  border: 0.7px solid rgba(255, 255, 255, 0.9);
}

.hover-card {
  pointer-events: none;
}

.hover-card rect {
  fill: rgba(15, 23, 42, 0.92);
  stroke: rgba(226, 232, 240, 0.55);
  stroke-width: 1;
  height: 212px;
}

.hover-card text {
  fill: #dbeafe;
  font-size: 15px;
}

.hover-card .hover-title {
  fill: #ffffff;
  font-size: 17px;
  font-weight: 750;
}

@media (max-width: 860px) {
  svg {
    width: 100%;
    min-width: 672px;
  }
}
</style>
