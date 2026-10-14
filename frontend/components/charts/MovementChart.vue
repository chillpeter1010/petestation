<template>
  <section class="movement-chart" :class="{ 'no-point-outline': showPointOutline === false, 'stuff-color-mode': colorMode === 'stuff' }">
    <header class="chart-header">
      <div>
        <h2>{{ title || 'Movement' }}</h2>
        <span>{{ subtitle }}</span>
      </div>
      <div class="chart-actions">
        <div v-if="allowStuffColor" class="color-toggle" role="group" aria-label="Movement point color">
          <button type="button" :class="{ active: colorMode === 'pitch' }" @click="colorMode = 'pitch'">Pitch</button>
          <button type="button" :class="{ active: colorMode === 'stuff' }" @click="showStuffColors">{{ stuffColorLoading ? 'Loading…' : 'Stuff+' }}</button>
        </div>
        <div class="mode-toggle" role="group" aria-label="Movement chart mode">
          <button type="button" :class="{ active: mode === 'scatter' }" @click="$emit('update:mode', 'scatter')">Scatter</button>
          <button type="button" :class="{ active: mode === 'average' }" @click="$emit('update:mode', 'average')">Average</button>
        </div>
      </div>
    </header>

    <div v-if="mode === 'scatter'" class="plot-wrap">
      <svg class="scatter-svg" viewBox="0 0 560 500" role="img" aria-label="Pitch movement chart">
        <rect class="plot-bg" :x="plot.left" :y="plot.top" :width="plot.width" :height="plot.height" />

        <g class="grid">
          <line v-for="tick in xTicks" :key="`x-${tick}`" :x1="scaleX(tick)" :x2="scaleX(tick)" :y1="plot.top" :y2="plot.bottom" />
          <line v-for="tick in yTicks" :key="`y-${tick}`" :x1="plot.left" :x2="plot.right" :y1="scaleY(tick)" :y2="scaleY(tick)" />
          <line class="zero" :x1="scaleX(0)" :x2="scaleX(0)" :y1="plot.top" :y2="plot.bottom" />
          <line class="zero" :x1="plot.left" :x2="plot.right" :y1="scaleY(0)" :y2="scaleY(0)" />
        </g>

        <g class="axis-labels">
          <text v-for="tick in xTicks" :key="`xl-${tick}`" :x="scaleX(tick)" :y="plot.bottom + 28">{{ tick }}</text>
          <text v-for="tick in yTicks" :key="`yl-${tick}`" :x="plot.left - 22" :y="scaleY(tick) + 4">{{ tick }}</text>
          <text :x="plot.left + plot.width / 2" :y="plot.bottom + 58">Horizontal Break (in)</text>
          <text :x="22" :y="plot.top + plot.height / 2" transform="rotate(-90 22 220)">Induced Vertical Break (in)</text>
        </g>
        <circle
          v-for="(point, index) in scatterPoints"
          :key="index"
          :cx="scaleX(point.x)"
          :cy="scaleY(point.y)"
          r="4.2"
          :fill="pointColor(point)"
          stroke="#020617"
          stroke-width="1.4"
          vector-effect="non-scaling-stroke"
          class="pitch-dot"
          :class="{ selected: selectedKey && selectedKey === point.key }"
          tabindex="0"
          role="button"
          @click="emit('select-point', point.raw)"
          @keydown.enter.prevent="emit('select-point', point.raw)"
          @keydown.space.prevent="emit('select-point', point.raw)"
        >
          <title>{{ scatterTooltip(point) }}</title>
        </circle>
      </svg>
    </div>

    <div v-else class="profile-wrap">
      <svg class="profile-svg" :viewBox="profileViewBox" role="img" aria-label="Average pitch movement profile">
        <defs>
          <pattern
            v-for="point in profilePoints"
            :id="`league-hatch-${slug(point.pitch)}`"
            :key="`pattern-${point.pitch}`"
            patternUnits="userSpaceOnUse"
            width="8"
            height="8"
            patternTransform="rotate(45)"
          >
            <line x1="0" y1="0" x2="0" y2="8" :stroke="colorForPitch(point.pitch)" stroke-width="2.2" opacity="0.72" />
          </pattern>
          <pattern id="league-key-hatch" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#94a3b8" stroke-width="2" opacity="0.72" />
          </pattern>
        </defs>

        <rect class="profile-bg" width="640" height="900" />
        <text x="320" y="82" class="profile-title">Movement Profile</text>
        <g :transform="`translate(${profile.cx} ${profile.cy})`">
          <circle class="profile-center-bg" :r="profile.radius" />
          <circle v-for="ring in profileRings" :key="ring.radius" :r="ring.radius" class="profile-ring" :class="{ dashed: ring.dashed }" />
          <line :x1="-profile.radius - 20" :x2="profile.radius + 20" y1="0" y2="0" class="profile-zero" />
          <line x1="0" x2="0" :y1="-profile.radius - 20" :y2="profile.radius + 20" class="profile-zero" />

          <text x="0" :y="-profile.radius - 39" class="toward-label">1B ◀&nbsp; MOVES TOWARD &nbsp;▶ 3B</text>
          <text v-for="tick in [6, 12, 18, 24]" :key="`pos-${tick}`" :x="profileScale(tick)" y="18" class="profile-tick">{{ tick }}"</text>
          <text v-for="tick in [6, 12, 18, 24]" :key="`neg-${tick}`" :x="profileScale(-tick)" y="18" class="profile-tick">{{ tick }}"</text>

          <g v-for="point in profilePoints" :key="point.pitch">
            <circle
              v-if="point.leagueX !== null && point.leagueY !== null"
              :cx="profileScale(point.leagueX)"
              :cy="-profileScale(point.leagueY)"
              :r="leagueRadius(point)"
              :fill="`url(#league-hatch-${slug(point.pitch)})`"
              :stroke="colorForPitch(point.pitch)"
              stroke-width="2.2"
              fill-opacity="0.72"
              stroke-opacity="0.72"
              class="pitch-outline league-bubble"
            >
              <title>{{ leagueTooltip(point) }}</title>
            </circle>
            <circle
              :cx="profileScale(point.x)"
              :cy="-profileScale(point.y)"
              :r="usageRadius(point)"
              :fill="colorForPitch(point.pitch)"
              :stroke="colorForPitch(point.pitch)"
              stroke-width="2"
              vector-effect="non-scaling-stroke"
              fill-opacity="0.56"
              stroke-opacity="0.84"
              class="pitch-bubble"
            >
              <title>{{ profileTooltip(point) }}</title>
            </circle>
            <circle
              :cx="profileScale(point.x)"
              :cy="-profileScale(point.y)"
              r="4.8"
              :fill="colorForPitch(point.pitch)"
              stroke="rgba(2, 6, 23, 0.72)"
              stroke-width="1.1"
              vector-effect="non-scaling-stroke"
              opacity="0.82"
              class="pitch-dot"
            >
              <title>{{ profileTooltip(point) }}</title>
            </circle>
          </g>

          <text v-if="armAngleLines.length" x="236" y="198" class="arm-angle">
            <tspan v-for="(line, index) in armAngleLines" :key="line" x="236" :dy="index === 0 ? 0 : 18">{{ line }}</tspan>
          </text>
        </g>

        <g v-if="showProfileInfo !== false" class="profile-info">
          <g v-for="(group, groupIndex) in profileGroups" :key="groupIndex">
            <text x="20" :y="infoY(groupIndex, 'pitch')" class="info-heading">PITCH</text>
            <text x="20" :y="infoY(groupIndex, 'usage')" class="info-heading">USAGE</text>
            <text x="20" :y="infoY(groupIndex, 'mph')" class="info-heading">MPH</text>
            <text x="20" :y="infoY(groupIndex, 'avg')" class="info-heading">{{ leagueAverageLabel }}</text>
            <g v-for="(point, index) in group" :key="point.pitch" :transform="`translate(${infoX(index)} 0)`">
              <circle :cy="infoY(groupIndex, 'dot')" r="13" :fill="colorForPitch(point.pitch)" stroke="#020617" stroke-width="1.4" vector-effect="non-scaling-stroke" opacity="0.95" class="pitch-dot" />
              <circle
                v-if="point.leagueVelo !== null"
                :cy="infoY(groupIndex, 'dot') - 2"
                cx="18"
                r="12"
                fill="none"
                :stroke="colorForPitch(point.pitch)"
                stroke-width="2"
                opacity="0.55"
              />
              <text y="0" :transform="`translate(0 ${infoY(groupIndex, 'pitch')})`" class="info-value">{{ displayPitch(point.pitch) }}</text>
              <text y="0" :transform="`translate(0 ${infoY(groupIndex, 'usage')})`" class="info-value">{{ point.usage.toFixed(0) }}%</text>
              <text y="0" :transform="`translate(0 ${infoY(groupIndex, 'mph')})`" class="info-muted">{{ formatOne(point.velocity) }}</text>
              <text y="0" :transform="`translate(0 ${infoY(groupIndex, 'avg')})`" class="info-muted">{{ formatOne(point.leagueVelo) }}</text>
            </g>
          </g>
        </g>
      </svg>
    </div>

    <div v-if="mode === 'scatter' && colorMode === 'pitch' && legendItems.length" class="legend">
      <span v-for="pitch in legendItems" :key="pitch">
        <i :style="{ background: colorForPitch(pitch) }" />
        {{ pitch }}
      </span>
    </div>
    <div v-else-if="mode === 'scatter' && colorMode === 'stuff'" class="stuff-legend">
      <span>70</span><i /><span>100</span><span>130</span><strong>Stuff+</strong>
    </div>
  </section>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  mode: 'scatter' | 'average'
  title?: string
  scatterRows: Array<Record<string, unknown>>
  summaryRows: Array<Record<string, unknown>>
  leagueRows?: Array<Record<string, unknown>>
  allowStuffColor?: boolean
  stuffColorLoading?: boolean
  pitcherHand?: string
  showPointOutline?: boolean
  showProfileInfo?: boolean
  selectedKey?: string | null
}>(), {
  showPointOutline: true,
  showProfileInfo: true,
  allowStuffColor: false,
  stuffColorLoading: false
})

const emit = defineEmits<{
  'update:mode': [mode: 'scatter' | 'average']
  'request-stuff-colors': []
  'select-point': [point: Record<string, unknown>]
}>()

const plot = {
  left: 78,
  top: 28,
  right: 478,
  bottom: 388,
  width: 400,
  height: 360
}

const xDomain = [-25, 25] as const
const yDomain = [-20, 25] as const
const xTicks = [-20, -10, 0, 10, 20]
const yTicks = [-20, -10, 0, 10, 20]
const profile = {
  cx: 320,
  cy: 300,
  radius: 205,
  domain: 26
}
const profileRings = [
  { radius: profileScaleValue(6), dashed: true },
  { radius: profileScaleValue(12), dashed: false },
  { radius: profileScaleValue(18), dashed: true },
  { radius: profileScaleValue(24), dashed: false }
]
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
const colorMode = ref<'pitch' | 'stuff'>('pitch')
const stuffColorRequested = ref(false)

const scatterPoints = computed(() => props.scatterRows.flatMap((row, index) => {
  const x = Number(row.h_break)
  const y = Number(row.v_break)
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return []
  }
  const key = `movement:${index}:${pitchPointKey(row)}`
  return [{
    x,
    y,
    pitch: String(row.pitch_name || row.Pitch || 'Unknown'),
    stuffPlus: numberOrNull(row.pitch_stuff_plus),
    locationPlus: numberOrNull(row.location_plus_pitch),
    staminaPlus: numberOrNull(row.stamina_plus_trait),
    expectedStuffPlus: numberOrNull(row.stamina_expected_stuff_plus),
    expectedRetentionDelta: numberOrNull(row.stamina_expected_retention_delta),
    staminaSample: String(row.stamina_sample_label || ''),
    key,
    raw: { ...row, _movement_point_key: key },
  }]
}))

const hasStuffScores = computed(() => scatterPoints.value.some((point) => point.stuffPlus !== null))

const averagePoints = computed(() => props.summaryRows.flatMap((row) => {
  const x = Number(row.h_break)
  const y = Number(row.v_break)
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return []
  }
  return [{ x, y, pitch: String(row.Pitch || row.pitch_name || 'Unknown') }]
}))

const leagueByPitch = computed(() => {
  const map = new Map<string, Record<string, unknown>>()
  for (const row of props.leagueRows || []) {
    const pitch = String(row.Pitch || row.pitch_name || row['Pitch Raw'] || '')
    if (pitch) {
      map.set(normalizePitchKey(pitch), row)
    }
  }
  return map
})

const profilePoints = computed(() => {
  return props.summaryRows.flatMap((row) => {
    const rawPitch = String(row.pitch_name || row.Pitch || 'Unknown')
    const pitch = String(row.Pitch || row.pitch_name || 'Unknown')
    const x = Number(row.h_break ?? row.HB)
    const y = Number(row.v_break ?? row.IVB)
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return []
    }
    const league = leagueByPitch.value.get(normalizePitchKey(rawPitch)) || leagueByPitch.value.get(normalizePitchKey(pitch))
    return [{
      pitch,
      x,
      y,
      usage: numberOrZero(row.usage_pct ?? row['Usage%']),
      velocity: numberOrNull(row.release_speed ?? row.Velo),
      leagueX: numberOrNull(findLeagueValue(league, 'HB')),
      leagueY: numberOrNull(findLeagueValue(league, 'IVB')),
      leagueUsage: numberOrNull(findLeagueValue(league, 'Usage%')),
      leagueVelo: numberOrNull(findLeagueValue(league, 'Velo'))
    }]
  }).sort((a, b) => b.usage - a.usage).slice(0, 10)
})

const profileGroups = computed(() => {
  const rows = profilePoints.value
  return [rows.slice(0, 5), rows.slice(5, 10)].filter((group) => group.length)
})

const profileViewBox = computed(() => props.showProfileInfo === false ? '0 0 640 560' : '0 0 640 900')

const legendItems = computed(() => {
  const source = props.mode === 'average' ? averagePoints.value : scatterPoints.value
  return [...new Set(source.map((point) => point.pitch))]
})

const subtitle = computed(() => {
  if (props.mode === 'average') {
    return `${averagePoints.value.length.toLocaleString()} pitch types`
  }
  return `${scatterPoints.value.length.toLocaleString()} pitches`
})

const leagueAverageLabel = computed(() => {
  return props.pitcherHand === 'L' || props.pitcherHand === 'R' ? `${props.pitcherHand}HP AVG` : 'MLB AVG'
})

const armAngleLines = computed(() => {
  const values = props.scatterRows
    .map((row) => numberOrNull(row.arm_angle))
    .filter((value): value is number => value !== null)
  if (!values.length) {
    return []
  }
  const average = values.reduce((sum, value) => sum + value, 0) / values.length
  return ['ARM', 'ANGLE', `${average.toFixed(0)}°`]
})

function scaleX(value: number) {
  return plot.left + ((value - xDomain[0]) / (xDomain[1] - xDomain[0])) * plot.width
}

function scaleY(value: number) {
  return plot.bottom - ((value - yDomain[0]) / (yDomain[1] - yDomain[0])) * plot.height
}

function profileScaleValue(value: number) {
  return (value / profile.domain) * profile.radius
}

function profileScale(value: number) {
  return profileScaleValue(value)
}

function usageRadius(point: { usage: number }) {
  return proportionalUsageRadius(point.usage)
}

function leagueRadius(point: { leagueUsage: number | null }) {
  return point.leagueUsage === null ? 0 : proportionalUsageRadius(point.leagueUsage)
}

function proportionalUsageRadius(usage: number) {
  const boundedUsage = Math.min(50, Math.max(0, usage))
  return boundedUsage > 0 ? 9 + Math.sqrt(boundedUsage / 50) * 29 : 9
}

function infoX(index: number) {
  return [146, 236, 326, 416, 506][index] || 146
}

function infoY(groupIndex: number, key: 'dot' | 'pitch' | 'usage' | 'mph' | 'avg') {
  const rows = [
    { dot: 536, pitch: 568, usage: 600, mph: 632, avg: 664 },
    { dot: 696, pitch: 728, usage: 760, mph: 792, avg: 824 }
  ]
  return rows[groupIndex]?.[key] || rows[0][key]
}

function displayPitch(pitch: string) {
  return pitch === 'Four-Seam' ? '4-Seam' : pitch
}

function normalizePitchKey(pitch: string) {
  return displayPitch(pitch).toLowerCase().replace(/[^a-z0-9]/g, '')
}

function findLeagueValue(row: Record<string, unknown> | undefined, metric: 'Usage%' | 'HB' | 'IVB' | 'Velo') {
  if (!row) {
    return null
  }
  const direct = row[`League ${props.pitcherHand === 'L' ? 'LHP' : 'RHP'} ${metric}`] ?? row[`League ${props.pitcherHand} ${metric}`]
  if (direct !== undefined) {
    return direct
  }
  const key = Object.keys(row).find((name) => name.includes('League') && name.endsWith(metric))
  return key ? row[key] : null
}

function numberOrNull(value: unknown) {
  if (value === null || value === undefined || value === '') return null
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

function numberOrZero(value: unknown) {
  return numberOrNull(value) ?? 0
}

function formatOne(value: number | null) {
  return value === null ? '-' : value.toFixed(1)
}

function profileTooltip(point: {
  pitch: string
  usage: number
  velocity: number | null
  x: number
  y: number
  leagueVelo: number | null
  leagueX: number | null
  leagueY: number | null
}) {
  return [
    displayPitch(point.pitch),
    `Usage ${point.usage.toFixed(1)}%`,
    `MPH ${formatOne(point.velocity)}`,
    `HB ${point.x.toFixed(1)}`,
    `IVB ${point.y.toFixed(1)}`,
    `${leagueAverageLabel.value} Velo ${formatOne(point.leagueVelo)}`,
    `${leagueAverageLabel.value} HB ${formatOne(point.leagueX)}`,
    `${leagueAverageLabel.value} IVB ${formatOne(point.leagueY)}`
  ].join('\n')
}

function leagueTooltip(point: {
  pitch: string
  leagueUsage: number | null
  leagueVelo: number | null
  leagueX: number | null
  leagueY: number | null
}) {
  return [
    `${displayPitch(point.pitch)} · ${leagueAverageLabel.value}`,
    `Usage ${formatOne(point.leagueUsage)}%`,
    `MPH ${formatOne(point.leagueVelo)}`,
    `HB ${formatOne(point.leagueX)}`,
    `IVB ${formatOne(point.leagueY)}`
  ].join('\n')
}

function slug(value: string) {
  return normalizePitchKey(value) || 'unknown'
}

function colorForPitch(pitch: string) {
  return pitchColors[pitch] || defaultPitchColor
}

function showStuffColors() {
  stuffColorRequested.value = true
  emit('update:mode', 'scatter')
  if (hasStuffScores.value) {
    colorMode.value = 'stuff'
    return
  }
  if (!props.stuffColorLoading) emit('request-stuff-colors')
}

function pointColor(point: { pitch: string; stuffPlus: number | null }) {
  if (colorMode.value === 'pitch') return colorForPitch(point.pitch)
  const score = point.stuffPlus
  if (score === null) return hasStuffScores.value ? defaultPitchColor : colorForPitch(point.pitch)
  const distance = Math.min(1, Math.abs(score - 100) / 18)
  const intensity = Math.pow(distance, 0.55)
  return score < 100
    ? mixColor('#f3f0e8', '#304ffe', intensity)
    : mixColor('#f3f0e8', '#f02f24', intensity)
}

watch(hasStuffScores, (available) => {
  if (available && stuffColorRequested.value) colorMode.value = 'stuff'
})

function mixColor(from: string, to: string, amount: number) {
  const start = from.match(/[a-f\d]{2}/gi)?.map((value) => Number.parseInt(value, 16)) || [0, 0, 0]
  const end = to.match(/[a-f\d]{2}/gi)?.map((value) => Number.parseInt(value, 16)) || [0, 0, 0]
  const mixed = start.map((value, index) => Math.round(value + ((end[index] || 0) - value) * Math.max(0, Math.min(1, amount))))
  return `rgb(${mixed.join(', ')})`
}

function scatterTooltip(point: { pitch: string; x: number; y: number; stuffPlus: number | null; locationPlus: number | null; staminaPlus: number | null; expectedStuffPlus: number | null; expectedRetentionDelta: number | null; staminaSample: string }) {
  const fields = [point.pitch, `HB ${point.x.toFixed(1)}`, `IVB ${point.y.toFixed(1)}`]
  if (point.stuffPlus !== null) fields.push(`Pitch Stuff+ ${point.stuffPlus.toFixed(1)}`)
  if (point.locationPlus !== null) fields.push(`Location+ ${point.locationPlus.toFixed(1)}`)
  if (point.staminaPlus !== null) fields.push(`Stamina+ trait ${point.staminaPlus.toFixed(1)}${point.staminaSample ? ` (${point.staminaSample})` : ''}`)
  if (point.expectedRetentionDelta !== null) fields.push(`Expected retention ${point.expectedRetentionDelta >= 0 ? '+' : ''}${point.expectedRetentionDelta.toFixed(1)}`)
  if (point.expectedStuffPlus !== null) fields.push(`Expected Stuff+ ${point.expectedStuffPlus.toFixed(1)}`)
  return fields.join(' | ')
}

function pitchPointKey(row: Record<string, unknown>) {
  return [row.game_pk, row.at_bat_number, row.pitch_number, row.plate_x, row.plate_z, row.pitch_name]
    .map(value => String(value ?? '')).join('|')
}
</script>

<style scoped>
.movement-chart {
  width: 100%;
  justify-self: start;
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.chart-header {
  display: flex;
  align-items: center;
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

.chart-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mode-toggle,
.color-toggle {
  display: inline-flex;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-surface);
}

.mode-toggle button,
.color-toggle button {
  min-height: 34px;
  border: 0;
  padding: 7px 11px;
  color: var(--color-muted-text);
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}

.mode-toggle button.active,
.color-toggle button.active {
  color: var(--color-on-primary);
  background: var(--color-primary);
}

.color-toggle button.active {
  color: var(--color-foreground);
  background: color-mix(in srgb, var(--color-primary) 18%, var(--color-surface));
}

.plot-wrap {
  overflow-x: auto;
  padding: 8px 10px 0;
}

.scatter-svg,
.profile-svg {
  display: block;
  width: 100%;
  height: auto;
}

.plot-bg {
  fill: var(--color-plot-bg);
}

.grid line {
  stroke: var(--color-border);
  stroke-width: 1;
}

.grid .zero {
  stroke: #94a3b8;
  stroke-width: 1.5;
}

.axis-labels text {
  fill: var(--color-muted-text);
  font-size: 13px;
  text-anchor: middle;
}

.scatter-svg circle {
  opacity: 0.78;
  stroke: #020617 !important;
  stroke-width: 1.4 !important;
  vector-effect: non-scaling-stroke;
}

.scatter-svg .pitch-dot[role="button"] {
  cursor: pointer;
}

.scatter-svg .pitch-dot[role="button"].selected,
.scatter-svg .pitch-dot[role="button"]:focus-visible {
  stroke: #fff !important;
  stroke-width: 3 !important;
  opacity: 1;
  outline: none;
}

.movement-chart.stuff-color-mode .scatter-svg circle {
  opacity: 0.96;
  stroke: rgba(2, 6, 23, 0.78) !important;
  stroke-width: 1.15 !important;
}

.movement-chart.stuff-color-mode .scatter-svg .pitch-dot[role="button"].selected,
.movement-chart.stuff-color-mode .scatter-svg .pitch-dot[role="button"]:focus-visible {
  stroke: #fff !important;
  stroke-width: 3 !important;
  opacity: 1;
}

.stuff-legend {
  display: grid;
  grid-template-columns: auto minmax(150px, 280px) auto auto auto;
  align-items: center;
  justify-content: center;
  gap: 9px;
  padding: 12px 16px 18px;
  color: var(--color-muted-text);
  font-size: 11px;
  font-weight: 800;
}

.stuff-legend i {
  grid-column: 2 / 4;
  grid-row: 1;
  width: 100%;
  height: 9px;
  border-radius: 999px;
  background: linear-gradient(90deg, #304ffe 0%, #6f7cff 28%, #f3f0e8 50%, #ff796b 72%, #f02f24 100%);
  box-shadow: 0 0 14px rgba(83, 91, 255, 0.2), 0 0 14px rgba(240, 47, 36, 0.18);
}

.stuff-legend span:nth-of-type(1) { grid-column: 1; }
.stuff-legend span:nth-of-type(2) { grid-column: 2; justify-self: center; z-index: 1; color: #334155; }
.stuff-legend span:nth-of-type(3) { grid-column: 4; }
.stuff-legend strong { grid-column: 5; color: var(--color-foreground); }

@media (max-width: 700px) {
  .chart-header { align-items: flex-start; }
  .chart-actions { align-items: stretch; flex-direction: column; }
}

.profile-svg .pitch-outline {
  vector-effect: non-scaling-stroke;
}

.movement-chart.no-point-outline .scatter-svg circle,
.movement-chart.no-point-outline .profile-svg .pitch-dot,
.movement-chart.no-point-outline .profile-svg .pitch-bubble {
  stroke: transparent;
  stroke-width: 0;
}

.scatter-svg g > text {
  fill: var(--color-text);
  font-size: 12px;
  font-weight: 700;
}

.profile-wrap {
  padding: 0;
  overflow: hidden;
  background: var(--color-surface);
}

.profile-bg,
.profile-center-bg {
  fill: var(--color-plot-bg);
}

.profile-title {
  fill: var(--color-text);
  font-size: 25px;
  font-weight: 650;
  text-anchor: middle;
}

.profile-ring {
  fill: none;
  stroke: #64748b;
  stroke-width: 2;
  opacity: 0.55;
}

.profile-ring.dashed {
  stroke-dasharray: 8 10;
}

.profile-zero {
  stroke: #64748b;
  stroke-width: 2.2;
  opacity: 0.6;
}

.toward-label,
.profile-tick,
.arm-angle {
  fill: var(--color-muted-text);
  font-size: 14px;
  text-anchor: middle;
}

.profile-tick {
  font-size: 13px;
}

.arm-angle {
  white-space: pre;
  font-size: 13px;
  text-anchor: middle;
}

.profile-info text {
  text-anchor: middle;
}

.info-heading {
  fill: #64748b;
  font-size: 13px;
  text-anchor: start !important;
}

.info-value {
  fill: var(--color-text);
  font-size: 13px;
}

.info-muted {
  fill: var(--color-muted-text);
  font-size: 13px;
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

@media (max-width: 860px) {
  .movement-chart {
    width: 100%;
  }
}
</style>
