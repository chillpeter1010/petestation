<template>
  <section class="ballpark-runtime" aria-labelledby="ballpark-runtime-title" :data-room="room" :data-player-x="worldState.x" :data-player-y="worldState.y" :data-status="status">
    <div class="ballpark-runtime__viewport">
      <div ref="runtimeHost" class="ballpark-runtime__canvas" :aria-hidden="status === 'ready'" />

      <div v-if="status === 'loading'" class="ballpark-runtime__state" role="status">
        <span class="ballpark-runtime__spinner" aria-hidden="true" />
        <strong>Loading Ballpark walk preview…</strong>
        <small>The static Ballpark map remains available.</small>
      </div>

      <div v-else-if="status === 'error'" class="ballpark-runtime__state" role="alert">
        <strong>Ballpark could not start.</strong>
        <p>{{ errorMessage }}</p>
        <div class="ballpark-runtime__state-actions">
          <button type="button" @click="mountRuntime">Try again</button>
          <NuxtLink to="/ballpark">Open static Ballpark</NuxtLink>
          <NuxtLink :to="fallbackRoute || '/'" @click="emit('classic')">Open Classic UI</NuxtLink>
        </div>
      </div>
    </div>

    <aside class="ballpark-runtime__hud" aria-live="polite">
      <div>
        <span>Runtime</span>
        <strong>{{ statusLabel }}</strong>
      </div>
      <div>
        <span>Nearby</span>
        <strong>{{ worldState.nearby || 'Walk toward a doorway' }}</strong>
      </div>
      <div>
        <span>Input</span>
        <strong>{{ worldState.inputSource }}</strong>
      </div>
      <div>
        <span>Renderer</span>
        <strong>{{ worldState.renderer }}</strong>
      </div>
      <button type="button" :disabled="status !== 'ready'" @click="resetPlayer">Safe reset</button>
      <button ref="interactButton" type="button" :disabled="status !== 'ready' || !worldState.nearby || paused" @click="interact">Interact / Enter / Exit</button>
    </aside>

    <div class="ballpark-runtime__controls" aria-label="Touch movement controls">
      <button
        v-for="control in touchControls"
        :key="control.label"
        type="button"
        :aria-label="control.label"
        :style="{ gridArea: control.area }"
        :disabled="status !== 'ready'"
        @pointerdown.prevent="setTouch(control.x, control.y)"
        @pointerup.prevent="clearTouch"
        @pointercancel="clearTouch"
        @pointerleave="clearTouch"
        @keydown.space.prevent="setTouch(control.x, control.y)"
        @keyup.space.prevent="clearTouch"
      >
        {{ control.glyph }}
      </button>
    </div>

    <p id="ballpark-runtime-title" class="ballpark-runtime__instructions">
      Move with WASD, arrow keys, gamepad or touch. Use E or Enter near objects and guides, or click an object / use the room object menu. Use C near the Clubhouse smoking-area door; R near an exit returns to Clubhouse or Campus. Interact / Enter / Exit also works. Panels pause movement. Safe reset returns to this room’s spawn.
    </p>
    <p v-if="worldState.characterWarning" class="ballpark-runtime__instructions" role="status">{{ worldState.characterWarning }}</p>
    <p v-if="worldState.restoreWarning" class="ballpark-runtime__instructions" role="status">{{ worldState.restoreWarning }}</p>
    <details class="ballpark-runtime__diagnostics">
      <summary>Runtime options / E6 recording</summary>
      <div class="diagnostic-actions"><label><input v-model="reducedMotion" type="checkbox" @change="restartWithPosition"> Reduced motion</label><label><input v-model="preferCanvas" type="checkbox" @change="restartWithPosition"> Use Canvas renderer</label>
        <button type="button" :disabled="status!=='ready'||recording" @click="startRecording">Record 20 seconds</button>
        <button v-if="report" type="button" @click="downloadReport">Download recording JSON</button>
      </div>
      <p v-if="recording" role="status">Recording: walk normally for 20 seconds. Hidden tabs and paused panels are excluded.</p>
      <p v-else-if="report" role="status">Samples {{ report.sample_count }} · walking {{ report.moving_samples }} · p95 {{ report.p95_ms?.toFixed(1) ?? '—' }} ms · {{ report.interpretation }}</p>
      <p v-if="report?.interpretation==='offer_classic_fallback'">Frame time was high in this sample. <NuxtLink :to="fallbackRoute || '/'" @click="emit('classic')">Use Classic UI</NuxtLink> or choose Canvas.</p>
      <p>Browser-local measurements only. This is not a production/device release certificate. Memory is unavailable if the browser does not expose it.</p>
    </details>
  </section>
</template>

<script setup lang="ts">
import type { BallparkPortalTarget, BallparkRoom, BallparkRuntimeHandle, BallparkRuntimeState } from './runtime/createBallparkGame'
import { createRuntimeLoadGate } from './runtime/runtimeGuards'
import type { ObjectIntent } from './runtime/interactionCatalog'
import type { WorldPosition } from './runtime/worldState'
import { createFrameRecorder, lifecycleSnapshot } from './runtime/runtimeTelemetry'

const props = defineProps<{ room: BallparkRoom; arrivalId?: string; savedPosition?: WorldPosition; allowAdmin?: boolean; paused?: boolean; fallbackRoute?: string }>()
const emit = defineEmits<{ portal: [target: BallparkPortalTarget]; object: [intent: ObjectIntent]; state: [state: BallparkRuntimeState]; classic:[] }>()
const interactButton = ref<HTMLButtonElement | null>(null)
defineExpose({ focusInteraction: () => interactButton.value?.focus({preventScroll:true}), snapshot:()=>runtime.value?.snapshot() })
const { user } = useAuth()

type RuntimeStatus = 'loading' | 'ready' | 'error'

const runtimeHost = ref<HTMLElement | null>(null)
const status = ref<RuntimeStatus>('loading')
const errorMessage = ref('The runtime is unavailable on this device. Use the static Ballpark map instead.')
const runtime = shallowRef<BallparkRuntimeHandle | null>(null)
const worldState = ref<BallparkRuntimeState>({
  room:props.room,
  facing:'south',
  status: 'paused',
  x: 800,
  y: 690,
  inputSource: 'idle',
  renderer: 'canvas',
  nearby: null
})
const loadGate = createRuntimeLoadGate()
let loadTimeout: ReturnType<typeof setTimeout> | undefined
const reducedMotion=ref(false),preferCanvas=ref(false),recording=ref(false)
const recorder=createFrameRecorder()
type FrameReport=NonNullable<ReturnType<typeof recorder.finish>>
const report=shallowRef<(FrameReport & Record<string,unknown>)|null>(null)
let recordTimer:ReturnType<typeof setTimeout>|undefined,loadStarted=0,loadMs:number|null=null
let resumePosition:WorldPosition|undefined,media:MediaQueryList|undefined
let recordEnvironment:Record<string,unknown>={}
function memory(){return (performance as Performance & {memory?:{usedJSHeapSize:number}}).memory?.usedJSHeapSize ?? null}
function syncMotion(event:MediaQueryListEvent){reducedMotion.value=event.matches;restartWithPosition()}
onMounted(()=>{media=window.matchMedia('(prefers-reduced-motion: reduce)');reducedMotion.value=media.matches;media.addEventListener('change',syncMotion)})

const statusLabel = computed(() => {
  if (status.value === 'loading') return 'loading'
  if (status.value === 'error') return 'fallback'
  return worldState.value.status
})

const touchControls = [
  { label: 'Move up', glyph: '↑', area: 'up', x: 0, y: -1 },
  { label: 'Move left', glyph: '←', area: 'left', x: -1, y: 0 },
  { label: 'Move right', glyph: '→', area: 'right', x: 1, y: 0 },
  { label: 'Move down', glyph: '↓', area: 'down', x: 0, y: 1 }
] as const

watch(runtimeHost, host => { if (host) void mountRuntime() }, { flush: 'post' })
watch(() => props.paused, value => runtime.value?.setPaused(Boolean(value)))
watch(() => [user.value?.avatar, user.value?.favorite_team_code] as const, ([avatar, team]) => { if (avatar) runtime.value?.setAppearance(avatar, team) })

onBeforeUnmount(() => {
  clearTimeout(recordTimer);recorder.cancel();media?.removeEventListener('change',syncMotion)
  loadGate.cancel()
  clearTimeout(loadTimeout)
  runtime.value?.destroy()
  runtime.value = null
})

async function mountRuntime() {
  const host = runtimeHost.value
  if (!host) return
  const signal = loadGate.start()
  const isCurrent = () => loadGate.isCurrent(signal) && runtimeHost.value === host
  runtime.value?.destroy()
  runtime.value = null
  host.replaceChildren()
  status.value = 'loading'
  loadStarted=performance.now();loadMs=null
  clearTimeout(loadTimeout)
  function fail(message: string) {
    if (!isCurrent()) return
    clearTimeout(recordTimer);recording.value=false;recorder.cancel()
    loadGate.cancel()
    clearTimeout(loadTimeout)
    runtime.value?.destroy()
    runtime.value = null
    errorMessage.value = message
    status.value = 'error'
  }
  loadTimeout = setTimeout(() => fail('The scene did not finish loading. Retry or use the static Ballpark map.'), 15000)

  try {
    const { createBallparkGame } = await import('./runtime/createBallparkGame')
    if (!isCurrent()) return
    const savedPosition=resumePosition || props.savedPosition
    const arrivalId=resumePosition ? undefined : props.arrivalId
    resumePosition=undefined
    const handle = await createBallparkGame({
      parent: host,
      signal,
      room: props.room,
      arrivalId,
      savedPosition,
      allowAdmin: props.allowAdmin,
      reducedMotion: reducedMotion.value || (!media && window.matchMedia('(prefers-reduced-motion: reduce)').matches),
      preferCanvas:preferCanvas.value,
      onFrame(active,moving){if(recording.value)recorder.sample(performance.now(),active,moving)},
      avatar: user.value?.avatar,
      favoriteTeam: user.value?.favorite_team_code,
      onError(error) { fail(error.message) },
      onPortal(target) { if (isCurrent()) emit('portal', target) },
      onObject(intent) { if (isCurrent()) emit('object', intent) },
      onState(nextState) {
        if (!isCurrent()) return
        clearTimeout(loadTimeout)
        if(loadMs===null)loadMs=performance.now()-loadStarted
        worldState.value = nextState
        emit('state', nextState)
        status.value = 'ready'
      }
    })
    if (!isCurrent()) {
      handle.destroy()
      return
    }
    runtime.value = handle
    if (user.value?.avatar) handle.setAppearance(user.value.avatar, user.value.favorite_team_code)
    handle.setPaused(Boolean(props.paused))
  } catch (error) {
    if (!isCurrent()) return
    console.error('Unable to start Ballpark runtime', error)
    fail(error instanceof Error ? error.message : 'Unknown runtime error.')
  }
}

function setTouch(x: number, y: number) {
  runtime.value?.setTouchVector(x, y)
}

function clearTouch() {
  runtime.value?.setTouchVector(0, 0)
}

function resetPlayer() {
  runtime.value?.reset()
}

function interact() {
  runtime.value?.interact()
}
function restartWithPosition(){
  const state=runtime.value?.snapshot()
  if(state){emit('state',state);resumePosition={x:state.x,y:state.y,facing:state.facing,objectId:state.nearbyObject||undefined}}
  clearTimeout(recordTimer);recording.value=false;recorder.cancel();report.value=null
  void mountRuntime()
}
function startRecording(){
  report.value=null;recording.value=true;recorder.start(performance.now())
  recordEnvironment={schema_version:1,started_at:new Date().toISOString(),room:props.room,route:location.pathname+location.search,mode:import.meta.dev?'development':'production',browser:navigator.userAgent,viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},hardware_threads:navigator.hardwareConcurrency,device_memory_gb:(navigator as Navigator & {deviceMemory?:number}).deviceMemory ?? null,reduced_motion:reducedMotion.value,renderer:worldState.value.renderer,heap_before_bytes:memory(),lifecycle_before:lifecycleSnapshot(),load_to_first_state_ms:loadMs,load_metric:'component mount to first runtime state, not navigation/LCP',cache_state:'not measured',device_class:'user must identify real hardware',release_status:'pending_user',limitations:['No forced GC / retained heap or GPU memory measurement','Owned lifecycle counters do not prove absence of all browser listeners/resources','No production LCP/input-latency/bundle certification','User-operated sample; no assistant browser test']}
  recordTimer=setTimeout(()=>{
    const frames=recorder.finish(performance.now());recording.value=false
    if(frames)report.value={...frames,...recordEnvironment,heap_after_bytes:memory(),memory_api:memory()===null?'unavailable':'performance.memory.usedJSHeapSize (not retained heap)',lifecycle_after:lifecycleSnapshot()}
  },20000)
}
function downloadReport(){
  if(!report.value)return
  const url=URL.createObjectURL(new Blob([JSON.stringify(report.value,null,2)],{type:'application/json'}))
  const link=document.createElement('a');link.href=url;link.download=`ballpark-e6-${props.room}-${Date.now()}.json`;link.click();URL.revokeObjectURL(url)
}
</script>

<style scoped>
.ballpark-runtime {
  position: relative;
  min-height: 0;
  overflow: hidden;
  border: 1px solid #3a414c;
  border-radius: 14px;
  background: #070707;
  box-shadow: 0 24px 70px rgb(0 0 0 / 42%);
}
.ballpark-runtime__diagnostics{padding:14px;color:#d7e4df;background:#111c19;border-top:1px solid #46554a;font-size:13px}.ballpark-runtime__diagnostics summary{cursor:pointer;font-weight:800}.diagnostic-actions{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin-top:12px}.diagnostic-actions button{min-height:42px;padding:8px 12px;border:1px solid #d49d43;border-radius:6px;background:#1b2824;color:#ffe3af;cursor:pointer}.ballpark-runtime__diagnostics a{color:#ffc668}

.ballpark-runtime__viewport {
  position: relative;
  aspect-ratio: 16 / 9;
  min-height: 320px;
  overflow: hidden;
}

.ballpark-runtime__canvas,
.ballpark-runtime__canvas :deep(canvas) {
  width: 100% !important;
  height: 100% !important;
}

.ballpark-runtime__canvas :deep(canvas) {
  display: block;
  outline: none;
}

.ballpark-runtime__state {
  position: absolute;
  inset: 0;
  z-index: 4;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 12px;
  padding: 28px;
  color: #f3efe3;
  text-align: center;
  background: radial-gradient(circle, rgb(36 75 43 / 55%), rgb(7 7 7 / 96%) 58%);
}

.ballpark-runtime__state p,
.ballpark-runtime__state small {
  max-width: 48ch;
  color: #aab2bd;
}

.ballpark-runtime__spinner {
  width: 46px;
  height: 46px;
  border: 6px solid #3a414c;
  border-top-color: #ff9900;
  border-radius: 50%;
  animation: ballpark-spin 800ms linear infinite;
}

.ballpark-runtime__state-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.ballpark-runtime__state button,
.ballpark-runtime__state a,
.ballpark-runtime__hud button,
.ballpark-runtime__controls button {
  min-height: 42px;
  border: 1px solid #ff9900;
  border-radius: 9px;
  padding: 9px 14px;
  color: #070707;
  background: #ff9900;
  font-weight: 800;
  text-decoration: none;
  cursor: pointer;
}

.ballpark-runtime__hud {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) auto auto;
  gap: 10px;
  border-top: 1px solid #3a414c;
  padding: 12px;
  color: #f3efe3;
  background: #141414;
}

.ballpark-runtime__hud div {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.ballpark-runtime__hud span {
  color: #aab2bd;
  font: 600 11px/1.2 "Fira Code", Consolas, monospace;
  text-transform: uppercase;
}

.ballpark-runtime__hud strong {
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ballpark-runtime__controls {
  position: absolute;
  right: 18px;
  bottom: 86px;
  z-index: 3;
  display: none;
  grid-template-areas: ". up ." "left . right" ". down .";
  grid-template-columns: repeat(3, 48px);
  gap: 5px;
}

.ballpark-runtime__controls button {
  width: 48px;
  min-height: 48px;
  padding: 0;
  color: #f3efe3;
  background: rgb(20 20 20 / 90%);
  touch-action: none;
}

.ballpark-runtime__controls button:disabled,
.ballpark-runtime__hud button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ballpark-runtime__instructions {
  margin: 0;
  padding: 0 14px 14px;
  color: #aab2bd;
  background: #141414;
  font-size: 13px;
}

@keyframes ballpark-spin {
  to { transform: rotate(360deg); }
}

@media (hover: none), (pointer: coarse), (max-width: 760px) {
  .ballpark-runtime__controls { display: grid; }
  .ballpark-runtime__hud { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ballpark-runtime__hud button { grid-column: 1 / -1; }
  .ballpark-runtime__instructions { padding-right: 182px; }
}

@media (max-width: 520px) {
  .ballpark-runtime { border-radius: 0; }
  .ballpark-runtime__viewport { min-height: 390px; aspect-ratio: auto; }
  .ballpark-runtime__controls { right: 12px; bottom: 176px; }
  .ballpark-runtime__instructions { min-height: 86px; padding-right: 14px; }
}

@media (prefers-reduced-motion: reduce) {
  .ballpark-runtime__spinner { animation: none; border-top-color: #ffd166; }
}
</style>
