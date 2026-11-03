<template>
  <section class="replay-chart" aria-label="Pitch trajectory replay">
    <header class="replay-header">
      <div>
        <h3>Pitch Replay</h3>
        <p>Statcast constant-acceleration reconstruction · ball path only</p>
      </div>
      <span :class="['status-badge', trajectoryStatus]">{{ statusLabel }}</span>
    </header>

    <div class="replay-controls">
      <label>Pitch
        <select v-model="selectedKey">
          <option v-for="row in sortedRows" :key="rowKey(row)" :value="rowKey(row)">{{ pitchOptionLabel(row) }}</option>
        </select>
      </label>
      <label>Playback
        <select v-model="playMode">
          <option value="pitch">Single pitch</option>
          <option value="pa">Plate appearance</option>
          <option value="game">This game</option>
        </select>
      </label>
      <label>Speed
        <select v-model.number="playbackRate">
          <option :value="0.25">0.25×</option>
          <option :value="0.5">0.5×</option>
          <option :value="1">1×</option>
        </select>
      </label>
      <div class="button-row">
        <button type="button" :disabled="!pathPoints.length || isPlaying" @click="play(false)">Play</button>
        <button type="button" class="secondary" :disabled="!isPlaying" @click="pause">Pause</button>
        <button type="button" :disabled="!pathPoints.length" @click="replay">Replay</button>
      </div>
      <label class="timeline">Timeline
        <input v-model.number="progress" type="range" min="0" max="1" step="0.001" :disabled="!pathPoints.length" @input="pause">
        <span v-if="playMode !== 'pitch'">0.7 s between pitches</span>
      </label>
    </div>

    <p v-if="reducedMotion" class="motion-note">Reduced motion is enabled. The path stays static until you press Play or Replay.</p>
    <p v-if="trajectoryReason" class="trajectory-note">{{ trajectoryReason }}</p>

    <div v-if="pathPoints.length" class="replay-stage">
      <div class="stage-toolbar">
        <div class="toolbar-group" aria-label="Camera viewpoint">
          <span>View</span>
          <div class="segmented-control">
            <button type="button" :class="{ active: activeView === 'pitcher' }" :aria-pressed="activeView === 'pitcher'" @click="setView('pitcher')">Pitcher</button>
            <button type="button" :class="{ active: activeView === 'catcher' }" :aria-pressed="activeView === 'catcher'" @click="setView('catcher')">Catcher</button>
          </div>
        </div>
        <div class="toolbar-group" aria-label="Comparison pitches">
          <span>Compare</span>
          <div class="segmented-control">
            <button type="button" :class="{ active: comparisonScope === 'pa' }" :aria-pressed="comparisonScope === 'pa'" @click="comparisonScope = 'pa'">This PA</button>
            <button type="button" :class="{ active: comparisonScope === 'game' }" :aria-pressed="comparisonScope === 'game'" @click="comparisonScope = 'game'">This game</button>
          </div>
        </div>
        <div class="camera-actions">
          <button type="button" class="camera-button" @click="setLowCamera">Low angle</button>
          <button type="button" class="camera-button" @click="resetCamera">Reset angle</button>
        </div>
      </div>

      <div class="scene-shell">
        <svg
          class="trajectory-scene"
          :class="{ dragging }"
          viewBox="0 0 960 560"
          role="img"
          :aria-label="`${pitchName} trajectory from the ${activeView} view. Drag to adjust the camera angle.`"
          tabindex="0"
          @pointerdown="startCameraDrag"
          @pointermove="moveCamera"
          @pointerup="stopCameraDrag"
          @pointercancel="stopCameraDrag"
          @lostpointercapture="stopCameraDrag"
          @keydown="moveCameraWithKeyboard"
          @wheel.prevent="zoomCamera"
        >
          <defs>
            <linearGradient id="replay-sky" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#070d18" />
              <stop offset="1" stop-color="#101b2c" />
            </linearGradient>
            <linearGradient id="replay-turf" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#1c4a3d" />
              <stop offset="1" stop-color="#102b27" />
            </linearGradient>
            <filter id="ball-glow" x="-200%" y="-200%" width="500%" height="500%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          <rect width="960" height="560" fill="url(#replay-sky)" />
          <polygon class="field" :points="groundPolygon" />
          <polygon class="dirt-lane" :points="dirtLanePolygon" />
          <polyline v-for="(line, index) in fieldLines" :key="`field-${index}`" class="field-line" :points="line" />
          <polygon class="mound" :points="moundPolygon" />
          <line v-if="rubberLine" class="rubber" :x1="rubberLine[0].x" :y1="rubberLine[0].y" :x2="rubberLine[1].x" :y2="rubberLine[1].y" />
          <polygon class="plate" :points="homePlatePolygon" />

          <image v-if="batterFigure" class="batter-silhouette" :href="batterFigure.asset" width="179" height="478" :transform="batterFigure.transform" preserveAspectRatio="xMidYMax meet" aria-hidden="true" />

          <polygon class="strike-zone" :points="strikeZonePolygon"><title>Statcast strike zone: 17-inch plate width by batter sz_bot / sz_top</title></polygon>
          <line v-for="(line, index) in strikeZoneGridLines" :key="`zone-grid-${index}`" class="strike-zone-grid" :x1="line[0].x" :y1="line[0].y" :x2="line[1].x" :y2="line[1].y" />

          <g class="comparison-trajectories" aria-hidden="true">
            <polyline v-for="path in contextPaths" :key="path.key" class="comparison-path" :style="{ stroke: path.color }" :points="path.points"><title>{{ path.label }}</title></polyline>
            <circle v-for="path in contextPaths" :key="`${path.key}-release`" class="comparison-release" :style="{ fill: path.color }" :cx="path.release.x" :cy="path.release.y" r="3.5" />
          </g>

          <polyline class="selected-path-shadow" :points="selectedProjectedPath" />
          <polyline class="selected-full-path" :style="{ stroke: pitchColor }" :points="selectedProjectedPath" />
          <polyline class="selected-played-path" :style="{ stroke: pitchColor }" :points="playedProjectedPath" />
          <circle v-if="releaseScreenPoint" class="selected-release-ring" :cx="releaseScreenPoint.x" :cy="releaseScreenPoint.y" r="8" />
          <circle v-if="releaseScreenPoint" class="selected-release" :style="{ fill: pitchColor }" :cx="releaseScreenPoint.x" :cy="releaseScreenPoint.y" r="4.5" />
          <circle v-if="currentScreenPoint" class="ball-halo" :cx="currentScreenPoint.x" :cy="currentScreenPoint.y" r="7.8" />
          <circle v-if="currentScreenPoint" class="ball" :cx="currentScreenPoint.x" :cy="currentScreenPoint.y" r="3.9"><title>{{ ballTooltip }}</title></circle>

          <g class="scene-hud" aria-hidden="true">
            <rect x="24" y="22" width="300" height="106" rx="9" />
            <text x="42" y="48" class="hud-title">{{ activeView === 'pitcher' ? 'PITCHER VIEW' : 'CATCHER VIEW' }}</text>
            <text x="42" y="72" class="hud-copy">Drag to orbit · wheel to zoom</text>
            <text x="42" y="92" class="hud-copy">{{ contextPaths.length }} comparison {{ contextPaths.length === 1 ? 'pitch' : 'pitches' }} · elevation {{ cameraElevationLabel }}</text>
            <text x="42" y="112" class="hud-copy">Statcast zone · 3×3 grid</text>
          </g>
          <g class="scene-orientation" aria-hidden="true">
            <line x1="846" y1="505" x2="898" y2="505" />
            <line x1="846" y1="505" x2="846" y2="458" />
            <text x="907" y="510">X</text>
            <text x="840" y="449">Z</text>
          </g>
        </svg>

        <div class="scene-caption">
          <div>
            <span class="pitch-swatch" :style="{ background: pitchColor }" />
            <b>{{ pitchName }}</b>
            <span>PA {{ selectedRow?.at_bat_number ?? '—' }} · Pitch {{ selectedRow?.pitch_number ?? '—' }}</span>
          </div>
          <span>{{ activeView === 'pitcher' ? 'Mound → plate' : 'Plate → mound' }}</span>
        </div>
      </div>
    </div>
    <p v-else class="empty-state">This pitch does not have enough release, velocity and acceleration data for replay.</p>

    <footer class="replay-readout" aria-live="polite">
      <span><b>{{ pitchName }}</b> · {{ displayNumber(selectedRow?.release_speed, 1) }} mph</span>
      <span>Flight {{ displayNumber(selectedRow?.flight_time_seconds, 3) }} s</span>
      <span>Plate closure X {{ displayNumber(selectedRow?.closure_error_x_in, 2) }}″ · Z {{ displayNumber(selectedRow?.closure_error_z_in, 2) }}″</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { getPitchColor } from '~/utils/pitchColors'
import leftSideBatterAsset from '~/assets/images/pitch-replay/LHH_pitcher_and_RHH_catcher.png'
import rightSideBatterAsset from '~/assets/images/pitch-replay/RHH_pitcher_and_LHH_catcher.png'

type ReplayRow = Record<string, unknown>
type TrajectoryPoint = { progress: number; time_seconds: number; x_ft: number; y_ft: number; z_ft: number }
type CameraView = 'catcher' | 'pitcher'
type ComparisonScope = 'pa' | 'game'
type Point3D = { x: number; y: number; z: number }
type Point2D = { x: number; y: number }

const CAMERA_PRESETS: Record<CameraView, { yaw: number; pitch: number; distance: number }> = {
  pitcher: { yaw: 0, pitch: -3 * Math.PI / 180, distance: 42 },
  catcher: { yaw: 0, pitch: -4 * Math.PI / 180, distance: 42 },
}

const props = defineProps<{ rows: ReplayRow[] }>()
const emit = defineEmits<{ 'select-pitch': [pitch: ReplayRow] }>()

const selectedKey = ref('')
const playMode = ref<'pitch' | 'pa' | 'game'>('pitch')
const playbackRate = ref(0.25)
const progress = ref(1)
const isPlaying = ref(false)
const reducedMotion = ref(false)
const activeView = ref<CameraView>('pitcher')
const comparisonScope = ref<ComparisonScope>('pa')
const cameraYaw = ref(CAMERA_PRESETS.pitcher.yaw)
const cameraPitch = ref(CAMERA_PRESETS.pitcher.pitch)
const cameraDistance = ref(CAMERA_PRESETS.pitcher.distance)
const dragging = ref(false)
let dragPointerId: number | null = null
let lastPointerX = 0
let lastPointerY = 0
let animationFrame: number | null = null
let pitchGapTimer: ReturnType<typeof setTimeout> | null = null
let pendingNextKey: string | null = null
let animationStartedAt = 0
let animationStartProgress = 0
const INTER_PITCH_GAP_MS = 700

const sortedRows = computed(() => [...props.rows].sort((left, right) => {
  const paDifference = Number(left.at_bat_number || 0) - Number(right.at_bat_number || 0)
  return paDifference || Number(left.pitch_number || 0) - Number(right.pitch_number || 0)
}))
const selectedRow = computed(() => sortedRows.value.find(row => rowKey(row) === selectedKey.value) || sortedRows.value[0] || null)
const pathPoints = computed<TrajectoryPoint[]>(() => trajectoryPoints(selectedRow.value))
const currentPoint = computed<TrajectoryPoint | null>(() => interpolatePoint(pathPoints.value, progress.value))
const playedPoints = computed(() => currentPoint.value ? [...pathPoints.value.filter(point => point.progress < progress.value), currentPoint.value] : [])
const pitchName = computed(() => String(selectedRow.value?.pitch_name || 'Pitch'))
const pitchColor = computed(() => getPitchColor(pitchName.value))
const trajectoryStatus = computed(() => String(selectedRow.value?.trajectory_status || 'unavailable'))
const trajectoryReason = computed(() => String(selectedRow.value?.trajectory_reason || ''))
const statusLabel = computed(() => ({ supported: 'Supported', limited_trajectory: 'Limited', unavailable: 'Unavailable' }[trajectoryStatus.value] || 'Unavailable'))
const zoneTop = computed(() => finiteOr(selectedRow.value?.sz_top, 3.5))
const zoneBottom = computed(() => finiteOr(selectedRow.value?.sz_bot, 1.5))
const batterStand = computed(() => {
  const value = String(selectedRow.value?.stand || '').toUpperCase()
  return value === 'L' || value === 'R' ? value : ''
})
const cameraElevationLabel = computed(() => {
  const degrees = Math.round(cameraPitch.value * 180 / Math.PI)
  return `${degrees > 0 ? '+' : ''}${degrees}°`
})
const ballTooltip = computed(() => `${pitchName.value} · ${(progress.value * 100).toFixed(0)}% · ${displayNumber(currentPoint.value?.time_seconds, 3)} s`)
const contextRows = computed(() => sortedRows.value.filter((row) => {
  if (rowKey(row) === selectedKey.value || !trajectoryPoints(row).length) return false
  return comparisonScope.value === 'game' || Number(row.at_bat_number) === Number(selectedRow.value?.at_bat_number)
}))
const contextPaths = computed(() => contextRows.value.flatMap((row) => {
  const points = trajectoryPoints(row)
  const release = projectPhysical(points[0])
  const projected = projectPolyline(points)
  if (!release || !projected) return []
  return [{
    key: rowKey(row),
    points: projected,
    release,
    color: getPitchColor(String(row.pitch_name || row.pitch_type || 'Unknown')),
    label: pitchOptionLabel(row),
  }]
}))
const selectedProjectedPath = computed(() => projectPolyline(pathPoints.value))
const playedProjectedPath = computed(() => projectPolyline(playedPoints.value))
const releaseScreenPoint = computed(() => pathPoints.value.length ? projectPhysical(pathPoints.value[0]) : null)
const currentScreenPoint = computed(() => currentPoint.value ? projectPhysical(currentPoint.value) : null)
const groundPolygon = computed(() => visualPolygon([
  { x: -25, y: -6, z: 0 }, { x: 25, y: -6, z: 0 }, { x: 25, y: 68, z: 0 }, { x: -25, y: 68, z: 0 },
]))
const dirtLanePolygon = computed(() => visualPolygon([
  { x: -0.66, y: -4, z: 0.02 }, { x: 0.66, y: -4, z: 0.02 }, { x: 0.82, y: 67, z: 0.02 }, { x: -0.82, y: 67, z: 0.02 },
]))
const fieldLines = computed(() => [
  visualPolyline([{ x: 0, y: -4, z: 0.04 }, { x: 0, y: 68, z: 0.04 }]),
  visualPolyline([{ x: -19, y: -4, z: 0.04 }, { x: -7, y: 68, z: 0.04 }]),
  visualPolyline([{ x: 19, y: -4, z: 0.04 }, { x: 7, y: 68, z: 0.04 }]),
].filter(Boolean))
const moundPolygon = computed(() => physicalPolygon(Array.from({ length: 30 }, (_, index) => {
  const angle = (index / 29) * Math.PI * 2
  return { x: Math.cos(angle) * 9, y: 60.5 + Math.sin(angle) * 9, z: 0.05 }
})))
const rubberLine = computed<[Point2D, Point2D] | null>(() => {
  const left = projectPhysical({ x: -1, y: 60.5, z: 0.18 })
  const right = projectPhysical({ x: 1, y: 60.5, z: 0.18 })
  return left && right ? [left, right] : null
})
const homePlatePolygon = computed(() => physicalPolygon([
  { x: -17 / 24, y: 0, z: 0.06 }, { x: 17 / 24, y: 0, z: 0.06 }, { x: 17 / 24, y: 17 / 24, z: 0.06 },
  { x: 0, y: 17 / 12, z: 0.06 }, { x: -17 / 24, y: 17 / 24, z: 0.06 },
]))
const batterFigure = computed(() => {
  if (!batterStand.value) return null
  const physicalSide = batterStand.value === 'R' ? -1 : 1
  const feet = projectPhysical({ x: physicalSide * 2.15, y: 0.72, z: 0.06 })
  const crown = projectPhysical({ x: physicalSide * 2.15, y: 0.72, z: 6.15 })
  if (!feet || !crown) return null
  const viewScale = activeView.value === 'catcher' ? 0.95 : 1
  const scale = clamp(Math.abs(feet.y - crown.y) / 478 * viewScale, 0.04, 2)
  const useLeftSideAsset = (activeView.value === 'pitcher' && batterStand.value === 'L')
    || (activeView.value === 'catcher' && batterStand.value === 'R')
  return {
    asset: useLeftSideAsset ? leftSideBatterAsset : rightSideBatterAsset,
    transform: `translate(${feet.x.toFixed(2)} ${feet.y.toFixed(2)}) scale(${scale.toFixed(4)}) translate(-89.5 -478)`,
  }
})
const strikeZoneHalfWidth = 17 / 24
const strikeZonePlaneY = 17 / 12
const strikeZonePolygon = computed(() => physicalPolygon([
  { x: -strikeZoneHalfWidth, y: strikeZonePlaneY, z: zoneBottom.value }, { x: strikeZoneHalfWidth, y: strikeZonePlaneY, z: zoneBottom.value },
  { x: strikeZoneHalfWidth, y: strikeZonePlaneY, z: zoneTop.value }, { x: -strikeZoneHalfWidth, y: strikeZonePlaneY, z: zoneTop.value },
]))
const strikeZoneGridLines = computed<Array<[Point2D, Point2D]>>(() => {
  const height = zoneTop.value - zoneBottom.value
  const verticalXs = [-strikeZoneHalfWidth / 3, strikeZoneHalfWidth / 3]
  const horizontalZs = [zoneBottom.value + height / 3, zoneBottom.value + height * 2 / 3]
  return [
    ...verticalXs.map(x => [
      projectPhysical({ x, y: strikeZonePlaneY, z: zoneBottom.value }),
      projectPhysical({ x, y: strikeZonePlaneY, z: zoneTop.value }),
    ]),
    ...horizontalZs.map(z => [
      projectPhysical({ x: -strikeZoneHalfWidth, y: strikeZonePlaneY, z }),
      projectPhysical({ x: strikeZoneHalfWidth, y: strikeZonePlaneY, z }),
    ]),
  ].filter((line): line is [Point2D, Point2D] => Boolean(line[0] && line[1]))
})

function rowKey(row: ReplayRow) { return [row.game_pk, row.pitcher, row.at_bat_number, row.pitch_number, row.pitch_uid].map(value => String(value ?? '')).join('|') }
function pitchOptionLabel(row: ReplayRow) { return `PA ${row.at_bat_number ?? '—'} · P${row.pitch_number ?? '—'} · ${row.pitch_name || row.pitch_type || 'Unknown'} · ${row.trajectory_status === 'unavailable' ? 'Unavailable' : displayNumber(row.release_speed, 1) + ' mph'}` }
function finiteOr(value: unknown, fallback: number) { if (value === null || value === undefined || value === '') return fallback; const number = Number(value); return Number.isFinite(number) ? number : fallback }
function displayNumber(value: unknown, digits: number) { if (value === null || value === undefined || value === '') return '—'; const number = Number(value); return Number.isFinite(number) ? number.toFixed(digits) : '—' }
function clamp(value: number, minimum: number, maximum: number) { return Math.min(maximum, Math.max(minimum, value)) }
function trajectoryPoints(row: ReplayRow | null | undefined): TrajectoryPoint[] {
  const points = row?.trajectory_points
  if (!Array.isArray(points)) return []
  return points.flatMap((point) => {
    if (!point || typeof point !== 'object' || Array.isArray(point)) return []
    const candidate = point as Record<string, unknown>
    const values = [candidate.progress, candidate.time_seconds, candidate.x_ft, candidate.y_ft, candidate.z_ft].map(Number)
    return values.every(Number.isFinite) ? [{ progress: values[0], time_seconds: values[1], x_ft: values[2], y_ft: values[3], z_ft: values[4] }] : []
  })
}
function subtract(left: Point3D, right: Point3D): Point3D { return { x: left.x - right.x, y: left.y - right.y, z: left.z - right.z } }
function dot(left: Point3D, right: Point3D) { return left.x * right.x + left.y * right.y + left.z * right.z }
function cross(left: Point3D, right: Point3D): Point3D { return { x: left.y * right.z - left.z * right.y, y: left.z * right.x - left.x * right.z, z: left.x * right.y - left.y * right.x } }
function normalize(vector: Point3D): Point3D { const length = Math.hypot(vector.x, vector.y, vector.z) || 1; return { x: vector.x / length, y: vector.y / length, z: vector.z / length } }
function toVisual(point: Point3D): Point3D {
  return activeView.value === 'catcher' ? { x: point.x, y: point.y, z: point.z } : { x: -point.x, y: 60 - point.y, z: point.z }
}
function projectVisual(point: Point3D): Point2D | null {
  const target = { x: 0, y: 30, z: 4.8 }
  const radius = cameraDistance.value
  const horizontalRadius = radius * Math.cos(cameraPitch.value)
  const camera = { x: Math.sin(cameraYaw.value) * horizontalRadius, y: target.y - Math.cos(cameraYaw.value) * horizontalRadius, z: target.z + Math.sin(cameraPitch.value) * radius }
  const forward = normalize(subtract(target, camera))
  const right = normalize(cross(forward, { x: 0, y: 0, z: 1 }))
  const cameraUp = normalize(cross(right, forward))
  const relative = subtract(point, camera)
  const depth = dot(relative, forward)
  if (depth <= 1) return null
  const focalLength = 590
  const screenCenterY = activeView.value === 'catcher' ? 294 : 282
  return { x: 480 + dot(relative, right) * focalLength / depth, y: screenCenterY - dot(relative, cameraUp) * focalLength / depth }
}
function projectPhysical(point: Pick<TrajectoryPoint, 'x_ft' | 'y_ft' | 'z_ft'> | Point3D): Point2D | null {
  const physical = 'x_ft' in point ? { x: point.x_ft, y: point.y_ft, z: point.z_ft } : point
  return projectVisual(toVisual(physical))
}
function formatPoints(points: Array<Point2D | null>) { return points.every(Boolean) ? (points as Point2D[]).map(point => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' ') : '' }
function visualPolyline(points: Point3D[]) { return formatPoints(points.map(projectVisual)) }
function visualPolygon(points: Point3D[]) { return visualPolyline(points) }
function physicalPolygon(points: Point3D[]) { return formatPoints(points.map(projectPhysical)) }
function projectPolyline(points: TrajectoryPoint[]) { return formatPoints(points.map(projectPhysical)) }
function interpolatePoint(points: TrajectoryPoint[], value: number) {
  if (!points.length) return null
  if (value <= 0) return points[0]
  if (value >= 1) return points[points.length - 1]
  const scaled = value * (points.length - 1)
  const lower = Math.floor(scaled)
  const upper = Math.min(points.length - 1, lower + 1)
  const ratio = scaled - lower
  const start = points[lower]
  const end = points[upper]
  return { progress: value, time_seconds: start.time_seconds + (end.time_seconds - start.time_seconds) * ratio, x_ft: start.x_ft + (end.x_ft - start.x_ft) * ratio, y_ft: start.y_ft + (end.y_ft - start.y_ft) * ratio, z_ft: start.z_ft + (end.z_ft - start.z_ft) * ratio }
}
function startCameraDrag(event: PointerEvent) {
  if (event.button !== 0) return
  const target = event.currentTarget as SVGSVGElement
  dragging.value = true
  dragPointerId = event.pointerId
  lastPointerX = event.clientX
  lastPointerY = event.clientY
  target.setPointerCapture(event.pointerId)
}
function moveCamera(event: PointerEvent) {
  if (!dragging.value || dragPointerId !== event.pointerId) return
  cameraYaw.value = clamp(cameraYaw.value + (event.clientX - lastPointerX) * 0.006, -0.72, 0.72)
  cameraPitch.value = clamp(cameraPitch.value - (event.clientY - lastPointerY) * 0.004, -0.1, 0.58)
  lastPointerX = event.clientX
  lastPointerY = event.clientY
}
function stopCameraDrag(event: PointerEvent) {
  if (dragPointerId !== null && event.pointerId !== dragPointerId) return
  const target = event.currentTarget as SVGSVGElement
  if (dragPointerId !== null && target.hasPointerCapture?.(dragPointerId)) target.releasePointerCapture(dragPointerId)
  dragging.value = false
  dragPointerId = null
}
function moveCameraWithKeyboard(event: KeyboardEvent) {
  if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home'].includes(event.key)) return
  event.preventDefault()
  if (event.key === 'Home') { resetCamera(); return }
  if (event.key === 'ArrowLeft') cameraYaw.value = clamp(cameraYaw.value - 0.06, -0.72, 0.72)
  if (event.key === 'ArrowRight') cameraYaw.value = clamp(cameraYaw.value + 0.06, -0.72, 0.72)
  if (event.key === 'ArrowUp') cameraPitch.value = clamp(cameraPitch.value + 0.04, -0.1, 0.58)
  if (event.key === 'ArrowDown') cameraPitch.value = clamp(cameraPitch.value - 0.04, -0.1, 0.58)
}
function setView(view: CameraView) {
  activeView.value = view
  resetCamera()
}
function zoomCamera(event: WheelEvent) {
  const direction = Math.sign(event.deltaY)
  if (!direction) return
  const step = clamp(Math.abs(event.deltaY) * 0.025, 1, 4)
  cameraDistance.value = clamp(cameraDistance.value + direction * step, 32, 70)
}
function setLowCamera() { cameraPitch.value = -0.08 }
function resetCamera() {
  const preset = CAMERA_PRESETS[activeView.value]
  cameraYaw.value = preset.yaw
  cameraPitch.value = preset.pitch
  cameraDistance.value = preset.distance
}
function clearPlaybackHandles() {
  if (animationFrame !== null) cancelAnimationFrame(animationFrame)
  if (pitchGapTimer !== null) clearTimeout(pitchGapTimer)
  animationFrame = null
  pitchGapTimer = null
}
function pause() {
  isPlaying.value = false
  clearPlaybackHandles()
}
function play(restart = false) {
  if (!pathPoints.value.length) return
  clearPlaybackHandles()
  if (restart) pendingNextKey = null
  if (!restart && progress.value >= 1 && pendingNextKey) {
    isPlaying.value = true
    schedulePendingPitch()
    return
  }
  if (restart || progress.value >= 1) progress.value = 0
  isPlaying.value = true
  animationStartProgress = progress.value
  animationStartedAt = performance.now()
  animationFrame = requestAnimationFrame(stepAnimation)
}
function stepAnimation(timestamp: number) {
  if (!isPlaying.value) return
  const durationMs = Math.max(80, finiteOr(selectedRow.value?.flight_time_seconds, 0.4) / playbackRate.value * 1000)
  progress.value = Math.min(1, animationStartProgress + (timestamp - animationStartedAt) / durationMs)
  if (progress.value < 1) { animationFrame = requestAnimationFrame(stepAnimation); return }
  animationFrame = null
  const next = nextPlaybackRow()
  if (!next) { isPlaying.value = false; return }
  pendingNextKey = rowKey(next)
  schedulePendingPitch()
}
function nextPlaybackRow() {
  const row = selectedRow.value
  if (!row || playMode.value === 'pitch') return null
  const candidates = sortedRows.value.filter(candidate => trajectoryPoints(candidate).length
    && (playMode.value === 'game' || Number(candidate.at_bat_number) === Number(row.at_bat_number)))
  const index = candidates.findIndex(candidate => rowKey(candidate) === selectedKey.value)
  return index >= 0 ? candidates[index + 1] || null : null
}
function schedulePendingPitch() {
  if (!pendingNextKey) { isPlaying.value = false; return }
  pitchGapTimer = setTimeout(() => {
    pitchGapTimer = null
    if (!isPlaying.value || !pendingNextKey) return
    const nextKey = pendingNextKey
    pendingNextKey = null
    selectedKey.value = nextKey
    nextTick(() => play(true))
  }, INTER_PITCH_GAP_MS)
}
function replay() { play(true) }

watch(sortedRows, (rows) => {
  if (!rows.length) { selectedKey.value = ''; pause(); progress.value = 1; return }
  if (!rows.some(row => rowKey(row) === selectedKey.value)) selectedKey.value = rowKey(rows[0])
}, { immediate: true })
watch(selectedRow, (row) => { pause(); pendingNextKey = null; progress.value = 1; if (row) emit('select-pitch', row) }, { immediate: true })
onMounted(() => { reducedMotion.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches })
onBeforeUnmount(pause)
</script>

<style scoped>
/* Interactive replay stage */
.replay-chart{display:grid;gap:14px;min-width:0;border:1px solid var(--color-border);border-radius:14px;padding:16px;background:var(--color-surface)}
.replay-header{display:flex;align-items:start;justify-content:space-between;gap:14px}.replay-header h3{margin:0}.replay-header p{margin:3px 0 0;color:var(--color-muted-text);font-size:12px}
.status-badge{border:1px solid var(--color-border);border-radius:999px;padding:5px 9px;font-size:10px;font-weight:900;text-transform:uppercase}.status-badge.supported{border-color:#22c55e;color:#22c55e}.status-badge.limited_trajectory{border-color:#f59e0b;color:#f59e0b}.status-badge.unavailable{border-color:#ef4444;color:#ef4444}
.replay-controls{display:grid;grid-template-columns:minmax(180px,1.25fr) minmax(130px,.7fr) minmax(90px,.4fr) auto;align-items:end;gap:9px}.replay-controls label{display:grid;gap:4px;color:var(--color-muted-text);font-size:10px;font-weight:900;text-transform:uppercase}.replay-controls select{min-height:38px;border:1px solid var(--color-border);border-radius:7px;padding:7px 9px;color:var(--color-foreground);background:var(--color-background);font:inherit}.button-row{display:flex;gap:7px}.button-row button{min-height:38px;border:1px solid var(--color-primary);border-radius:8px;padding:7px 12px;color:var(--color-on-primary);background:var(--color-primary);font-weight:850;cursor:pointer}.button-row button.secondary{border-color:var(--color-border);color:var(--color-foreground);background:var(--color-background)}.button-row button:disabled{opacity:.45;cursor:not-allowed}.timeline{grid-column:1/-1}.timeline input{width:100%;accent-color:var(--color-primary)}.timeline span{color:var(--color-muted-text);font-size:10px;font-weight:700;letter-spacing:0;text-transform:none}
.motion-note,.trajectory-note,.empty-state{margin:0;border-left:3px solid var(--color-primary);padding:7px 10px;color:var(--color-muted-text);font-size:12px}.trajectory-note{border-color:#f59e0b}.replay-stage{display:grid;gap:9px;min-width:0}.stage-toolbar{display:flex;align-items:end;flex-wrap:wrap;gap:9px 18px}.toolbar-group{display:grid;gap:5px}.toolbar-group>span{color:var(--color-muted-text);font-size:10px;font-weight:900;text-transform:uppercase}
.segmented-control{display:flex;overflow:hidden;border:1px solid var(--color-border);border-radius:8px;background:var(--color-background)}.segmented-control button,.camera-button{min-height:36px;border:0;padding:7px 13px;color:var(--color-muted-text);background:transparent;font:inherit;font-size:12px;font-weight:850;cursor:pointer}.segmented-control button+button{border-left:1px solid var(--color-border)}.segmented-control button.active{color:var(--color-on-primary);background:var(--color-primary)}.camera-actions{display:flex;gap:7px;margin-left:auto}.camera-button{border:1px solid var(--color-border);border-radius:8px}.camera-button:hover{border-color:var(--color-primary);color:var(--color-foreground)}
.scene-shell{overflow:hidden;border:1px solid var(--color-border);border-radius:12px;background:#070d18;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}.trajectory-scene{display:block;width:100%;height:auto;min-height:360px;max-height:650px;cursor:grab;touch-action:none;user-select:none}.trajectory-scene.dragging{cursor:grabbing}.field{fill:url(#replay-turf)}.dirt-lane{fill:#73543d;opacity:.82}.field-line{fill:none;stroke:rgba(226,232,240,.26);stroke-width:1.2;vector-effect:non-scaling-stroke}.mound{fill:#8a674a;opacity:.92}.rubber{stroke:#f8fafc;stroke-width:5;stroke-linecap:square;vector-effect:non-scaling-stroke}.plate{fill:#f8fafc;stroke:#94a3b8;stroke-width:1.5;vector-effect:non-scaling-stroke}.batter-silhouette{opacity:.82}.strike-zone{fill:rgba(255,255,255,.025);stroke:#f8fafc;stroke-width:2.2;stroke-linejoin:round;filter:drop-shadow(0 0 3px rgba(255,255,255,.28));vector-effect:non-scaling-stroke}.strike-zone-grid{stroke:rgba(248,250,252,.72);stroke-width:1.15;vector-effect:non-scaling-stroke}
.comparison-path{fill:none;stroke-width:2.2;stroke-linecap:round;opacity:.28;vector-effect:non-scaling-stroke}.comparison-release{stroke:rgba(255,255,255,.7);stroke-width:1;opacity:.72;vector-effect:non-scaling-stroke}.selected-path-shadow{fill:none;stroke:#020617;stroke-width:9;stroke-linecap:round;opacity:.75;vector-effect:non-scaling-stroke}.selected-full-path{fill:none;stroke-width:4.5;stroke-linecap:round;opacity:.4;vector-effect:non-scaling-stroke}.selected-played-path{fill:none;stroke-width:6;stroke-linecap:round;vector-effect:non-scaling-stroke}.selected-release-ring{fill:rgba(255,255,255,.12);stroke:#fff;stroke-width:1.5;vector-effect:non-scaling-stroke}.selected-release{stroke:#fff;stroke-width:1.4;vector-effect:non-scaling-stroke}.ball-halo{fill:rgba(255,255,255,.18);filter:url(#ball-glow)}.ball{fill:#fff;stroke:#0f172a;stroke-width:2.2;filter:url(#ball-glow);vector-effect:non-scaling-stroke}
.scene-hud rect{fill:rgba(3,7,18,.76);stroke:rgba(148,163,184,.28)}.scene-hud text{fill:#e2e8f0}.scene-hud .hud-title{fill:#f59e0b;font-size:14px;font-weight:900;letter-spacing:.08em}.scene-hud .hud-copy{fill:#94a3b8;font-size:12px}.scene-orientation line{stroke:rgba(226,232,240,.68);stroke-width:2}.scene-orientation text{fill:#94a3b8;font-size:12px;font-weight:800}.scene-caption{display:flex;align-items:center;justify-content:space-between;gap:10px;border-top:1px solid rgba(148,163,184,.2);padding:10px 13px;color:#94a3b8;font-size:12px}.scene-caption>div{display:flex;align-items:center;flex-wrap:wrap;gap:6px}.scene-caption b{color:#f8fafc}.pitch-swatch{width:9px;height:9px;border:1px solid rgba(255,255,255,.7);border-radius:50%}.replay-readout{display:flex;flex-wrap:wrap;gap:7px 18px;color:var(--color-muted-text);font-size:12px}.replay-readout b{color:var(--color-foreground)}
@media(max-width:980px){.replay-controls{grid-template-columns:repeat(2,minmax(0,1fr))}.timeline{grid-column:1/-1}.trajectory-scene{min-height:300px}}
@media(max-width:600px){.replay-header{flex-direction:column}.replay-controls{grid-template-columns:1fr}.timeline{grid-column:1}.button-row button{flex:1}.stage-toolbar{align-items:stretch}.toolbar-group{flex:1 1 140px}.segmented-control button{flex:1;padding-inline:9px}.camera-actions{width:100%;margin-left:0}.camera-button{flex:1}.trajectory-scene{min-height:260px}.scene-caption{align-items:flex-start;flex-direction:column}}
</style>
