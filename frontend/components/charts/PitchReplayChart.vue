<template>
  <section class="replay-chart" aria-label="Pitch trajectory replay">
    <header v-show="controlsOpen" class="replay-header">
      <div>
        <h3>{{ title }}</h3>
        <p>Statcast constant-acceleration reconstruction · ball path only</p>
      </div>
      <span :class="['status-badge', trajectoryStatus]">{{ statusLabel }}</span>
    </header>
    <nav v-if="selectedRow && !swingMode" class="matchup-names" aria-label="Selected pitch players">
      <NuxtLink :to="{path:'/pitcher-personal',query:{year,pitcher_id:Number(selectedRow.pitcher)}}">{{ displayPitcherName }}</NuxtLink><span>vs</span><NuxtLink :to="{path:'/batter-personal',query:{year,batter_id:selectedBatterId}}">{{ displayBatterName }}</NuxtLink><small>{{ selectedRow.balls ?? '—' }}–{{ selectedRow.strikes ?? '—' }} · {{ String(selectedRow.stand || '?') }}HB / {{ String(selectedRow.p_throws || '?') }}HP</small>
    </nav>
    <details v-if="MOTION_REFERENCES_AVAILABLE && year===2026 && sortedRows.some(row=>Number(row.batter)===672695)" @toggle="swingReviewOpen=($event.target as HTMLDetailsElement).open">
      <summary class="source-review-title">Geraldo Perdomo · 左右打揮棒標點試作</summary>
      <LazyBatterSwingReview v-if="swingReviewOpen" />
    </details>
    <details v-if="MOTION_REFERENCES_AVAILABLE && year===2026 && teamMotionPitcherIds.includes(selectedPitcherId)" @toggle="sourceReviewOpen=($event.target as HTMLDetailsElement).open">
      <summary class="source-review-title">來源標點 / B · MotionBERT-Lite · 響尾蛇先發投手</summary>
      <LazyPitcherMotionReview v-if="sourceReviewOpen" :key="selectedPitcherId" :pitcher-id="selectedPitcherId" :height-m="pitcherBio?.height_m" />
    </details>

    <div v-if="hasPerdomo && use3D" class="swing-mode-controls">
      <label>Scene playback <select v-model="swingMode"><option :value="false">Historical pitch</option><option :value="true">Perdomo · B swing reference</option></select></label>
      <label v-if="swingMode">Reference side <select v-model="swingSide"><option value="L">Left-handed</option><option value="R">Right-handed</option></select></label>
      <span v-if="swingLoading" role="status">Loading B swing…</span><span v-if="swingError" role="alert">{{ swingError }} <button type="button" @click="loadSwing">Retry</button></span>
    </div>
    <p v-if="swingMode && swingClip" class="motion-note">Geraldo Perdomo · {{ swingClip.data.clip.stand }}HB · <a :href="swingClip.data.clip.sourcePage" target="_blank" rel="noopener noreferrer">{{ swingClip.data.clip.date }} source video ↗</a> · {{ swingReference?.sourceTime.toFixed(3) }} s. B body estimate + generic bat grip; occluded arms are estimated. Independent reference, not this selected pitch. {{ swingReference?.points ? '' : 'Tracking gap: actor hidden.' }}</p>

    <div v-show="controlsOpen" class="replay-controls">
      <label>Pitch
        <select v-model="selectedKey" :disabled="swingMode">
          <option v-for="row in sortedRows" :key="rowKey(row)" :value="rowKey(row)">{{ pitchOptionLabel(row) }}</option>
        </select>
      </label>
      <label>Playback
        <select v-model="playMode" :disabled="swingMode">
          <option value="pitch">Single pitch</option>
          <option value="pa">Plate appearance</option>
          <option value="game">This game</option>
        </select>
      </label>
      <div class="comparison-controls">
        <div class="toolbar-group" aria-label="Comparison pitches">
          <span>Compare</span>
          <div class="segmented-control">
            <button type="button" :class="{ active: comparisonScope === 'pa' }" :aria-pressed="comparisonScope === 'pa'" @click="comparisonScope = 'pa'">This PA</button>
            <button type="button" :class="{ active: comparisonScope === 'game' }" :aria-pressed="comparisonScope === 'game'" @click="comparisonScope = 'game'">This game</button>
          </div>
        </div>
        <button type="button" class="camera-button" @click="resetCamera">Reset view</button>
      </div>
      <label class="timeline">Timeline
        <input v-model.number="progress" type="range" min="0" max="1" step="0.001" :disabled="!pathPoints.length" @input="pause">
        <span v-if="motionEnabled">{{ motionClock.phase }} · {{ motionClock.timeSeconds.toFixed(2) }} s relative to release · generic body motion</span>
        <span v-if="clickToContinue">每球結束後按「下一球」繼續，等待期間可查看 Sequence branch。</span>
        <span v-else-if="playMode !== 'pitch'">0.7 s between pitches</span>
      </label>
    </div>

    <p v-if="reducedMotion" class="motion-note">Reduced motion is enabled. The path stays static until you press Play or Replay.</p>
    <p v-if="trajectoryReason" class="trajectory-note">{{ trajectoryReason }}</p>

    <div v-if="pathPoints.length" class="replay-stage">
      <BatterInGameHeatmap
        v-if="year && selectedBatterId"
        v-show="controlsOpen"
        :year="year" :batter-id="heatmapBatterId" :batter-name="swingMode ? 'Geraldo Perdomo' : displayBatterName"
        :pitcher-id="heatmapPitcherId" :pitcher-hand="heatmapPitcherHand"
        :prefetch-batter-id="nextHeatmapBatterId"
        :context-mode="contextHeatmap" :context-key="currentScoutKey" :stand="batterStand"
        :count="countValid ? `${selectedRow?.balls}-${selectedRow?.strikes}` : ''" :zone-bottom="zoneBottom" :zone-top="zoneTop"
        @overlay="batterHeatmap = $event"
      >
      <template #header-actions>
        <label><input v-model="contextHeatmap" type="checkbox"> 僅看目前球數</label>
        <label><input v-model="clickToContinue" type="checkbox"> 點擊續播</label>
      </template>
      <template #toolbar>
      <div class="stage-toolbar">
        <div class="toolbar-group" aria-label="Camera viewpoint">
          <span>View</span>
          <div class="segmented-control">
            <button type="button" :class="{ active: use3D ? spatialView === 'pitcher' : activeView === 'pitcher' }" :aria-pressed="use3D ? spatialView === 'pitcher' : activeView === 'pitcher'" @click="setView('pitcher')">Pitcher</button>
            <button type="button" :class="{ active: use3D ? spatialView === 'catcher' : activeView === 'catcher' }" :aria-pressed="use3D ? spatialView === 'catcher' : activeView === 'catcher'" @click="setView('catcher')">Catcher</button>
            <button v-if="use3D" type="button" :class="{active:spatialView==='side'}" :aria-pressed="spatialView==='side'" @click="spatialView='side'">Side</button>
          </div>
        </div>
        <div class="scout-actions" aria-label="Scouting tools">
          <button type="button" class="camera-button" :aria-pressed="pitchScoutOpen" @click="pitchScoutOpen=!pitchScoutOpen">Pitch scout</button>
          <button type="button" class="camera-button" disabled title="規劃中，尚未啟用">Batter scout</button>
        </div>
        <div class="playback-actions">
          <label>Speed
            <select v-model.number="playbackRate">
              <option :value="0.25">0.25×</option>
              <option :value="0.5">0.5×</option>
              <option :value="1">1×</option>
            </select>
          </label>
          <div class="button-row">
            <button type="button" :disabled="!pathPoints.length || isPlaying || (swingMode && !swingClip)" @click="play(false)">{{ waitingForNext ? '下一球' : 'Play' }}</button>
            <button type="button" class="secondary" :disabled="!isPlaying" @click="pause">Pause</button>
            <button type="button" :disabled="!pathPoints.length || (swingMode && !swingClip)" @click="replay">Replay</button>
          </div>
          <button v-if="!use3D && activeView === 'pitcher'" type="button" class="camera-button" @click="setLowCamera">Low angle</button>
        </div>
      </div>
      </template>
      </BatterInGameHeatmap>

      <section v-if="pitchScoutOpen" class="pitch-scout-panel" aria-label="Prior-date pitch scout reference">
        <header><strong>{{ pitchScoutOpen ? 'Pitch scout · 投球前情境參考' : '逐球情境熱區' }}</strong><span>{{ selectedRow?.balls }}–{{ selectedRow?.strikes }} · {{ selectedRow?.stand }}HB / {{ selectedRow?.p_throws }}HP</span></header>
        <p v-if="!currentScoutRequest">日期、球數或投打手別缺失，沒有可用的情境參考。</p>
        <p v-else-if="scoutLoading" role="status">載入本球情境…{{ scoutPlaybackKey ? ' 資料完成後開始播放。' : '' }}</p>
        <p v-else-if="scoutError" role="alert">情境資料載入失敗。<button type="button" @click="retryScout">Retry</button></p>
        <template v-else-if="scoutData">
          <p>截至 {{ scoutData.before_date }} 前（不含當日）· {{ scoutData.tier }} · {{ scoutData.context_pitches }} 球／{{ scoutData.swing_count }} 次揮棒</p>
          <p v-if="scoutData.status!=='ready'">歷史樣本不足：需先有超過 30 PA，情境至少 30 球。此球不顯示推測標靶。</p>
          <template v-else-if="pitchScoutOpen">
            <div class="scout-rates"><b>揮棒 {{ scoutData.swing_pct?.toFixed(1) }}%</b><b>未出棒 {{ scoutData.take_pct?.toFixed(1) }}%</b></div>
            <p>歷史揮棒球種分布：{{ scoutData.candidates.map(c=>`${c.family} ${c.share_pct.toFixed(1)}%（${c.swings}）`).join(' · ') || '不足' }}</p>
            <p v-if="scoutData.target">揮棒集中區：{{ scoutData.target.zone }} · {{ scoutData.target.swings }} / {{ scoutData.target.located_swings }} 次有位置的揮棒</p>
            <p v-else>位置樣本不足，不畫標靶。</p>
            <small>歷史條件頻率，未經預測驗證；不是打者意圖、最佳配球或當球結果。金色環為歷史揮棒集中區，收縮僅表現球的到來，不改變球路。早／晚與切球上下緣未實作。</small>
          </template>
        </template>
      </section>

      <details class="pitch-zone-detail"><summary>逐球好球帶 · Stuff 式提示資訊</summary><StrikeZoneScatter :key="plateAppearanceKey(selectedRow)" title="In game · pitch locations" :points="[...(selectedRow ? [selectedRow] : []),...contextRows]" :total-pitches="contextRows.length+(selectedRow?1:0)" :heatmap-blend="0" @select-point="activatePitch" /></details>

      <div class="scene-layout">
      <div class="scene-shell">
        <div v-if="hasPerdomo && use3D" class="swing-stage-actions">
          <button type="button" :disabled="swingLoading" @click="playSwingReference">{{ swingLoading ? '載入揮棒…' : '播放 Perdomo 揮棒' }}</button>
          <span>{{ swingMode ? 'B 來源揮棒' : '目前只播放歷史球路' }}</span>
          <span v-if="swingError" role="alert">{{ swingError }}</span>
        </div>
        <details class="scene-view-help"><summary>{{ use3D ? spatialView.toUpperCase() : activeView.toUpperCase() }} VIEW · guide</summary><p>{{ use3D ? 'Drag / arrows: orbit · wheel / + −: move camera · Home: reset' : '2D schematic: drag / arrows to adjust · wheel to zoom · Home to reset' }}</p><p>{{ contextPaths.length }} comparison pitches. 17-inch Statcast zone · 3×3 grid; outer margin is a display guide.</p><p>Recorded release coordinates, arm angle and extension are shown separately. Pitcher motion is disabled. Historical ball path is unchanged.</p></details>
        <p v-if="sceneError" class="motion-note" role="status">{{ sceneError }} <button type="button" class="camera-button" @click="sceneError='';use3D=true;spatialReset++">Retry 3D</button></p>
        <PitchReplayScene3D v-if="use3D" :year="year" :input="spatialInput" :view="spatialView" :reset-token="spatialReset" @pick="pickSpatialPitch" @open-video="emit('open-video',$event)" @failure="spatialFailure" />
        <svg
          v-else
          class="trajectory-scene"
          :class="{ dragging }"
          viewBox="0 0 960 560"
          role="group"
          :aria-label="`${pitchName} trajectory from the ${activeView} view. ${activeView === 'catcher' ? 'Drag to pan the whole scene.' : 'Drag to adjust the camera angle.'}`"
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
              <stop offset="0" stop-color="#071420" />
              <stop offset="1" stop-color="#29475a" />
            </linearGradient>
            <linearGradient id="replay-turf" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#32684f" />
              <stop offset="1" stop-color="#123e32" />
            </linearGradient>
            <filter id="ball-glow" x="-200%" y="-200%" width="500%" height="500%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          <rect width="960" height="560" fill="#071420" />
          <g :transform="catcherSceneTransform">
          <rect width="960" height="560" fill="url(#replay-sky)" />
          <g>
          <g class="stadium-backdrop" aria-hidden="true"><path d="M0 180 Q480 245 960 180L960 275 0 275Z" fill="#0c2634" /><path d="M0 199 Q480 257 960 199M0 219 Q480 274 960 219" fill="none" stroke="#4a6e7b" stroke-width="3" /><path d="M0 239 Q480 285 960 239L960 285 0 285Z" fill="#163b3e" /><g v-for="i in 32" :key="i" opacity=".5"><circle :cx="i*31-10" :cy="207+Math.sin(i/32*Math.PI)*26" r="2" fill="#b9cad3" /></g><g v-for="x in [80,880]" :key="x"><path :d="`M${x} 88V208`" stroke="#638092" stroke-width="3" /><rect :x="x-23" y="74" width="46" height="15" rx="3" fill="#cedcdb" /><path :d="`M${x-25} 91L${x-90} 210H${x+90}L${x+25} 91`" fill="#c7e6df" opacity=".035" /></g></g>
          <polygon class="field" :points="groundPolygon" />
          <polygon v-for="(stripe,i) in grassStripes" :key="i" :points="stripe" :fill="i%2?'#174b39':'#438262'" opacity=".24" />
          <polygon class="dirt-lane" :points="dirtLanePolygon" />
          <polyline v-for="(line, index) in fieldLines" :key="`field-${index}`" class="field-line" :points="line" />
          <polygon class="mound" :points="moundPolygon" />
          <line v-if="rubberLine" class="rubber" :x1="rubberLine[0].x" :y1="rubberLine[0].y" :x2="rubberLine[1].x" :y2="rubberLine[1].y" />
          </g>
          <g>
          <polygon v-for="(box, index) in batterBoxPolygons" :key="`batter-box-${index}`" class="batter-box" :points="box" aria-hidden="true" />
          <polygon class="plate" :points="homePlatePolygon" />

          <polygon class="zone-backplate" :points="strikeZonePolygon" />
          <g v-if="activeView === 'catcher'" class="batter-zone-rates" pointer-events="none" aria-hidden="true">
            <path v-for="band in heatmapPaths" :key="band.id" :d="band.path" :fill="band.color" :fill-opacity="band.opacity" stroke="none" />
          </g>
          <polygon class="zone-margin" :points="zoneMarginPolygon" aria-hidden="true" />
          <polygon class="strike-zone" :points="strikeZonePolygon"><title>Statcast strike zone: 17-inch plate width by batter sz_bot / sz_top</title></polygon>
          <line v-for="(line, index) in strikeZoneGridLines" :key="`zone-grid-${index}`" class="strike-zone-grid" :x1="line[0].x" :y1="line[0].y" :x2="line[1].x" :y2="line[1].y" />
          <circle v-if="scoutScreenTarget" :cx="scoutScreenTarget.x" :cy="scoutScreenTarget.y" :r="20-12*ballProgress" fill="none" stroke="#ffd34d" stroke-width="3" pointer-events="none"><title>Pitch scout · historical swing concentration</title></circle>

          <g class="comparison-trajectories">
            <g v-for="path in contextPaths" :key="path.key" class="interactive-pitch" role="button" tabindex="0" :aria-label="path.label" @pointerdown.stop @click.stop="activatePitch(path.row)" @keydown.enter.stop.prevent="activatePitch(path.row)" @keydown.space.stop.prevent="activatePitch(path.row)">
              <title>{{ path.label }}</title>
              <polyline class="pitch-hit-area" :points="path.points" />
              <polyline class="comparison-path" :style="{ stroke: path.color }" :points="path.points" />
              <circle class="comparison-release" :style="{ fill: path.color }" :cx="path.release.x" :cy="path.release.y" r="3.5" />
            </g>
          </g>

          <polyline class="selected-path-shadow" :points="selectedProjectedPath" />
          <polyline class="selected-full-path" :style="{ stroke: pitchColor }" :points="selectedProjectedPath" />
          <polyline class="selected-played-path" :style="{ stroke: pitchColor }" :points="playedProjectedPath" />
          <g v-if="selectedRow && selectedProjectedPath" class="interactive-pitch" role="button" tabindex="0" :aria-label="pitchInfo(selectedRow)" @pointerdown.stop @click.stop="activatePitch(selectedRow)" @keydown.enter.stop.prevent="activatePitch(selectedRow)" @keydown.space.stop.prevent="activatePitch(selectedRow)">
            <title>{{ pitchInfo(selectedRow) }}</title><polyline class="pitch-hit-area" :points="selectedProjectedPath" />
          </g>
          <circle v-if="releaseScreenPoint" class="selected-release-ring" :cx="releaseScreenPoint.x" :cy="releaseScreenPoint.y" r="8" />
          <circle v-if="releaseScreenPoint" class="selected-release" :style="{ fill: pitchColor }" :cx="releaseScreenPoint.x" :cy="releaseScreenPoint.y" r="4.5" />
          <circle v-if="currentScreenPoint" class="ball-halo" :cx="currentScreenPoint.x" :cy="currentScreenPoint.y" r="7.8" />
          <circle v-if="currentScreenPoint" class="ball" :cx="currentScreenPoint.x" :cy="currentScreenPoint.y" r="3.9"><title>{{ ballTooltip }}</title></circle>
          </g>
          </g>

          <g class="scene-orientation" aria-hidden="true">
            <line x1="846" y1="505" x2="898" y2="505" />
            <line x1="846" y1="505" x2="846" y2="458" />
            <text x="907" y="510">X</text>
            <text x="840" y="449">Z</text>
          </g>
        </svg>

        <div v-if="!swingMode" class="scene-caption">
          <div>
            <span class="pitch-swatch" :style="{ background: pitchColor }" />
            <b>{{ pitchName }}</b>
            <span>PA {{ selectedRow?.at_bat_number ?? '—' }} · Pitch {{ selectedRow?.pitch_number ?? '—' }}</span>
          </div>
          <span>{{ activeView === 'pitcher' ? 'Mound → plate' : 'Plate → mound' }}</span>
        </div>
      </div>
      </div>
    </div>
    <p v-else class="empty-state">This pitch does not have enough release, velocity and acceleration data for replay.</p>

    <p class="motion-note">Hover or focus a path for pitch details. Click a path or press Enter to select it and open its video when available; the Pitch menu also selects individual pitches.</p>
    <footer v-if="!swingMode" class="replay-readout" aria-live="polite">
      <span><b>{{ pitchName }}</b> · {{ displayNumber(selectedRow?.release_speed, 1) }} mph</span>
      <span>Flight {{ displayNumber(selectedRow?.flight_time_seconds, 3) }} s</span>
      <span>Plate closure X {{ displayNumber(selectedRow?.closure_error_x_in, 2) }}″ · Z {{ displayNumber(selectedRow?.closure_error_z_in, 2) }}″</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { getPitchColor } from '~/utils/pitchColors'
import type { PlayerBio } from '~/types/api'
import { teamMotionPitcherIds } from '~/utils/pitchMotionReview'
import StrikeZoneScatter from './StrikeZoneScatter.vue'
import { inGamePitchDetails, replayComparisonRows } from '~/utils/pitcherInGame'
import {scoutRequest,scoutKey} from '~/utils/pitchScout'
import {usePitchScout} from '~/composables/usePitchScout'
import { buildZoneRateContours, type BatterHeatmapOverlay } from '~/utils/batterZoneRates'
import { replayMotionFrame, type Replay3DInput, type ReplayView } from './replay3d/replayContract'
import { prepareBatterSwing, sampleBatterSwing, type BatterSwingData } from '~/utils/perdomoSwing'
const PitchReplayScene3D = defineAsyncComponent(() => import('./PitchReplayScene3D.client.vue'))

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

const props = withDefaults(defineProps<{ rows: ReplayRow[]; allRows?:ReplayRow[]; title?: string; year?: number; controlsOpen?: boolean }>(), { title: 'Pitch Replay', controlsOpen:true })
const emit = defineEmits<{ 'select-pitch': [pitch: ReplayRow]; 'open-video': [pitch: ReplayRow] }>()

const selectedKey = ref('')
const MOTION_REFERENCES_AVAILABLE=false // User paused all actor-motion work.
const swingReviewOpen=ref(false)
const sourceReviewOpen=ref(false)
const swingMode=ref(false),swingSide=ref<'L'|'R'>('L'),swingLoading=ref(false),swingError=ref('')
const swingClip=shallowRef<ReturnType<typeof prepareBatterSwing>|null>(null)
let swingRequest=0
let swingAutoplay=false,initialSwingSelected=false
const route=useRoute()
const apiBase=useRuntimeConfig().public.apiBase
const playMode = ref<'pitch' | 'pa' | 'game'>('pitch')
const playbackRate = ref(0.25)
const progress = ref(1)
const isPlaying = ref(false)
const clickToContinue = ref(false), waitingForNext = ref(false)
const reducedMotion = ref(false)
const activeView = ref<CameraView>('catcher')
const use3D = ref(true), spatialView = ref<ReplayView>('catcher'), spatialReset = ref(0), sceneError = ref('')
const showActors=ref(true),actorPose=ref<'delivery'|'ready'|'idle'>('ready')
const motionEnabled=computed(()=>use3D.value&&actorPose.value==='delivery')
const batterHeatmap = shallowRef<BatterHeatmapOverlay | null>(null)
const contextHeatmap=ref(false),pitchScoutOpen=ref(false),scoutPlaybackKey=ref('')
const comparisonScope = ref<ComparisonScope>('pa')
const cameraYaw = ref(CAMERA_PRESETS.pitcher.yaw)
const cameraPitch = ref(CAMERA_PRESETS.pitcher.pitch)
const cameraDistance = ref(CAMERA_PRESETS.pitcher.distance)
// A flat stadium cannot orbit in 3D. Catcher view moves every rendered layer together.
const catcherViewport = ref({ x: 0, y: 0, zoom: 1 })
const catcherSceneTransform = computed(() => activeView.value === 'catcher'
  ? `translate(${catcherViewport.value.x} ${catcherViewport.value.y}) translate(480 280) scale(${catcherViewport.value.zoom}) translate(-480 -280)`
  : undefined)
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
const hasPerdomo=computed(()=>MOTION_REFERENCES_AVAILABLE&&props.year===2026&&sortedRows.value.some(row=>Number(row.batter)===672695))
const swingReference=computed(()=>swingMode.value&&swingClip.value?sampleBatterSwing(swingClip.value,progress.value):undefined)
async function loadSwing(){
  if(!MOTION_REFERENCES_AVAILABLE)return
  const token=++swingRequest;pause();pendingNextKey=null;swingClip.value=null;swingError.value='';swingLoading.value=true
  if(selectedBatterId.value!==672695){const row=sortedRows.value.find(r=>Number(r.batter)===672695);if(row)selectedKey.value=rowKey(row)}
  try{const data=await $fetch<BatterSwingData>(`${apiBase}/personal/motion-review/batter/672695/${swingSide.value}/data`,{credentials:'include',timeout:12_000});if(token!==swingRequest)return
    if(data.clip.stand!==swingSide.value)throw new Error('Swing side mismatch')
    swingClip.value=prepareBatterSwing(data);progress.value=0
    if(swingAutoplay&&!document.hidden){swingAutoplay=false;play(true)}
  }catch{if(token===swingRequest){swingAutoplay=false;swingError.value='揮棒資料載入失敗，請重試。'}}finally{if(token===swingRequest)swingLoading.value=false}
}
function playSwingReference(){
  if(!MOTION_REFERENCES_AVAILABLE)return
  swingAutoplay=true
  if(!swingMode.value){swingMode.value=true;return}
  if(swingClip.value){swingAutoplay=false;play(true)}else if(!swingLoading.value)void loadSwing()
}
const pathPoints = computed<TrajectoryPoint[]>(() => trajectoryPoints(selectedRow.value))
const flightSeconds=computed(()=>{const value=Number(selectedRow.value?.flight_time_seconds);return Number.isFinite(value)&&value>0?value:pathPoints.value.at(-1)?.time_seconds||.4})
const motionClock=computed(()=>replayMotionFrame(progress.value,flightSeconds.value,selectedRow.value?.description,selectedRow.value?.arm_angle))
const ballProgress=computed(()=>motionEnabled.value?motionClock.value.ballProgress:progress.value)
const currentPoint = computed<TrajectoryPoint | null>(() => interpolatePoint(pathPoints.value, ballProgress.value))
const playedPoints = computed(() => currentPoint.value ? [...pathPoints.value.filter(point => point.progress < ballProgress.value), currentPoint.value] : [])
const pitchName = computed(() => String(selectedRow.value?.pitch_name || 'Pitch'))
const pitchColor = computed(() => getPitchColor(pitchName.value))
const trajectoryStatus = computed(() => String(selectedRow.value?.trajectory_status || 'unavailable'))
const trajectoryReason = computed(() => String(selectedRow.value?.trajectory_reason || ''))
const statusLabel = computed(() => ({ supported: 'Supported', limited_trajectory: 'Limited', unavailable: 'Unavailable' }[trajectoryStatus.value] || 'Unavailable'))
const zoneTop = computed(() => finiteOr(selectedRow.value?.sz_top, 3.5))
const zoneBottom = computed(() => finiteOr(selectedRow.value?.sz_bot, 1.5))
const selectedBatterId = computed(() => {
  const id = Number(selectedRow.value?.batter)
  return Number.isInteger(id) && id > 0 ? id : 0
})
const selectedPitcherId=computed(()=>Number(selectedRow.value?.pitcher)||0)
const identity=ref<{pitcherId:number;batterId:number;pitcherName:string;batterName:string}|null>(null)
function validPlayerName(value:unknown){const text=String(value||'').trim();return !text||/^(?:(?:batter|pitcher|player)\s*)?\d+$/i.test(text)||/^(unknown|none|nan)/i.test(text)?'':text}
const displayPitcherName=computed(()=>validPlayerName(selectedRow.value?.pitcher_name) || (identity.value?.pitcherId===selectedPitcherId.value?validPlayerName(identity.value.pitcherName):'') || 'Pitcher name unavailable')
const displayBatterName=computed(()=>validPlayerName(selectedRow.value?.batter_name) || (identity.value?.batterId===selectedBatterId.value?validPlayerName(identity.value.batterName):'') || 'Batter name unavailable')
const countValid=computed(()=>selectedRow.value?.balls!=null&&selectedRow.value?.strikes!=null&&Number.isInteger(Number(selectedRow.value.balls))&&Number.isInteger(Number(selectedRow.value.strikes))&&Number(selectedRow.value.balls)>=0&&Number(selectedRow.value.balls)<=3&&Number(selectedRow.value.strikes)>=0&&Number(selectedRow.value.strikes)<=2)
function setIdentity(value:{pitcherName:string;batterName:string}){identity.value={...value,pitcherId:selectedPitcherId.value,batterId:selectedBatterId.value}}
const heatmapBatterId=computed(()=>swingMode.value?672695:selectedBatterId.value)
const nextHeatmapBatterId=computed(()=>{const index=sortedRows.value.findIndex(row=>rowKey(row)===selectedKey.value);const row=sortedRows.value.slice(index+1).find(row=>Number(row.batter)>0&&Number(row.batter)!==heatmapBatterId.value);return row?Number(row.batter):undefined})
const heatmapPitcherId=computed(()=>swingMode.value&&swingClip.value?swingClip.value.data.clip.pitcherId:selectedPitcherId.value)
const heatmapPitcherHand=computed(()=>String(swingMode.value&&swingClip.value?swingClip.value.data.clip.pitchHand:selectedRow.value?.p_throws||'').toUpperCase())
const currentScoutRequest=computed(()=>pitchScoutOpen.value?scoutRequest(props.year,selectedRow.value,props.allRows||props.rows):null)
const nextScoutRequest=computed(()=>{if(!currentScoutRequest.value)return null;const index=sortedRows.value.findIndex(row=>rowKey(row)===selectedKey.value);return scoutRequest(props.year,sortedRows.value[index+1]||null,props.allRows||props.rows)})
const currentScoutKey=computed(()=>currentScoutRequest.value?scoutKey(currentScoutRequest.value):'')
const {data:scoutData,loading:scoutLoading,error:scoutError,retry:retryScout}=usePitchScout(currentScoutRequest,nextScoutRequest)
const scoutTarget=computed(()=>pitchScoutOpen.value&&scoutData.value?.status==='ready'?scoutData.value.target:null)
const scoutScreenTarget=computed(()=>scoutTarget.value?projectPhysical({x:-strikeZoneHalfWidth+scoutTarget.value.u*2*strikeZoneHalfWidth,y:strikeZonePlaneY,z:zoneBottom.value+scoutTarget.value.v*(zoneTop.value-zoneBottom.value)}):null)
const heatmapBands = computed(() => {
  const overlay = batterHeatmap.value
  const context = `${props.year}:${heatmapBatterId.value}:${heatmapPitcherId.value}:${heatmapPitcherHand.value}${contextHeatmap.value?':'+currentScoutKey.value:''}`
  if (!overlay || overlay.context !== context) return []
  return overlay.bands || (overlay.data ? buildZoneRateContours(overlay.data.cells, overlay.metric,overlay.colorMode) : [])
})
const spatialPaths = computed(() => [...(selectedRow.value?[selectedRow.value]:[]),...contextRows.value].map(row=>({key:rowKey(row),label:pitchHoverInfo(row),source:row,color:getPitchColor(String(row.pitch_name||row.pitch_type||'Unknown')),points:trajectoryPoints(row)})))
const pitcherBio = computed(() => selectedRow.value?.pitcher_bio as PlayerBio | null | undefined)
const batterBio = computed(() => selectedRow.value?.batter_bio as PlayerBio | null | undefined)
const gameTeams=computed(()=>{
  const row=selectedRow.value,top=String(row?.inning_topbot||'').toLowerCase()
  return {pitcher:top==='top'?String(row?.home_team||''):top==='bot'?String(row?.away_team||''):'',batter:top==='top'?String(row?.away_team||''):top==='bot'?String(row?.home_team||''):'',pitcherHome:top==='top'?true:top==='bot'?false:null,batterHome:top==='bot'?true:top==='top'?false:null}
})
const spatialInput = computed<Replay3DInput>(() => ({selectedKey:selectedKey.value,points:pathPoints.value,progress:ballProgress.value,color:pitchColor.value,
  paths:spatialPaths.value,
  zoneTop:zoneTop.value,zoneBottom:zoneBottom.value,stand:swingMode.value?swingSide.value:batterStand.value,heatmap:heatmapBands.value,
  scoutTarget:scoutTarget.value||undefined,
  batterHeightM:batterBio.value?.height_m ?? null,
  armAngleDeg:motionClock.value.armAngleDeg,
  releaseExtensionFt:selectedRow.value?.release_extension==null?null:finiteOr(selectedRow.value.release_extension,NaN),
  pitcherActor:{heightM:pitcherBio.value?.height_m,hand:String(selectedRow.value?.p_throws||''),team:gameTeams.value.pitcher,home:gameTeams.value.pitcherHome},
  batterActor:{team:gameTeams.value.batter,home:gameTeams.value.batterHome},actorPose:'ready',showActors:showActors.value,
  motion:undefined,
  batterSwingReference:undefined,
}))
function spatialFailure(message:string){sceneError.value=message;use3D.value=false;spatialView.value=activeView.value}
function pickSpatialPitch(key:string){const row=sortedRows.value.find(row=>rowKey(row)===key);if(row)activatePitch(row)}
const heatmapPolygons = computed(() => {
  return heatmapBands.value.map(cell => {
    const [x0, z0, x1, z1] = cell.bounds
    const point = (x: number, z: number) => ({ x: -strikeZoneHalfWidth + x * strikeZoneHalfWidth * 2, y: strikeZonePlaneY, z: zoneBottom.value + z * (zoneTop.value - zoneBottom.value) })
    return { ...cell, points: physicalPolygon([point(x0, z0), point(x1, z0), point(x1, z1), point(x0, z1)]) }
  })
})
// One compound path per color/opacity avoids seams between translucent row tiles.
const heatmapPaths = computed(() => {
  const groups = new Map<string, { id: string; path: string; color: string; opacity: number }>()
  for (const cell of heatmapPolygons.value) {
    if (!cell.points) continue
    const id = `${cell.color}:${cell.opacity}`
    const group = groups.get(id) || { id, path: '', color: cell.color, opacity: cell.opacity }
    group.path += `M${cell.points.trim().split(/\s+/).join('L')}Z`
    groups.set(id, group)
  }
  return [...groups.values()]
})
const batterStand = computed(() => {
  const value = String(selectedRow.value?.stand || '').toUpperCase()
  return value === 'L' || value === 'R' ? value : ''
})
const cameraElevationLabel = computed(() => {
  const degrees = Math.round(cameraPitch.value * 180 / Math.PI)
  return `${degrees > 0 ? '+' : ''}${degrees}°`
})
const ballTooltip = computed(() => `${pitchName.value} · ${(ballProgress.value * 100).toFixed(0)}% · ${displayNumber(currentPoint.value?.time_seconds, 3)} s`)
const contextRows = computed(() => replayComparisonRows(sortedRows.value,selectedRow.value,comparisonScope.value).filter(row=>rowKey(row)!==selectedKey.value&&trajectoryPoints(row).length))
const contextPaths = computed(() => contextRows.value.flatMap((row) => {
  const points = trajectoryPoints(row)
  const release = projectPhysical(points[0])
  const projected = projectPolyline(points)
  if (!release || !projected) return []
  return [{
    key: rowKey(row),
    row,
    points: projected,
    release,
    color: getPitchColor(String(row.pitch_name || row.pitch_type || 'Unknown')),
    label: pitchInfo(row),
  }]
}))
const selectedProjectedPath = computed(() => projectPolyline(pathPoints.value))
const playedProjectedPath = computed(() => projectPolyline(playedPoints.value))
const releaseScreenPoint = computed(() => pathPoints.value.length ? projectPhysical(pathPoints.value[0]) : null)
const currentScreenPoint = computed(() => currentPoint.value ? projectPhysical(currentPoint.value) : null)
const groundPolygon = computed(() => visualPolygon([
  { x: -25, y: -6, z: 0 }, { x: 25, y: -6, z: 0 }, { x: 25, y: 68, z: 0 }, { x: -25, y: 68, z: 0 },
]))
const dirtLanePolygon = computed(() => physicalPolygon([
  ...Array.from({length:49},(_,i)=>({x:Math.cos(i/48*Math.PI*2)*13,y:Math.sin(i/48*Math.PI*2)*13,z:.02}))
]))
const grassStripes=computed(()=>Array.from({length:12},(_,i)=>visualPolygon([{x:-25,y:-6+i*6,z:.01},{x:25,y:-6+i*6,z:.01},{x:25,y:i*6,z:.01},{x:-25,y:i*6,z:.01}])))
const fieldLines = computed(() => [-1,1].map(side=>formatPoints([{x:0,y:0,z:.04},{x:55*side,y:55,z:.04}].map(projectPhysical))).filter(Boolean))
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
// Presentation-only chalk guides on the same ground plane as the plate.
// Keep both boxes visible; selected stand controls the independently authored batter.
const batterBoxPolygons = computed(() => activeView.value === 'catcher'
  ? [-1, 1].map(side => physicalPolygon([
    { x: side * 1.2, y: -3, z: 0.06 }, { x: side * 5.2, y: -3, z: 0.06 },
    { x: side * 5.2, y: 3, z: 0.06 }, { x: side * 1.2, y: 3, z: 0.06 },
  ]))
  : [])
const strikeZoneHalfWidth = 17 / 24
const strikeZonePlaneY = 17 / 12
const strikeZonePolygon = computed(() => physicalPolygon([
  { x: -strikeZoneHalfWidth, y: strikeZonePlaneY, z: zoneBottom.value }, { x: strikeZoneHalfWidth, y: strikeZonePlaneY, z: zoneBottom.value },
  { x: strikeZoneHalfWidth, y: strikeZonePlaneY, z: zoneTop.value }, { x: -strikeZoneHalfWidth, y: strikeZonePlaneY, z: zoneTop.value },
]))
const zoneMarginPolygon=computed(()=>physicalPolygon([{x:-strikeZoneHalfWidth-.18,y:strikeZonePlaneY,z:zoneBottom.value-.18},{x:strikeZoneHalfWidth+.18,y:strikeZonePlaneY,z:zoneBottom.value-.18},{x:strikeZoneHalfWidth+.18,y:strikeZonePlaneY,z:zoneTop.value+.18},{x:-strikeZoneHalfWidth-.18,y:strikeZonePlaneY,z:zoneTop.value+.18}]))
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
function plateAppearanceKey(row:ReplayRow|null|undefined){return row?[row.game_pk,row.pitcher,row.at_bat_number].map(value=>String(value??'')).join('|'):''}
function pitchInfo(row: ReplayRow) { return inGamePitchDetails(row).map(field => `${field.label}: ${field.value}`).join('\n') }
function pitchHoverInfo(row:ReplayRow){const keys=['game_date','pitch_name','release_speed','balls','strikes','description','pitch_stuff_plus','location_plus_pitch','stamina_plus_trait','stamina_expected_retention_delta','stamina_expected_stuff_plus'];return inGamePitchDetails(row).filter(field=>keys.includes(field.key)).map(field=>`${field.label}: ${field.value}`).join('\n')+`\nVideo: ${row.video_url||row.play_id?'Y':'N'}\nObserved ≠ fatigue cause`}
function activatePitch(row: ReplayRow) { selectedKey.value = rowKey(row); emit('select-pitch', row); emit('open-video', row) }
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
  if (activeView.value === 'catcher') {
    const bounds = (event.currentTarget as SVGSVGElement).getBoundingClientRect()
    const unitsPerPixel = 960 / Math.max(bounds.width, 1)
    panCatcher((event.clientX - lastPointerX) * unitsPerPixel, (event.clientY - lastPointerY) * unitsPerPixel)
  } else {
    cameraYaw.value = clamp(cameraYaw.value + (event.clientX - lastPointerX) * 0.006, -0.72, 0.72)
    cameraPitch.value = clamp(cameraPitch.value - (event.clientY - lastPointerY) * 0.004, -0.1, 0.58)
  }
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
  if (activeView.value === 'catcher') {
    panCatcher(event.key === 'ArrowLeft' ? -20 : event.key === 'ArrowRight' ? 20 : 0,
      event.key === 'ArrowUp' ? -20 : event.key === 'ArrowDown' ? 20 : 0)
    return
  }
  if (event.key === 'ArrowLeft') cameraYaw.value = clamp(cameraYaw.value - 0.06, -0.72, 0.72)
  if (event.key === 'ArrowRight') cameraYaw.value = clamp(cameraYaw.value + 0.06, -0.72, 0.72)
  if (event.key === 'ArrowUp') cameraPitch.value = clamp(cameraPitch.value + 0.04, -0.1, 0.58)
  if (event.key === 'ArrowDown') cameraPitch.value = clamp(cameraPitch.value - 0.04, -0.1, 0.58)
}
function setView(view: CameraView) {
  activeView.value = view
  spatialView.value = view
  resetCamera()
}
function zoomCamera(event: WheelEvent) {
  const direction = Math.sign(event.deltaY)
  if (!direction) return
  if (activeView.value === 'catcher') {
    const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 560 : 1)
    const zoom = clamp(catcherViewport.value.zoom * Math.exp(-clamp(delta, -160, 160) * 0.0015), 0.75, 2.5)
    const ratio = zoom / catcherViewport.value.zoom
    catcherViewport.value = { x: catcherViewport.value.x * ratio, y: catcherViewport.value.y * ratio, zoom }
    return
  }
  const step = clamp(Math.abs(event.deltaY) * 0.025, 1, 4)
  cameraDistance.value = clamp(cameraDistance.value + direction * step, 32, 70)
}
function panCatcher(x: number, y: number) {
  catcherViewport.value.x = clamp(catcherViewport.value.x + x, -480, 480)
  catcherViewport.value.y = clamp(catcherViewport.value.y + y, -280, 280)
}
function setLowCamera() { if (activeView.value === 'pitcher') cameraPitch.value = -0.08 }
function resetCamera() {
  spatialReset.value++
  catcherViewport.value = { x: 0, y: 0, zoom: 1 }
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
  scoutPlaybackKey.value=''
  isPlaying.value = false
  clearPlaybackHandles()
}
function play(restart = false) {
  if (!pathPoints.value.length || (swingMode.value && !swingClip.value)) return
  clearPlaybackHandles()
  waitingForNext.value = false
  if (restart) pendingNextKey = null
  if (!restart && progress.value >= 1 && pendingNextKey) {
    isPlaying.value = true
    schedulePendingPitch()
    return
  }
  if(scoutLoading.value&&currentScoutRequest.value){progress.value=0;isPlaying.value=false;scoutPlaybackKey.value=selectedKey.value;return}
  scoutPlaybackKey.value=''
  if (restart || progress.value >= 1) progress.value = 0
  isPlaying.value = true
  animationStartProgress = progress.value
  animationStartedAt = performance.now()
  animationFrame = requestAnimationFrame(stepAnimation)
}
function stepAnimation(timestamp: number) {
  if (!isPlaying.value) return
  const duration=swingMode.value&&swingClip.value?swingClip.value.data.processingWindow[1]-swingClip.value.data.processingWindow[0]:motionEnabled.value?motionClock.value.durationSeconds:flightSeconds.value
  const durationMs = Math.max(80, duration / playbackRate.value * 1000)
  progress.value = Math.min(1, animationStartProgress + (timestamp - animationStartedAt) / durationMs)
  if (progress.value < 1) { animationFrame = requestAnimationFrame(stepAnimation); return }
  animationFrame = null
  if(swingMode.value){isPlaying.value=false;return}
  const next = nextPlaybackRow()
  if (!next) { isPlaying.value = false; return }
  pendingNextKey = rowKey(next)
  if (clickToContinue.value) { isPlaying.value = false; waitingForNext.value = true; return }
  schedulePendingPitch()
}
function nextPlaybackRow() {
  const row = selectedRow.value
  if (!row || (playMode.value === 'pitch' && !clickToContinue.value)) return null
  const candidates = sortedRows.value.filter(candidate => trajectoryPoints(candidate).length
    && (playMode.value !== 'pa' || Number(candidate.at_bat_number) === Number(row.at_bat_number)))
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
watch(scoutLoading,loading=>{if(!loading&&scoutPlaybackKey.value===selectedKey.value&&scoutPlaybackKey.value&&!document.hidden)play(true)})

watch(sortedRows, (rows) => {
  if (!rows.length) { selectedKey.value = ''; pause(); progress.value = 1; return }
  if (!rows.some(row => rowKey(row) === selectedKey.value)) selectedKey.value = rowKey(rows[0])
}, { immediate: true })
watch(selectedRow, (row) => { pause(); pendingNextKey = null; waitingForNext.value = false; progress.value = 1; if (row) emit('select-pitch', row)
  if(MOTION_REFERENCES_AVAILABLE&&!initialSwingSelected&&props.year===2026&&Number(row?.batter)===672695){initialSwingSelected=true;swingSide.value=row?.stand==='R'?'R':'L';swingMode.value=true}
}, { immediate: true })
watch(()=>plateAppearanceKey(selectedRow.value),()=>{comparisonScope.value='pa'})
watch([use3D,actorPose],()=>{pause();pendingNextKey=null})
watch([swingMode,swingSide],()=>{if(swingMode.value)void loadSwing();else{++swingRequest;swingAutoplay=false;pause();pendingNextKey=null;swingClip.value=null;swingLoading.value=false;progress.value=1}},{immediate:true})
watch(hasPerdomo,available=>{if(available&&!initialSwingSelected&&route.query.swing_reference==='1'){initialSwingSelected=true;swingSide.value=route.query.swing_side==='R'?'R':'L';swingMode.value=true}},{immediate:true})
watch([hasPerdomo,use3D],()=>{if(!hasPerdomo.value||!use3D.value)swingMode.value=false})
watch(playbackRate,()=>{if(isPlaying.value)play(false)})
watch([playMode,clickToContinue],()=>{pause();pendingNextKey=null;waitingForNext.value=false})
watch([contextHeatmap,pitchScoutOpen],()=>pause())
function visibilityPause(){if(document.hidden){swingAutoplay=false;pause();pendingNextKey=null}}
onMounted(() => { reducedMotion.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches;document.addEventListener('visibilitychange',visibilityPause) })
onBeforeUnmount(()=>{swingRequest++;pause();document.removeEventListener('visibilitychange',visibilityPause)})
</script>

<style scoped>
.pitch-scout-panel{display:grid;gap:8px;padding:12px;border:1px solid #c5a34d;border-radius:9px;background:var(--color-surface);color:var(--color-foreground);font-size:12px}.pitch-scout-panel header,.scout-rates{display:flex;gap:16px;justify-content:space-between;flex-wrap:wrap}.pitch-scout-panel p{margin:0}.pitch-scout-panel small{color:var(--color-muted-text);line-height:1.5}.scout-rates{justify-content:flex-start;color:#ffd34d}.scout-actions [aria-pressed="true"]{border-color:#ffd34d;color:#ffd34d}
.scene-layout{display:grid;grid-template-columns:minmax(0,1fr);gap:12px;align-items:start}.scene-layout>.scene-shell{min-width:0}
.source-review-title{cursor:pointer;padding:8px 0;font-weight:800}
.swing-stage-actions{position:relative;z-index:5;display:flex;align-items:center;flex-wrap:wrap;gap:12px;padding:12px;background:var(--color-surface);color:var(--color-foreground)}.swing-stage-actions button{padding:10px 16px;font:inherit;font-weight:800;color:var(--color-on-primary);background:var(--color-primary);border:0;border-radius:7px;cursor:pointer}.swing-stage-actions~.scene-view-help{top:80px}
.swing-mode-controls{display:flex;flex-wrap:wrap;align-items:end;gap:12px}.swing-mode-controls label{display:grid;gap:5px}.swing-mode-controls select{padding:8px;color:var(--color-foreground);background:var(--color-background);border:1px solid var(--color-border);border-radius:7px}.motion-note a{color:var(--color-foreground)}
.matchup-names{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.matchup-names a{color:var(--color-foreground);font-size:16px;font-weight:850;text-decoration:none;border-bottom:1px solid #4dbe9b}.matchup-names span,.matchup-names small{color:var(--color-muted-text)}.scene-shell{position:relative}.scene-view-help{position:absolute;top:14px;left:16px;z-index:4;max-width:310px;padding:10px 14px;border:1px solid #55727c;border-radius:8px;background:#000;color:#cfdee7;font-size:12px;box-shadow:0 7px 20px #0003}.scene-view-help summary{cursor:pointer;color:#f8c473;font-weight:850;letter-spacing:.06em}.scene-view-help p{margin:9px 0;line-height:1.5}.zone-backplate{fill:#061725;fill-opacity:.78;stroke:#061725;stroke-width:7;vector-effect:non-scaling-stroke}.zone-margin{fill:none;stroke:#7ce9d0;stroke-width:1.5;stroke-dasharray:5 4;vector-effect:non-scaling-stroke;opacity:.9}
/* Interactive replay stage */
.interactive-pitch { cursor:pointer; }
.selected-release-ring,.selected-release,.ball,.ball-halo { pointer-events:none; }
.pitch-hit-area { fill:none; stroke:transparent; stroke-width:12; pointer-events:stroke; vector-effect:non-scaling-stroke; }
.batter-box{fill:none;stroke:#fff9e6;stroke-width:2.6;stroke-linejoin:round;opacity:.94;pointer-events:none;vector-effect:non-scaling-stroke}
.interactive-pitch:focus-visible .pitch-hit-area,.interactive-pitch:hover .pitch-hit-area { stroke:rgba(255,255,255,.18); }
.replay-chart{display:grid;gap:14px;min-width:0;border:1px solid var(--color-border);border-radius:14px;padding:16px;background:var(--color-surface)}
.replay-header{display:flex;align-items:start;justify-content:space-between;gap:14px}.replay-header h3{margin:0}.replay-header p{margin:3px 0 0;color:var(--color-muted-text);font-size:12px}
.status-badge{border:1px solid var(--color-border);border-radius:999px;padding:5px 9px;font-size:10px;font-weight:900;text-transform:uppercase}.status-badge.supported{border-color:#22c55e;color:#22c55e}.status-badge.limited_trajectory{border-color:#f59e0b;color:#f59e0b}.status-badge.unavailable{border-color:#ef4444;color:#ef4444}
.replay-controls{display:grid;grid-template-columns:minmax(180px,1.25fr) minmax(130px,.7fr) minmax(90px,.4fr) auto;align-items:end;gap:9px}.replay-controls label{display:grid;gap:4px;color:var(--color-muted-text);font-size:10px;font-weight:900;text-transform:uppercase}.replay-controls select{min-height:38px;border:1px solid var(--color-border);border-radius:7px;padding:7px 9px;color:var(--color-foreground);background:var(--color-background);font:inherit}.button-row{display:flex;gap:7px}.button-row button{min-height:38px;border:1px solid var(--color-primary);border-radius:8px;padding:7px 12px;color:var(--color-on-primary);background:var(--color-primary);font-weight:850;cursor:pointer}.button-row button.secondary{border-color:var(--color-border);color:var(--color-foreground);background:var(--color-background)}.button-row button:disabled{opacity:.45;cursor:not-allowed}.timeline{grid-column:1/-1}.timeline input{width:100%;accent-color:var(--color-primary)}.timeline span{color:var(--color-muted-text);font-size:10px;font-weight:700;letter-spacing:0;text-transform:none}
.motion-note,.trajectory-note,.empty-state{margin:0;border-left:3px solid var(--color-primary);padding:7px 10px;color:var(--color-muted-text);font-size:12px}.trajectory-note{border-color:#f59e0b}.replay-stage{display:grid;gap:9px;min-width:0}.stage-toolbar{display:flex;flex:2 1 750px;align-items:end;flex-wrap:wrap;gap:9px 18px}.toolbar-group:first-child{flex:1 1 auto}.toolbar-group{display:grid;gap:5px}.toolbar-group>span{color:var(--color-muted-text);font-size:10px;font-weight:900;text-transform:uppercase}
.segmented-control{display:flex;width:max-content;max-width:100%;overflow:hidden;border:1px solid var(--color-border);border-radius:8px;background:var(--color-background)}.segmented-control button,.camera-button{min-height:36px;border:0;padding:7px 13px;color:var(--color-muted-text);background:transparent;font:inherit;font-size:12px;font-weight:850;cursor:pointer}.segmented-control button+button{border-left:1px solid var(--color-border)}.segmented-control button.active{color:var(--color-on-primary);background:var(--color-primary)}.camera-actions{display:flex;gap:7px;margin-left:auto}.camera-button{border:1px solid var(--color-border);border-radius:8px}.camera-button:hover{border-color:var(--color-primary);color:var(--color-foreground)}
.scene-shell{overflow:hidden;border:1px solid var(--color-border);border-radius:12px;background:#000;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}.trajectory-scene{display:block;width:100%;height:auto;min-height:360px;max-height:650px;cursor:grab;touch-action:none;user-select:none}.trajectory-scene.dragging{cursor:grabbing}.field{fill:url(#replay-turf)}.dirt-lane{fill:#73543d;opacity:.82}.field-line{fill:none;stroke:rgba(226,232,240,.26);stroke-width:1.2;vector-effect:non-scaling-stroke}.mound{fill:#8a674a;opacity:.92}.rubber{stroke:#f8fafc;stroke-width:5;stroke-linecap:square;vector-effect:non-scaling-stroke}.plate{fill:#f8fafc;stroke:#94a3b8;stroke-width:1.5;vector-effect:non-scaling-stroke}.batter-silhouette{opacity:.82}.strike-zone{fill:rgba(255,255,255,.025);stroke:#f8fafc;stroke-width:2.2;stroke-linejoin:round;filter:drop-shadow(0 0 3px rgba(255,255,255,.28));vector-effect:non-scaling-stroke}.strike-zone-grid{stroke:rgba(248,250,252,.72);stroke-width:1.15;vector-effect:non-scaling-stroke}
.comparison-path{fill:none;stroke-width:2.2;stroke-linecap:round;opacity:.28;vector-effect:non-scaling-stroke}.comparison-release{stroke:rgba(255,255,255,.7);stroke-width:1;opacity:.72;vector-effect:non-scaling-stroke}.selected-path-shadow{fill:none;stroke:#020617;stroke-width:9;stroke-linecap:round;opacity:.75;vector-effect:non-scaling-stroke}.selected-full-path{fill:none;stroke-width:4.5;stroke-linecap:round;opacity:.4;vector-effect:non-scaling-stroke}.selected-played-path{fill:none;stroke-width:6;stroke-linecap:round;vector-effect:non-scaling-stroke}.selected-release-ring{fill:rgba(255,255,255,.12);stroke:#fff;stroke-width:1.5;vector-effect:non-scaling-stroke}.selected-release{stroke:#fff;stroke-width:1.4;vector-effect:non-scaling-stroke}.ball-halo{fill:rgba(255,255,255,.18);filter:url(#ball-glow)}.ball{fill:#fff;stroke:#0f172a;stroke-width:2.2;filter:url(#ball-glow);vector-effect:non-scaling-stroke}
.scene-hud rect{fill:rgba(3,7,18,.76);stroke:rgba(148,163,184,.28)}.scene-hud text{fill:#e2e8f0}.scene-hud .hud-title{fill:#f59e0b;font-size:14px;font-weight:900;letter-spacing:.08em}.scene-hud .hud-copy{fill:#94a3b8;font-size:12px}.scene-orientation line{stroke:rgba(226,232,240,.68);stroke-width:2}.scene-orientation text{fill:#94a3b8;font-size:12px;font-weight:800}.scene-caption{display:flex;align-items:center;justify-content:space-between;gap:10px;border-top:1px solid rgba(148,163,184,.2);padding:10px 13px;color:#94a3b8;font-size:12px}.scene-caption>div{display:flex;align-items:center;flex-wrap:wrap;gap:6px}.scene-caption b{color:#f8fafc}.pitch-swatch{width:9px;height:9px;border:1px solid rgba(255,255,255,.7);border-radius:50%}.replay-readout{display:flex;flex-wrap:wrap;gap:7px 18px;color:var(--color-muted-text);font-size:12px}.replay-readout b{color:var(--color-foreground)}
@media(max-width:980px){.replay-controls{grid-template-columns:repeat(2,minmax(0,1fr))}.timeline{grid-column:1/-1}.trajectory-scene{min-height:300px}}
@media(max-width:600px){.replay-header{flex-direction:column}.replay-controls{grid-template-columns:1fr}.timeline{grid-column:1}.button-row button{flex:1}.stage-toolbar{align-items:stretch}.toolbar-group{flex:1 1 140px}.segmented-control button{flex:1;padding-inline:9px}.camera-actions{width:100%;margin-left:0}.camera-button{flex:1}.trajectory-scene{min-height:260px}.scene-caption{align-items:flex-start;flex-direction:column}}
.stage-toolbar{flex:1 1 480px}
.stage-toolbar>.toolbar-group:first-child{flex:0 0 auto}.scout-actions{display:flex;gap:7px}.scout-actions button:disabled{opacity:.55;cursor:not-allowed}
.replay-controls{grid-template-columns:minmax(180px,1.25fr) minmax(130px,.7fr) auto}.comparison-controls,.playback-actions{display:flex;align-items:end;gap:12px}.playback-actions{margin-left:auto;flex-wrap:wrap}.playback-actions label{display:grid;gap:5px;font-size:10px;font-weight:900;text-transform:uppercase;color:var(--color-muted-text)}.playback-actions select{min-height:38px;min-width:90px;padding:7px 9px;color:var(--color-foreground);background:var(--color-background);border:1px solid var(--color-border);border-radius:7px}.stage-toolbar{flex:1 0 100%}
@media(max-width:980px){.replay-controls{grid-template-columns:repeat(2,minmax(0,1fr))}.comparison-controls{grid-column:1/-1}}
@media(max-width:600px){.replay-controls{grid-template-columns:1fr}.playback-actions{margin-left:0;width:100%}}
</style>
