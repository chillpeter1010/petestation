<template>
  <section class="pitch-reel">
    <header>
      <div>
        <span><Clapperboard :size="15" /> Previous outing arsenal</span>
        <h2>{{ title }}</h2>
        <p v-if="response?.game_date">{{ response.game_date }} · one representative pitch from each of the six most-used pitch types.</p>
      </div>
      <strong v-if="response?.pitches.length">Top {{ response.pitches.length }} by usage</strong>
    </header>

    <p v-if="pending" class="pitch-reel__empty">Loading pitch videos…</p>
    <p v-else-if="!selection" class="pitch-reel__empty">This starter has no earlier appearance for the selected game.</p>
    <p v-else-if="!response?.pitches.length" class="pitch-reel__empty">No linked pitch videos are available for the previous appearance.</p>
    <div v-else class="pitch-reel__grid">
      <article
        v-for="row in response.pitches"
        :key="row.play_id"
        class="pitch-video"
        @mouseenter="playPreview"
        @mouseleave="stopPreview"
        @focusin="playPreview"
        @focusout="stopPreview"
      >
        <div class="pitch-video__media">
          <video v-if="videoUrls[row.play_id]" :src="videoUrls[row.play_id]" muted loop playsinline controls preload="metadata" />
          <div v-else class="pitch-video__placeholder"><Play :size="25" fill="currentColor" /><span>Resolving video</span></div>
          <strong>{{ row.usage_pct.toFixed(1) }}%</strong>
        </div>
        <div class="pitch-video__body">
          <div><h3>{{ row.pitch_name }}</h3><span>{{ row.pitch_count }} pitches</span></div>
          <p>{{ row.release_speed === null ? '—' : `${row.release_speed.toFixed(1)} mph` }}</p>
          <small>{{ row.description || 'Representative pitch from this outing.' }}</small>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { Clapperboard, Play } from '@lucide/vue'
import type { TeamPitchVideoResponse } from '~/types/api'

export interface StarterVideoSelection {
  teamId: string
  pitcherId: number
  pitcherName: string
  gamePk: number
}

const props = defineProps<{ selection: StarterVideoSelection | null; year: number }>()
const api = useApi()
const response = ref<TeamPitchVideoResponse | null>(null)
const pending = ref(false)
const videoUrls = reactive<Record<string, string>>({})
let requestId = 0

const title = computed(() => props.selection ? `${props.selection.pitcherName} pitch videos` : 'Previous outing pitch videos')

watch(() => props.selection, selection => { void load(selection) }, { immediate: true, deep: true })

async function load(selection: StarterVideoSelection | null) {
  const currentRequest = ++requestId
  response.value = null
  if (!selection) return
  pending.value = true
  try {
    const payload = await api.teamStarterPitchVideos({
      year: props.year,
      teamId: selection.teamId,
      pitcherId: selection.pitcherId,
      gamePk: selection.gamePk
    })
    if (currentRequest !== requestId) return
    response.value = payload
    await Promise.all(payload.pitches.map(async row => {
      if (videoUrls[row.play_id]) return
      try {
        const metadata = await api.teamDirectVideo(row.play_id)
        videoUrls[row.play_id] = cleanVideoUrl(metadata.direct_video_url)
      } catch {
        videoUrls[row.play_id] = ''
      }
    }))
  } finally {
    if (currentRequest === requestId) pending.value = false
  }
}

function playPreview(event: Event) {
  const video = (event.currentTarget as HTMLElement | null)?.querySelector('video')
  if (video) void video.play().catch(() => undefined)
}

function stopPreview(event: Event) {
  const video = (event.currentTarget as HTMLElement | null)?.querySelector('video')
  if (!video) return
  video.pause()
}

function cleanVideoUrl(value: unknown) {
  const text = String(value ?? '').trim()
  return text && !['None', 'nan', 'NaN'].includes(text) ? text : ''
}
</script>

<style scoped>
.pitch-reel { border: 1px solid var(--team-panel-border); border-radius: 16px; padding: clamp(18px, 3vw, 28px); background: var(--team-panel-bg); box-shadow: var(--shadow-sm); }
.pitch-reel > header { display: flex; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
.pitch-reel > header span { display: flex; align-items: center; gap: 7px; color: var(--team-accent); font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.pitch-reel h2 { margin: 5px 0 0; color: var(--color-text); font-size: 25px; }
.pitch-reel header p { margin: 6px 0 0; color: var(--color-muted-text); font-size: 12px; }
.pitch-reel header > strong { align-self: center; color: var(--color-muted-text); font-size: 11px; }
.pitch-reel__grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.pitch-video { min-width: 0; overflow: hidden; border: 1px solid var(--team-panel-border); border-radius: 13px; background: var(--color-surface); transition: border-color .16s ease, transform .16s ease; }
.pitch-video:hover, .pitch-video:focus-within { border-color: var(--team-primary); transform: translateY(-2px); }
.pitch-video__media { position: relative; aspect-ratio: 16 / 9; display: grid; place-items: center; overflow: hidden; color: var(--color-muted-text); background: #030508; }
.pitch-video__media video { width: 100%; height: 100%; object-fit: cover; }
.pitch-video__media > strong { position: absolute; right: 9px; bottom: 9px; border-radius: 999px; padding: 5px 8px; color: #fff; background: color-mix(in srgb, var(--team-primary) 88%, #080a0d); font: 900 12px "Fira Code", monospace; pointer-events: none; }
.pitch-video__placeholder { display: grid; justify-items: center; gap: 7px; font-size: 10px; font-weight: 800; }
.pitch-video__body { padding: 13px 14px 15px; }
.pitch-video__body > div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.pitch-video h3 { margin: 0; color: var(--color-text); font-size: 15px; }
.pitch-video__body span, .pitch-video__body p, .pitch-video__body small { color: var(--color-muted-text); font-size: 10px; }
.pitch-video__body p { margin: 7px 0; color: var(--team-accent); font: 800 11px "Fira Code", monospace; }
.pitch-video__body small { display: -webkit-box; overflow: hidden; line-height: 1.4; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.pitch-reel__empty { margin: 0; padding: 24px 0; color: var(--color-muted-text); }
@media (max-width: 980px) { .pitch-reel__grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 620px) { .pitch-reel > header { flex-direction: column; } .pitch-reel__grid { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .pitch-video { transition: none; } }
</style>
