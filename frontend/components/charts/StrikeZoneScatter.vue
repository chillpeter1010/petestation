<template>
  <section class="zone-chart" :class="{ compact }">
    <header class="chart-header">
      <h2>{{ title || 'Pitch Location Scatter' }}</h2>
      <span>{{ subtitle }}</span>
    </header>
    <div class="plot-wrap">
      <svg :viewBox="viewBox" role="img" aria-label="Pitch location scatter plot">
        <defs>
          <filter id="heatmap-blur" x="-12%" y="-12%" width="124%" height="124%">
            <feGaussianBlur stdDeviation="1.15" />
          </filter>
        </defs>
        <g :transform="plotTransform">
        <rect class="plot-bg" :x="plot.left" :y="plot.top" :width="plot.width" :height="plot.height" />

        <g class="grid">
          <line v-for="tick in xTicks" :key="`x-${tick}`" :x1="scaleX(tick)" :x2="scaleX(tick)" :y1="plot.top" :y2="plot.bottom" />
          <line v-for="tick in yTicks" :key="`y-${tick}`" :x1="plot.left" :x2="plot.right" :y1="scaleY(tick)" :y2="scaleY(tick)" />
        </g>

        <g class="axis-labels">
          <text v-for="tick in xTicks" :key="`xl-${tick}`" :x="scaleX(tick)" :y="plot.bottom + 28">{{ tick }}</text>
          <text v-for="tick in yTicks" :key="`yl-${tick}`" :x="plot.left - 18" :y="scaleY(tick) + 4">{{ tick }}</text>
          <text :x="plot.left + plot.width / 2" :y="plot.bottom + 56">plate_x</text>
          <text :x="22" :y="plot.top + plot.height / 2" transform="rotate(-90 22 240)">plate_z</text>
        </g>

        <g v-if="heatmapCells.length" class="heatmap" filter="url(#heatmap-blur)">
          <rect
            v-for="cell in heatmapCells"
            :key="`${cell.x}-${cell.z}`"
            :x="scaleX(cell.x0)"
            :y="scaleY(cell.z1)"
            :width="scaleX(cell.x1) - scaleX(cell.x0)"
            :height="scaleY(cell.z0) - scaleY(cell.z1)"
            :fill="cell.color"
            :opacity="cell.opacity"
            :stroke="cell.stroke"
            :stroke-opacity="cell.strokeOpacity"
            stroke-width="0.9"
          />
        </g>

        <g class="zone-guides">
          <rect
            v-for="band in zoneBands"
            :key="band.key"
            :class="band.key"
            :x="scaleX(band.x)"
            :y="scaleY(band.z + band.h)"
            :width="scaleX(band.x + band.w) - scaleX(band.x)"
            :height="scaleY(band.z) - scaleY(band.z + band.h)"
          />
          <line
            v-for="line in heartGuideLines"
            :key="line.key"
            :class="line.kind"
            :x1="scaleX(line.x1)"
            :x2="scaleX(line.x2)"
            :y1="scaleY(line.z1)"
            :y2="scaleY(line.z2)"
          />
        </g>
        <polyline class="plate" :points="platePoints" />

        <g v-if="showPoints">
          <circle
            v-for="(point, index) in plottedPoints"
            :key="index"
            :cx="scaleX(point.x)"
            :cy="scaleY(point.z)"
            :r="(compact ? 5.2 : 4.32) * pointScale"
            :fill="colorForPitch(point.pitch)"
            :opacity="pointOpacity"
            :class="{ selected: selectedKey && selectedKey === point.key }"
            tabindex="0"
            role="button"
            @mouseenter="hoveredPoint = point"
            @mouseleave="hoveredPoint = null"
            @focus="hoveredPoint = point"
            @blur="hoveredPoint = null"
            @click="emit('select-point', point.raw)"
            @keydown.enter.prevent="emit('select-point', point.raw)"
            @keydown.space.prevent="emit('select-point', point.raw)"
          />
        </g>

        <g v-if="hoveredPoint" class="hover-card">
          <rect :x="hoverCard.x" :y="hoverCard.y" :width="hoverCard.width" height="176" rx="6" />
          <text :x="hoverCard.textX" :y="hoverCard.y + 26" class="hover-title">{{ hoveredPoint.date }}</text>
          <text :x="hoverCard.textX" :y="hoverCard.y + 50">Pitch {{ hoveredPoint.pitch }}</text>
          <text :x="hoverCard.textX" :y="hoverCard.y + 74">Desc {{ hoveredPoint.description || '-' }}</text>
          <text :x="hoverCard.textX" :y="hoverCard.y + 98">Video {{ hoveredPoint.video }}</text>
          <text :x="hoverCard.textX" :y="hoverCard.y + 122">Stuff+ {{ hoveredPoint.stuffPlus }}</text>
          <text :x="hoverCard.textX" :y="hoverCard.y + 146">Location+ {{ hoveredPoint.locationPlus }}</text>
        </g>
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
const props = withDefaults(defineProps<{
  points: Array<Record<string, unknown>>
  totalPitches?: number | null
  title?: string
  selectedKey?: string | null
  heatmapBlend?: number
  compact?: boolean
  pointScale?: number
  plotScale?: number
  heatmapMode?: 'density' | 'bat-speed' | 'choice'
  showPoints?: boolean
}>(), {
  showPoints: true
})

const emit = defineEmits<{
  'select-point': [point: Record<string, unknown>]
}>()

const compact = computed(() => Boolean(props.compact))
const showPoints = computed(() => props.showPoints !== false)
const heatmapMode = computed(() => props.heatmapMode || 'density')
const pointScale = computed(() => {
  const scale = Number(props.pointScale || 1)
  return Number.isFinite(scale) ? Math.max(0.2, scale) : 1
})
const plotScale = computed(() => {
  const scale = Number(props.plotScale || 1)
  return Number.isFinite(scale) ? Math.max(0.5, scale) : 1
})
const viewBox = computed(() => compact.value ? '0 0 520 586' : '0 0 760 560')

const hoveredPoint = ref<{
  x: number
  z: number
  pitch: string
  description: string
  date: string
  count: string
  velo: string
  video: 'Y' | 'N'
  stuffPlus: string
  locationPlus: string
  key: string
  raw: Record<string, unknown>
} | null>(null)

const regularPlot = {
  left: 66,
  top: 28,
  right: 606,
  bottom: 478,
  width: 540,
  height: 450
}

const compactPlot = {
  left: 42,
  top: 22,
  right: 478,
  bottom: 498,
  width: 436,
  height: 476
}

const plot = computed(() => compact.value ? compactPlot : regularPlot)
const plotTransform = computed(() => {
  if (plotScale.value === 1) {
    return ''
  }
  const activePlot = plot.value
  const cx = activePlot.left + activePlot.width / 2
  const cy = activePlot.top + activePlot.height / 2
  return `translate(${cx} ${cy}) scale(${plotScale.value}) translate(${-cx} ${-cy})`
})
const hoverCard = computed(() => compact.value
  ? { x: 270, y: 28, width: 222, textX: 284 }
  : { x: 482, y: 36, width: 234, textX: 498 })
const xDomain = computed(() => compact.value ? [-2.2, 2.2] as const : [-3, 3] as const)
const yDomain = computed(() => compact.value ? [0, 4.8] as const : [0, 5] as const)
const xTicks = computed(() => compact.value ? [-2, -1, 0, 1, 2] : [-3, -2, -1, 0, 1, 2, 3])
const yTicks = computed(() => compact.value ? [0, 1, 2, 3, 4] : [0, 1, 2, 3, 4, 5])
const strikeZone = { x: -0.83, z: 1.5, w: 1.66, h: 2.0 }
const shadowZone = { x: -1.33, z: 1.17, w: 2.66, h: 2.66 }
const chaseZone = { x: -2.0, z: 0.5, w: 4.0, h: 4.0 }
const expandedHeartX = [-0.67, 0.67] as const
const expandedShadowVerticalExtension = 0.33
const heartZone = {
  x: expandedHeartX[0],
  z: strikeZone.z + expandedShadowVerticalExtension,
  w: expandedHeartX[1] - expandedHeartX[0],
  h: strikeZone.h - expandedShadowVerticalExtension * 2
}
const zoneBands = [
  { key: 'chase-zone', ...chaseZone },
  { key: 'shadow-zone', ...shadowZone },
  { key: 'strike-zone', ...strikeZone },
  { key: 'heart-zone', ...heartZone }
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

const plottedPoints = computed(() => {
  return props.points.flatMap((point) => {
    const x = Number(point.plate_x) * -1
    const z = Number(point.plate_z)
    if (!Number.isFinite(x) || !Number.isFinite(z)) {
      return []
    }
    return [{
      x,
      z,
      pitch: String(point.pitch_name || point.Pitch || 'Unknown'),
      description: String(point.description || point.events || ''),
      date: String(point.game_date || '').slice(0, 10) || '-',
      count: `${point.balls ?? '-'}-${point.strikes ?? '-'}`,
      velo: formatVelo(point.release_speed),
      video: videoFlag(point),
      stuffPlus: formatPlusScore(point.pitch_stuff_plus ?? point.stuff_plus),
      locationPlus: formatPlusScore(point.location_plus_pitch ?? point.location_plus),
      batSpeed: nullableNumber(point.bat_speed),
      swung: Boolean(point.is_swing),
      key: pitchPointKey(point),
      raw: point
    }]
  })
})

const legendItems = computed(() => {
  return [...new Set(plottedPoints.value.map((point) => point.pitch))]
})

const heatmapBlend = computed(() => {
  const blend = Number(props.heatmapBlend || 0)
  return Number.isFinite(blend) ? Math.max(0, Math.min(1, blend)) : 0
})

const pointOpacity = computed(() => Math.max(0.16, 0.78 * (1 - heatmapBlend.value * 0.78)))

const heatmapCells = computed(() => {
  if (heatmapBlend.value <= 0 || plottedPoints.value.length < 8) {
    return []
  }
  const xBins = 64
  const zBins = 52
  const activeXDomain = xDomain.value
  const activeYDomain = yDomain.value
  const xStep = (activeXDomain[1] - activeXDomain[0]) / xBins
  const zStep = (activeYDomain[1] - activeYDomain[0]) / zBins
  const sigmaX = 0.18
  const sigmaZ = 0.2
  const usablePoints = plottedPoints.value.filter((point) => (
    point.x >= activeXDomain[0]
    && point.x <= activeXDomain[1]
    && point.z >= activeYDomain[0]
    && point.z <= activeYDomain[1]
  ))
  const densityCells: Array<{ xi: number; zi: number; density: number; metric: number | null }> = []
  let maxDensity = 0

  for (let xi = 0; xi < xBins; xi += 1) {
    const xCenter = activeXDomain[0] + (xi + 0.5) * xStep
    for (let zi = 0; zi < zBins; zi += 1) {
      const zCenter = activeYDomain[0] + (zi + 0.5) * zStep
      let density = 0
      let metricTotal = 0
      let metricWeight = 0
      for (const point of usablePoints) {
        const dx = (xCenter - point.x) / sigmaX
        const dz = (zCenter - point.z) / sigmaZ
        const distanceSquared = dx * dx + dz * dz
        if (distanceSquared <= 9) {
          const weight = Math.exp(-0.5 * distanceSquared)
          density += weight
          const metricValue = heatmapMode.value === 'bat-speed'
            ? point.batSpeed
            : heatmapMode.value === 'choice'
              ? (point.swung ? 1 : 0)
              : null
          if (metricValue !== null) {
            metricTotal += metricValue * weight
            metricWeight += weight
          }
        }
      }
      if (density > 0 && (heatmapMode.value === 'density' || metricWeight > 0)) {
        densityCells.push({ xi, zi, density, metric: metricWeight ? metricTotal / metricWeight : null })
        maxDensity = Math.max(maxDensity, density)
      }
    }
  }

  if (!maxDensity) {
    return []
  }
  const metricValues = densityCells.map((cell) => cell.metric).filter((value): value is number => value !== null)
  const metricMin = metricValues.length ? Math.min(...metricValues) : 0
  const metricMax = metricValues.length ? Math.max(...metricValues) : 1
  return densityCells.flatMap(({ xi, zi, density, metric }) => {
    const normalized = density / maxDensity
    if (normalized < 0.045) {
      return []
    }
    const rawColorValue = heatmapMode.value === 'density'
      ? Math.min(1, Math.pow(normalized, 0.58))
      : heatmapMode.value === 'choice'
        ? Number(metric)
        : (Number(metric) - metricMin) / (metricMax - metricMin || 1)
    const colorValue = heatmapMode.value === 'density' ? contourLevel(rawColorValue) : Math.max(0, Math.min(1, rawColorValue))
    return {
      x: xi,
      z: zi,
      x0: activeXDomain[0] + xi * xStep - xStep * 0.16,
      x1: activeXDomain[0] + (xi + 1) * xStep + xStep * 0.16,
      z0: activeYDomain[0] + zi * zStep - zStep * 0.16,
      z1: activeYDomain[0] + (zi + 1) * zStep + zStep * 0.16,
      color: heatColor(colorValue),
      stroke: heatStroke(colorValue),
      strokeOpacity: heatmapBlend.value * 0.34,
      opacity: heatmapBlend.value * (0.35 + 0.65 * Math.min(1, Math.pow(normalized, 0.5)))
    }
  })
})

const subtitle = computed(() => {
  const sample = plottedPoints.value.length.toLocaleString()
  if (props.totalPitches && props.totalPitches > plottedPoints.value.length) {
    return `${sample} shown / ${props.totalPitches.toLocaleString()} total`
  }
  return `${sample} pitches`
})

const platePoints = computed(() => {
  const points = [
    [-0.83, 0.28],
    [-0.42, 0.12],
    [0, 0],
    [0.42, 0.12],
    [0.83, 0.28]
  ]
  return points.map(([x, y]) => `${scaleX(x)},${scaleY(y)}`).join(' ')
})

const heartGuideLines = computed(() => {
  const x1 = heartZone.x
  const x2 = heartZone.x + heartZone.w
  const z1 = heartZone.z
  const z2 = heartZone.z + heartZone.h
  const thirdW = heartZone.w / 3
  const thirdH = heartZone.h / 3
  return [
    { key: 'heart-v1', kind: 'heart-line', x1: x1 + thirdW, x2: x1 + thirdW, z1, z2 },
    { key: 'heart-v2', kind: 'heart-line', x1: x1 + thirdW * 2, x2: x1 + thirdW * 2, z1, z2 },
    { key: 'heart-h1', kind: 'heart-line', x1, x2, z1: z1 + thirdH, z2: z1 + thirdH },
    { key: 'heart-h2', kind: 'heart-line', x1, x2, z1: z1 + thirdH * 2, z2: z1 + thirdH * 2 }
  ]
})

function scaleX(value: number) {
  const activePlot = plot.value
  const activeDomain = xDomain.value
  return activePlot.left + ((value - activeDomain[0]) / (activeDomain[1] - activeDomain[0])) * activePlot.width
}

function scaleY(value: number) {
  const activePlot = plot.value
  const activeDomain = yDomain.value
  return activePlot.bottom - ((value - activeDomain[0]) / (activeDomain[1] - activeDomain[0])) * activePlot.height
}

function colorForPitch(pitch: string) {
  return pitchColors[pitch] || defaultPitchColor
}

function heatColor(value: number) {
  const clamped = Math.max(0, Math.min(1, value))
  if (clamped < 0.33) {
    return interpolateColor([15, 23, 96], [37, 99, 235], clamped / 0.33)
  }
  if (clamped < 0.55) {
    return interpolateColor([37, 99, 235], [239, 246, 255], (clamped - 0.33) / 0.22)
  }
  if (clamped < 0.75) {
    return interpolateColor([255, 237, 213], [239, 68, 68], (clamped - 0.55) / 0.2)
  }
  return interpolateColor([239, 68, 68], [127, 29, 29], (clamped - 0.75) / 0.25)
}

function heatStroke(value: number) {
  return value < 0.55 ? 'rgb(30, 64, 175)' : 'rgb(153, 27, 27)'
}

function contourLevel(value: number) {
  const levels = [0.16, 0.28, 0.4, 0.52, 0.64, 0.76, 0.88, 1]
  return levels.find((level) => value <= level) || 1
}

function interpolateColor(from: [number, number, number], to: [number, number, number], t: number) {
  const channels = from.map((value, index) => Math.round(value + (to[index] - value) * t))
  return `rgb(${channels[0]}, ${channels[1]}, ${channels[2]})`
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

function formatVelo(value: unknown) {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? `${numberValue.toFixed(1)} mph` : '-'
}

function formatPlusScore(value: unknown) {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue.toFixed(1) : '—'
}

function nullableNumber(value: unknown) {
  const numberValue = Number(value)
  return value === null || value === undefined || value === '' || !Number.isFinite(numberValue) ? null : numberValue
}

function hasVideo(point: Record<string, unknown>) {
  const videoUrl = String(point.video_url || '').trim()
  const playId = String(point.play_id || '').trim()
  return Boolean(
    (videoUrl && videoUrl !== 'None' && videoUrl !== 'nan')
    || (playId && playId !== 'None' && playId !== 'nan')
  )
}

function videoFlag(point: Record<string, unknown>): 'Y' | 'N' {
  return hasVideo(point) ? 'Y' : 'N'
}
</script>

<style scoped>
.zone-chart {
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

.plot-wrap {
  overflow-x: auto;
  padding: 8px 10px 0;
}

svg {
  display: block;
  width: 100%;
  min-width: 620px;
  height: auto;
}

.compact .chart-header {
  padding: 9px 10px;
}

.compact .chart-header h2 {
  font-size: 13px;
}

.compact .chart-header span {
  font-size: 12px;
}

.compact .plot-wrap {
  padding: 4px 6px 0;
  overflow: hidden;
}

.compact svg {
  min-width: 0;
  max-height: 360px;
}

.compact .axis-labels text {
  font-size: 11px;
}

.compact .legend {
  display: none;
}

.compact .plot-bg {
  fill: var(--color-plot-bg);
}

.compact .grid line {
  stroke: var(--color-border);
  stroke-width: 1.8;
}

.compact .chase-zone {
  stroke: #d9c26a;
  stroke-dasharray: 7 5;
  stroke-width: 2;
  opacity: 0.78;
}

.compact .shadow-zone {
  stroke: #8fc8ef;
  stroke-dasharray: 7 5;
  stroke-width: 2.1;
  opacity: 0.82;
}

.compact .strike-zone {
  stroke: #d62828;
  stroke-width: 2.6;
  opacity: 0.95;
}

.compact .heart-zone {
  stroke: #7b2cbf;
  stroke-width: 2.5;
  opacity: 0.95;
}

.compact .heart-line {
  stroke: #7b2cbf;
  stroke-width: 1.6;
  opacity: 0.65;
}

.compact .plate {
  stroke: var(--color-text);
  stroke-width: 3;
}

.plot-bg {
  fill: var(--color-plot-bg);
}

.grid line {
  stroke: var(--color-border);
  stroke-width: 2;
}

.axis-labels text {
  fill: var(--color-muted-text);
  font-size: 13px;
  text-anchor: middle;
}

.zone-guides rect {
  fill: none;
}

.chase-zone {
  stroke: #d9c26a;
  stroke-dasharray: 8 6;
  stroke-width: 2.8;
  opacity: 0.75;
}

.shadow-zone {
  stroke: #8fc8ef;
  stroke-dasharray: 7 6;
  stroke-width: 3;
  opacity: 0.8;
}

.strike-zone {
  stroke: var(--color-text);
  stroke-width: 4.4;
}

.heart-zone {
  stroke: #7a6281;
  stroke-width: 3.6;
  opacity: 0.95;
}

.heart-line {
  stroke: #7a6281;
  stroke-width: 2.2;
  opacity: 0.75;
}

.plate {
  fill: none;
  stroke: var(--color-text);
  stroke-width: 4;
}

circle {
  stroke: rgba(2, 6, 23, 0.82);
  stroke-width: 0.7;
  cursor: pointer;
}

circle.selected {
  opacity: 1;
  stroke: #020617;
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

.hover-card rect {
  fill: rgba(15, 23, 42, 0.9);
  stroke: rgba(226, 232, 240, 0.5);
  stroke-width: 1;
}

.hover-card text {
  fill: #dbeafe;
  font-size: 13px;
}

.hover-card .hover-title {
  fill: #ffffff;
  font-size: 15px;
  font-weight: 700;
}
</style>
