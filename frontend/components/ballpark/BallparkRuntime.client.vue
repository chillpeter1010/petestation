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
          <NuxtLink :to="fallbackRoute || '/'">Open Classic UI</NuxtLink>
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
      <button type="button" :disabled="status !== 'ready' || !worldState.nearby" @click="interact">Enter / Exit</button>
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
      Move with WASD, arrow keys, gamepad or touch. Use E or Enter at facility entrances; press R near a room’s exit to return to Ballpark. The Enter / Exit button also works. Safe reset returns to this room’s spawn.
    </p>
    <p v-if="worldState.characterWarning" class="ballpark-runtime__instructions" role="status">{{ worldState.characterWarning }}</p>
  </section>
</template>

<script setup lang="ts">
import type { BallparkPortalTarget, BallparkRoom, BallparkRuntimeHandle, BallparkRuntimeState } from './runtime/createBallparkGame'

const props = defineProps<{ room: BallparkRoom; arrivalId?: string; allowAdmin?: boolean; paused?: boolean; fallbackRoute?: string }>()
const emit = defineEmits<{ portal: [target: BallparkPortalTarget] }>()
const { user } = useAuth()

type RuntimeStatus = 'loading' | 'ready' | 'error'

const runtimeHost = ref<HTMLElement | null>(null)
const status = ref<RuntimeStatus>('loading')
const errorMessage = ref('The runtime is unavailable on this device. Use the static Ballpark map instead.')
const runtime = shallowRef<BallparkRuntimeHandle | null>(null)
const worldState = ref<BallparkRuntimeState>({
  status: 'paused',
  x: 800,
  y: 690,
  inputSource: 'idle',
  renderer: 'canvas',
  nearby: null
})
let mountId = 0
let loadTimeout: ReturnType<typeof setTimeout> | undefined

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

onMounted(async () => { await nextTick(); await mountRuntime() })
watch(runtimeHost, host => { if (host && !runtime.value && status.value === 'loading') void mountRuntime() }, { flush: 'post' })
watch(() => props.paused, value => runtime.value?.setPaused(Boolean(value)))
watch(() => [user.value?.avatar, user.value?.favorite_team_code] as const, ([avatar, team]) => { if (avatar) runtime.value?.setAppearance(avatar, team) })

onBeforeUnmount(() => {
  mountId += 1
  clearTimeout(loadTimeout)
  runtime.value?.destroy()
  runtime.value = null
})

async function mountRuntime() {
  const host = runtimeHost.value
  if (!host) return
  const currentMount = ++mountId
  runtime.value?.destroy()
  runtime.value = null
  host.replaceChildren()
  status.value = 'loading'
  clearTimeout(loadTimeout)
  loadTimeout = setTimeout(() => {
    if (currentMount !== mountId || status.value !== 'loading') return
    mountId += 1
    runtime.value?.destroy()
    runtime.value = null
    errorMessage.value = 'The scene did not finish loading. Retry or use the static Ballpark map.'
    status.value = 'error'
  }, 15000)

  try {
    const { createBallparkGame } = await import('./runtime/createBallparkGame')
    if (currentMount !== mountId) return
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handle = await createBallparkGame({
      parent: host,
      room: props.room,
      arrivalId: props.arrivalId,
      allowAdmin: props.allowAdmin,
      reducedMotion: media.matches,
      avatar: user.value?.avatar,
      favoriteTeam: user.value?.favorite_team_code,
      onError(error) { if (currentMount !== mountId) return; clearTimeout(loadTimeout); errorMessage.value = error.message; status.value = 'error' },
      onPortal(target) { emit('portal', target) },
      onState(nextState) {
        if (currentMount !== mountId) return
        clearTimeout(loadTimeout)
        worldState.value = nextState
        status.value = 'ready'
      }
    })
    if (currentMount !== mountId) {
      handle.destroy()
      return
    }
    runtime.value = handle
    handle.setPaused(Boolean(props.paused))
  } catch (error) {
    clearTimeout(loadTimeout)
    console.error('Unable to start Ballpark runtime', error)
    errorMessage.value = error instanceof Error ? error.message : 'Unknown runtime error.'
    status.value = 'error'
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
