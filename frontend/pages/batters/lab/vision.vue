<template>
  <main class="vision-page">
    <header class="vision-hero">
      <div>
        <nav>
          <NuxtLink to="/batters">Batters</NuxtLink><span>/</span>
          <NuxtLink to="/batters/lab">Lab</NuxtLink><span>/</span><b>Vision</b>
        </nav>
        <span class="eyebrow">Batter Lab · Representative swing</span>
        <h1>Vision</h1>
      </div>
      <div v-if="selectedBatter" class="player-lockup">
        <MlbPlayerHeadshot :player-id="selectedBatter.batter_id" :name="selectedBatter.name" :size="68" shape="circle" />
        <div><strong>{{ selectedBatter.name }}</strong><span>{{ selectedBatter.team }} · {{ selectedBatter.batter_side }}</span></div>
      </div>
    </header>

    <section class="vision-controls" aria-label="Vision filters">
      <label>
        <span>Season</span>
        <select v-model.number="year">
          <option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <label>
        <span>Pitch group</span>
        <select v-model="pitchGroup">
          <option v-for="option in pitchGroupOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <label>
        <span>Pitch type</span>
        <select v-model="pitchType">
          <option value="All">All in group</option>
          <option v-for="option in visiblePitchTypes" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <label class="hitter-select">
        <span>Hitter</span>
        <select v-model.number="selectedBatterId">
          <option v-for="row in response?.leaderboard || []" :key="row.batter_id" :value="row.batter_id">{{ row.name }} · {{ row.team }}</option>
        </select>
      </label>
      <div class="play-controls">
        <span>Playback</span>
        <div>
          <button type="button" :aria-pressed="playing" @click="playing = !playing">{{ playing ? 'Pause' : 'Play' }}</button>
          <button v-for="option in speedOptions" :key="option" type="button" :class="{ active: speed === option }" :aria-pressed="speed === option" @click="speed = option">{{ option }}×</button>
        </div>
      </div>
    </section>

    <p v-if="pending" class="state-card">Loading Vision…</p>
    <p v-else-if="error" class="state-card error">Unable to load Vision.</p>
    <p v-else-if="!selectedBatter" class="state-card">No qualified hitters for these filters.</p>

    <template v-else>
      <section class="metric-strip" aria-label="Selected hitter summary">
        <article><span>Swings</span><strong>{{ integer(selectedBatter.n_swings) }}</strong></article>
        <article><span>Centered</span><strong>{{ percent(selectedBatter.centered_pct) }}</strong></article>
        <article><span>On time</span><strong>{{ percent(selectedBatter.on_time_pct) }}</strong></article>
        <article><span>Lined up</span><strong>{{ percent(selectedBatter.lined_up_pct) }}</strong></article>
        <article><span>Avg miss</span><strong>{{ distance(selectedBatter.miss_distance) }}</strong></article>
      </section>

      <section class="vision-stage">
        <header>
          <div><span>Cycle {{ cycleIndex + 1 }}</span><h2>Bat-to-ball alignment</h2></div>
          <div class="timeline" aria-hidden="true"><i :style="{ width: `${progress * 100}%` }" /></div>
        </header>

        <div class="panel-grid">
          <article v-for="panel in panels" :key="panel.key" class="motion-panel">
            <header>
              <div><span>{{ panel.eyebrow }}</span><h3>{{ panel.title }}</h3></div>
              <strong :class="{ ideal: panelState(panel.key).ideal }">{{ panelState(panel.key).label }}</strong>
            </header>

            <svg viewBox="0 0 340 220" role="img" :aria-label="`${panel.title}: ${panelState(panel.key).label}`">
              <rect x="12" y="12" width="316" height="196" rx="18" class="field" />
              <line x1="34" y1="116" x2="304" y2="116" class="flight-path" />
              <line x1="202" y1="42" x2="202" y2="190" class="contact-line" />
              <rect x="188" y="101" width="28" height="30" rx="6" class="contact-window" />
              <circle :cx="ballX" :cy="ballY" r="8" class="ball" />
              <g :transform="batTransform(panel.key)">
                <line x1="282" y1="116" x2="142" y2="116" class="bat-shadow" />
                <line x1="282" y1="116" x2="142" y2="116" class="bat" />
                <circle cx="282" cy="116" r="6" class="handle" />
              </g>
              <text x="30" y="199" class="axis-label">{{ panel.low }}</text>
              <text x="170" y="199" text-anchor="middle" class="axis-label ideal-label">{{ panel.middle }}</text>
              <text x="310" y="199" text-anchor="end" class="axis-label">{{ panel.high }}</text>
            </svg>

            <footer>
              <div><span>Share</span><strong>{{ percent(panelState(panel.key).percentage) }}</strong></div>
              <div><span>Avg error</span><strong>{{ deviation(panel.key) }}</strong></div>
              <div><span>Window</span><strong>{{ panel.window }}</strong></div>
            </footer>
          </article>
        </div>

        <footer class="stage-note">
          <span>Summary-driven representative animation</span>
          <p>Each cycle samples the hitter’s observed category rates. Motion illustrates the average miss direction; it is not a tracked 3D replay.</p>
        </footer>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import type { SwingTimingLeaderboardRow, SwingTimingResponse } from '~/types/api'

type PanelKey = 'horizontal' | 'timing' | 'vertical'
type MotionState = { label: string; percentage: number | null; offset: number; ideal: boolean }

const api = useApi()
const year = ref(2026)
const pitchGroup = ref('all')
const pitchType = ref('All')
const selectedBatterId = ref<number | null>(null)
const playing = ref(true)
const speed = ref(1)
const progress = ref(0)
const cycleIndex = ref(0)
const speedOptions = [0.5, 1, 2]
const fallbackPitchGroups = [
  { value: 'all', label: 'All pitch types' },
  { value: 'fastball', label: 'Fastball' },
  { value: 'breaking', label: 'Breaking Ball' },
  { value: 'offspeed', label: 'Offspeed' },
  { value: 'other', label: 'Other' }
]

const panels: Array<{ key: PanelKey; eyebrow: string; title: string; low: string; middle: string; high: string; window: string }> = [
  { key: 'horizontal', eyebrow: 'Horizontal', title: 'Barrel reach', low: 'Tied up', middle: 'Centered', high: 'Flail', window: '±4 in' },
  { key: 'timing', eyebrow: 'Timing', title: 'Arrival time', low: 'Late', middle: 'On time', high: 'Early', window: '±7 ms' },
  { key: 'vertical', eyebrow: 'Vertical', title: 'Barrel height', low: 'Over', middle: 'Lined up', high: 'Under', window: '±2 in' }
]

const { data: response, pending, error } = await useAsyncData<SwingTimingResponse>(
  'batter-vision',
  () => api.batterSwingTiming({
    year: year.value,
    pitchGroup: pitchGroup.value,
    pitchType: pitchType.value,
    pitcherHand: 'All',
    batterSide: 'All',
    batterTeam: 'All',
    pitcherTeam: 'All',
    minimumSwings: 25,
    minimumPlateAppearances: 100
  }),
  { watch: [year, pitchGroup, pitchType] }
)

const yearOptions = computed(() => response.value?.filters.available_years?.length ? response.value.filters.available_years : [2026, 2025, 2024, 2023])
const pitchGroupOptions = computed(() => response.value?.filters.pitch_groups?.length ? response.value.filters.pitch_groups : fallbackPitchGroups)
const pitchTypeGroups = computed(() => response.value?.filters.pitch_type_groups || [])
const visiblePitchTypes = computed(() => {
  if (pitchGroup.value === 'all') return pitchTypeGroups.value.flatMap(group => group.options)
  return pitchTypeGroups.value.find(group => group.key === pitchGroup.value)?.options || []
})
const selectedBatter = computed(() => response.value?.leaderboard.find(row => row.batter_id === selectedBatterId.value) || response.value?.leaderboard[0] || null)

watch(response, (value) => {
  const rows = value?.leaderboard || []
  if (!rows.some(row => row.batter_id === selectedBatterId.value)) selectedBatterId.value = rows[0]?.batter_id ?? null
}, { immediate: true })

watch(pitchGroup, () => { pitchType.value = 'All' })

function weightedState(states: MotionState[], seed: number) {
  const total = states.reduce((sum, state) => sum + Math.max(0, state.percentage || 0), 0)
  if (!total) return states.find(state => state.ideal) || states[0]
  let cursor = (((cycleIndex.value * 0.61803398875) + seed) % 1) * total
  for (const state of states) {
    cursor -= Math.max(0, state.percentage || 0)
    if (cursor <= 0) return state
  }
  return states[states.length - 1]
}

function panelState(key: PanelKey): MotionState {
  const row = selectedBatter.value
  if (!row) return { label: 'No data', percentage: null, offset: 0, ideal: true }
  if (key === 'horizontal') {
    return weightedState([
      { label: 'Tied up', percentage: row.tied_up_pct, offset: -Math.abs(row.avg_tied_up_distance || 5), ideal: false },
      { label: 'Centered', percentage: row.centered_pct, offset: 0, ideal: true },
      { label: 'Flail', percentage: row.flail_pct, offset: Math.abs(row.avg_flail_distance || 5), ideal: false }
    ], 0.07)
  }
  if (key === 'timing') {
    return weightedState([
      { label: 'Late', percentage: row.late_pct, offset: -Math.abs(row.avg_late_ms || 10), ideal: false },
      { label: 'On time', percentage: row.on_time_pct, offset: 0, ideal: true },
      { label: 'Early', percentage: row.early_pct, offset: Math.abs(row.avg_early_ms || 10), ideal: false }
    ], 0.41)
  }
  return weightedState([
    { label: 'Over', percentage: row.over_pct, offset: -Math.abs(row.avg_over_distance || 3), ideal: false },
    { label: 'Lined up', percentage: row.lined_up_pct, offset: 0, ideal: true },
    { label: 'Under', percentage: row.under_pct, offset: Math.abs(row.avg_under_distance || 3), ideal: false }
  ], 0.73)
}

const ballX = computed(() => 34 + progress.value * 270)
const ballY = 116

function batTransform(key: PanelKey) {
  const state = panelState(key)
  const phaseShift = key === 'timing' ? state.offset / 52 : 0
  const swingProgress = Math.max(0, Math.min(1, progress.value + phaseShift))
  const angle = -72 + swingProgress * 118
  const contactEmphasis = Math.sin(Math.PI * Math.max(0, Math.min(1, progress.value)))
  const horizontalOffset = key === 'horizontal' ? state.offset * 3.4 * contactEmphasis : 0
  const verticalOffset = key === 'vertical' ? state.offset * 5.2 * contactEmphasis : 0
  return `translate(${horizontalOffset.toFixed(2)} ${verticalOffset.toFixed(2)}) rotate(${angle.toFixed(2)} 282 116)`
}

function deviation(key: PanelKey) {
  const state = panelState(key)
  if (state.ideal) return key === 'timing' ? '±7 ms' : key === 'horizontal' ? '±4 in' : '±2 in'
  return `${Math.abs(state.offset).toFixed(1)} ${key === 'timing' ? 'ms' : 'in'}`
}

function percent(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? '—' : `${value.toFixed(1)}%`
}

function distance(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? '—' : `${value.toFixed(1)} in`
}

function integer(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? '—' : Math.round(value).toLocaleString()
}

let animationFrame = 0
let cycleStarted = 0
const cycleDuration = 2600

function animate(timestamp: number) {
  if (!cycleStarted) cycleStarted = timestamp - progress.value * cycleDuration / speed.value
  if (playing.value) {
    const elapsed = (timestamp - cycleStarted) * speed.value
    if (elapsed >= cycleDuration) {
      cycleIndex.value += Math.floor(elapsed / cycleDuration)
      cycleStarted = timestamp
      progress.value = 0
    } else {
      progress.value = elapsed / cycleDuration
    }
  } else {
    cycleStarted = timestamp - progress.value * cycleDuration / speed.value
  }
  animationFrame = requestAnimationFrame(animate)
}

watch(speed, () => { cycleStarted = 0 })

onMounted(() => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    playing.value = false
    progress.value = 0.62
  }
  animationFrame = requestAnimationFrame(animate)
})

onBeforeUnmount(() => cancelAnimationFrame(animationFrame))
</script>

<style scoped>
.vision-page { max-width: 1460px; min-height: 100vh; margin: 0 auto; padding: 92px 22px 64px; }
.vision-hero, .vision-controls, .metric-strip, .vision-stage, .state-card { border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); box-shadow: var(--shadow-sm); }
.vision-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 28px; padding: 30px; background: radial-gradient(circle at top right, color-mix(in srgb, #69d3c3 20%, transparent), transparent 36%), var(--color-surface); }
nav { display: flex; gap: 9px; margin-bottom: 22px; color: var(--color-muted-text); font-size: 13px; }
nav a { color: inherit; }
.eyebrow, .vision-controls > label > span, .play-controls > span, .metric-strip span, .vision-stage > header span, .motion-panel header span, .motion-panel footer span, .stage-note > span { color: var(--color-primary); font-size: 12px; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; }
h1 { margin: 12px 0 0; color: var(--color-foreground); font-size: clamp(48px, 6vw, 76px); font-weight: 750; line-height: 1.05; letter-spacing: -.015em; }
.player-lockup { display: flex; align-items: center; gap: 13px; min-width: 250px; border: 1px solid var(--color-border); border-radius: 18px; padding: 12px 15px; background: color-mix(in srgb, var(--color-background) 82%, transparent); }
.player-lockup div { display: grid; gap: 4px; }
.player-lockup strong { color: var(--color-foreground); font-size: 18px; }
.player-lockup span { color: var(--color-muted-text); font-size: 13px; }
.vision-controls { display: grid; grid-template-columns: 130px 190px 210px minmax(240px, 1fr) auto; gap: 12px; margin-top: 18px; padding: 18px; }
.vision-controls label, .play-controls { display: grid; gap: 7px; }
select, button { min-height: 44px; border: 1px solid var(--color-border-strong); border-radius: 11px; color: var(--color-foreground); background: var(--color-background); font: inherit; font-size: 15px; font-weight: 700; }
select { width: 100%; padding: 0 12px; }
button { cursor: pointer; padding: 0 14px; }
button:hover, button.active, button[aria-pressed="true"] { border-color: var(--color-primary); color: var(--color-on-primary); background: var(--color-primary); }
.play-controls > div { display: flex; gap: 6px; }
.play-controls button:first-child { min-width: 72px; }
.play-controls button:not(:first-child) { min-width: 48px; }
.state-card { margin: 18px 0 0; padding: 22px; color: var(--color-muted-text); }
.state-card.error { color: var(--color-danger); }
.metric-strip { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); margin-top: 18px; overflow: hidden; }
.metric-strip article { display: grid; gap: 8px; padding: 18px 20px; }
.metric-strip article + article { border-left: 1px solid var(--color-border); }
.metric-strip strong { color: var(--color-foreground); font-size: 26px; font-weight: 750; }
.vision-stage { margin-top: 18px; overflow: hidden; }
.vision-stage > header { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; padding: 22px 24px; border-bottom: 1px solid var(--color-border); }
.vision-stage h2 { margin: 8px 0 0; color: var(--color-foreground); font-size: clamp(26px, 3vw, 38px); font-weight: 750; line-height: 1.1; letter-spacing: -.01em; }
.timeline { width: min(420px, 42vw); height: 6px; overflow: hidden; border-radius: 99px; background: var(--color-border); }
.timeline i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--color-primary), #69d3c3); }
.panel-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; background: var(--color-border); }
.motion-panel { min-width: 0; background: var(--color-surface); }
.motion-panel > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 18px 20px 0; }
.motion-panel h3 { margin: 6px 0 0; color: var(--color-foreground); font-size: 20px; line-height: 1.2; }
.motion-panel > header > strong { border: 1px solid color-mix(in srgb, #ef6a64 55%, var(--color-border)); border-radius: 999px; padding: 7px 10px; color: #ff9993; font-size: 12px; }
.motion-panel > header > strong.ideal { border-color: color-mix(in srgb, #69d3c3 55%, var(--color-border)); color: #8ce3d7; }
.motion-panel svg { display: block; width: 100%; height: auto; padding: 4px 10px 0; }
.field { fill: color-mix(in srgb, var(--color-background) 80%, transparent); stroke: var(--color-border); }
.flight-path { stroke: color-mix(in srgb, var(--color-muted-text) 35%, transparent); stroke-width: 1.5; stroke-dasharray: 5 7; }
.contact-line { stroke: color-mix(in srgb, var(--color-primary) 62%, transparent); stroke-width: 1.5; stroke-dasharray: 3 5; }
.contact-window { fill: color-mix(in srgb, #69d3c3 13%, transparent); stroke: color-mix(in srgb, #69d3c3 55%, transparent); }
.ball { fill: #f7f4ed; stroke: #d95f57; stroke-width: 2; filter: drop-shadow(0 3px 7px rgba(0, 0, 0, .35)); }
.bat-shadow { stroke: rgba(0, 0, 0, .28); stroke-width: 18; stroke-linecap: round; }
.bat { stroke: #d7a96d; stroke-width: 13; stroke-linecap: round; }
.handle { fill: #f0c58d; stroke: #5d4027; stroke-width: 2; }
.axis-label { fill: var(--color-muted-text); font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.ideal-label { fill: #8ce3d7; }
.motion-panel footer { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-top: 1px solid var(--color-border); }
.motion-panel footer div { display: grid; gap: 5px; padding: 14px 16px 17px; }
.motion-panel footer div + div { border-left: 1px solid var(--color-border); }
.motion-panel footer strong { color: var(--color-foreground); font-size: 17px; }
.stage-note { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 17px 24px; border-top: 1px solid var(--color-border); }
.stage-note p { max-width: 760px; margin: 0; color: var(--color-muted-text); font-size: 13px; line-height: 1.5; text-align: right; }
@media (max-width: 1120px) { .vision-controls { grid-template-columns: repeat(2, minmax(0, 1fr)); } .hitter-select { grid-column: 1 / -1; } .panel-grid { grid-template-columns: 1fr; } }
@media (max-width: 700px) { .vision-page { padding: 28px 12px 48px; } .vision-hero { align-items: flex-start; flex-direction: column; } .player-lockup { width: 100%; } .vision-controls, .metric-strip { grid-template-columns: 1fr; } .hitter-select { grid-column: auto; } .metric-strip article + article { border-top: 1px solid var(--color-border); border-left: 0; } .vision-stage > header, .stage-note { align-items: flex-start; flex-direction: column; } .timeline { width: 100%; } .stage-note p { text-align: left; } }
@media (prefers-reduced-motion: reduce) { .timeline i { transition: none; } }
</style>
