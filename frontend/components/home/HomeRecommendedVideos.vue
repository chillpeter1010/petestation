<template>
  <section class="video-recommendations" aria-labelledby="recommended-title">
    <header>
      <div>
        <span>{{ searchQuery ? 'Video search' : 'Recommended videos' }}</span>
        <h2 id="recommended-title">{{ searchQuery ? `Results for “${searchQuery}”` : 'Twelve pitches worth watching' }}</h2>
        <p v-if="searchQuery">{{ videos.length }} matching plays, ordered by WPA.</p>
        <p v-else>Six recent high-WPA plays, four from the latest data month, and two from the archive.</p>
      </div>
      <div class="recommendation-meta">
        <button
          type="button"
          :disabled="loading"
          aria-label="Refresh recommended videos"
          title="Refresh recommended videos"
          @click="emit('refresh')"
        >
          <RefreshCw :size="20" :class="{ 'is-spinning': loading }" />
        </button>
        <small>Data through {{ latestDataDate || '—' }}</small>
      </div>
    </header>

    <p v-if="loading && !videos.length" class="video-state">Building today’s reel…</p>
    <p v-else-if="!videos.length" class="video-state">No recommended videos are available.</p>
    <div v-else class="video-grid">
      <button
        v-for="video in videos"
        :key="video.play_id"
        type="button"
        class="video-card"
        :aria-label="`Watch ${video.batter_name} versus ${video.pitcher_name}`"
        @click="openVideo(video)"
        @mouseenter="playPreview($event, video)"
        @mouseleave="stopPreview($event)"
        @focus="playPreview($event, video)"
        @blur="stopPreview($event)"
      >
        <span class="video-card__media">
          <video
            v-if="directVideos[video.play_id]"
            :src="directVideos[video.play_id]"
            muted
            loop
            playsinline
            preload="metadata"
          />
          <span v-else class="video-placeholder">
            <LoaderCircle v-if="previewLoading.has(video.play_id)" :size="25" class="is-spinning" />
            <Play v-else :size="25" fill="currentColor" />
            <small>{{ previewLoading.has(video.play_id) ? 'Loading preview' : 'Preview unavailable' }}</small>
          </span>
          <strong v-if="video.wpa !== null" class="video-card__wpa">{{ Math.round(video.wpa * 100) }}% WPA</strong>
        </span>
        <span class="video-card__body">
          <span class="source-pill">{{ sourceLabel(video.recommendation_source) }}</span>
          <strong class="video-card__title">{{ video.batter_name }} <small>vs</small> {{ video.pitcher_name }}</strong>
          <span class="video-card__description">{{ video.description }}</span>
          <span class="video-card__footer">
            <span>{{ shortDate(video.game_date) }} · {{ video.away_team }} @ {{ video.home_team }}</span>
            <span>{{ inningLabel(video) }} · {{ video.pitch_name || 'Pitch' }}</span>
          </span>
        </span>
      </button>
    </div>

    <DialogRoot v-model:open="dialogOpen">
      <DialogPortal>
        <DialogOverlay class="home-video-dialog__overlay" />
        <DialogContent class="home-video-dialog__content">
          <div class="home-video-dialog__header">
            <div>
              <DialogTitle class="home-video-dialog__title">{{ selected?.batter_name }} vs {{ selected?.pitcher_name }}</DialogTitle>
              <DialogDescription class="home-video-dialog__description">{{ selected?.description }}</DialogDescription>
            </div>
            <DialogClose class="home-video-dialog__close" aria-label="Close video"><X :size="20" /></DialogClose>
          </div>
          <div class="home-video-dialog__player">
            <LoaderCircle v-if="dialogLoading" :size="30" class="is-spinning" />
            <video v-else-if="dialogVideoUrl" :src="dialogVideoUrl" controls autoplay playsinline />
            <p v-else>This video preview is currently unavailable.</p>
          </div>
        </DialogContent>
      </DialogPortal>
    </DialogRoot>
  </section>
</template>

<script setup lang="ts">
import { LoaderCircle, Play, RefreshCw, X } from '@lucide/vue'
import { DialogClose, DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'
import type { HomeVideoRecommendation } from '~/types/api'

const props = defineProps<{
  videos: HomeVideoRecommendation[]
  latestDataDate: string | null
  loading: boolean
  searchQuery?: string
}>()

const emit = defineEmits<{ refresh: [] }>()
const api = useApi()
const directVideos = reactive<Record<string, string>>({})
const previewLoading = reactive(new Set<string>())
const dialogOpen = ref(false)
const dialogLoading = ref(false)
const dialogVideoUrl = ref('')
const selected = ref<HomeVideoRecommendation | null>(null)

watch(() => props.videos, rows => { void preloadRows(rows) }, { immediate: true })

async function preloadRows(rows: HomeVideoRecommendation[]) {
  for (let index = 0; index < rows.length; index += 3) {
    await Promise.all(rows.slice(index, index + 3).map(resolvePreview))
  }
}

async function resolvePreview(video: HomeVideoRecommendation) {
  if (directVideos[video.play_id] || previewLoading.has(video.play_id)) return
  previewLoading.add(video.play_id)
  try {
    const result = await api.teamDirectVideo(video.play_id)
    directVideos[video.play_id] = cleanValue(result.direct_video_url)
  } catch {
    directVideos[video.play_id] = ''
  } finally {
    previewLoading.delete(video.play_id)
  }
}

async function playPreview(event: Event, video: HomeVideoRecommendation) {
  const target = event.currentTarget as HTMLElement | null
  await resolvePreview(video)
  await nextTick()
  const player = target?.querySelector('video')
  if (player) void player.play().catch(() => undefined)
}

function stopPreview(event: Event) {
  const player = (event.currentTarget as HTMLElement | null)?.querySelector('video')
  if (!player) return
  player.pause()
  player.currentTime = 0
}

async function openVideo(video: HomeVideoRecommendation) {
  selected.value = video
  dialogVideoUrl.value = directVideos[video.play_id] || ''
  dialogOpen.value = true
  if (dialogVideoUrl.value) return
  dialogLoading.value = true
  await resolvePreview(video)
  dialogVideoUrl.value = directVideos[video.play_id] || ''
  dialogLoading.value = false
}

function cleanValue(value: unknown) {
  const text = String(value ?? '').trim()
  return text && !['None', 'nan', 'NaN'].includes(text) ? text : ''
}

function sourceLabel(source: string) {
  if (source === 'Search result') return 'Search match'
  if (source === 'Recent high WPA') return 'Last 14 days'
  if (source === 'Top plays this data month') return 'This data month'
  return 'Archive pull'
}

function shortDate(value: string) {
  const [, month, day] = value.split('-')
  return month && day ? `${month}/${day}` : value
}

function inningLabel(video: HomeVideoRecommendation) {
  if (!video.inning) return '—'
  return `${String(video.inning_half || '').toLowerCase() === 'top' ? 'Top' : 'Bot'} ${video.inning}`
}
</script>

<style scoped>
.video-recommendations { max-width: 1380px; margin-inline: auto; overflow: hidden; border: 1px solid var(--home-line); border-radius: 12px; background: rgba(12, 12, 12, .72); box-shadow: 0 24px 80px rgba(0, 0, 0, .34); }
.video-recommendations > header { display: flex; align-items: end; justify-content: space-between; gap: 20px; border-bottom: 1px solid var(--home-line); padding: 22px 24px; }
header > div > span { color: var(--home-orange); font-size: 11px; font-weight: 950; letter-spacing: .1em; text-transform: uppercase; }
h2 { margin: 5px 0 0; color: var(--home-text); font-size: clamp(25px, 3vw, 38px); }
header p { max-width: 700px; margin: 7px 0 0; color: var(--home-muted); font-size: 13px; }
.recommendation-meta { display: grid; justify-items: end; gap: 8px; }
.recommendation-meta button { width: 42px; height: 42px; display: grid; place-items: center; border: 1px solid var(--home-orange); border-radius: 50%; padding: 0; color: #111; background: var(--home-orange); cursor: pointer; transition: transform .16s ease, box-shadow .16s ease; }
.recommendation-meta button:hover { transform: rotate(-18deg); box-shadow: 0 0 0 5px rgba(255, 153, 0, .12); }
.recommendation-meta button:disabled { cursor: wait; opacity: .68; }
.recommendation-meta small { color: var(--home-muted); }
.video-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; background: var(--home-line); }
.video-card { min-width: 0; border: 0; padding: 0; overflow: hidden; color: inherit; background: #111; text-align: left; cursor: pointer; }
.video-card:focus-visible { position: relative; z-index: 1; outline: 2px solid var(--home-orange); outline-offset: -2px; }
.video-card__media { position: relative; aspect-ratio: 16 / 9; display: block; overflow: hidden; color: #fff; background: #050505; }
.video-card__media video { width: 100%; height: 100%; display: block; object-fit: cover; }
.video-card__media::after { content: ''; position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,.62), transparent 52%); pointer-events: none; }
.video-placeholder { position: absolute; inset: 0; display: grid; place-content: center; justify-items: center; gap: 8px; color: var(--home-orange); background: radial-gradient(circle at 50% 35%, rgba(255, 153, 0, .2), transparent 34%), linear-gradient(145deg, #20170c, #090909 60%); }
.video-placeholder small { color: var(--home-muted); font-size: 10px; font-weight: 800; }
.video-card__wpa { position: absolute; z-index: 1; right: 12px; bottom: 10px; border-radius: 999px; padding: 5px 9px; color: #111; background: var(--home-orange); font: 900 12px "Fira Code", monospace; }
.video-card__body { display: block; padding: 15px 16px 17px; }
.source-pill { display: inline-block; border: 1px solid rgba(255,153,0,.32); border-radius: 999px; padding: 4px 8px; color: var(--home-orange); background: rgba(255,153,0,.08); font-size: 9px; font-weight: 900; text-transform: uppercase; }
.video-card__title { display: block; overflow: hidden; margin-top: 10px; color: var(--home-text); font-size: 16px; text-overflow: ellipsis; white-space: nowrap; }
.video-card__title small { color: var(--home-muted); font-size: 10px; text-transform: uppercase; }
.video-card__description { height: 34px; display: -webkit-box; overflow: hidden; margin: 8px 0 12px; color: var(--home-muted); font-size: 11px; line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.video-card__footer { display: flex; justify-content: space-between; gap: 10px; color: #8d8d8d; font: 700 9px "Fira Code", monospace; }
.video-state { margin: 0; padding: 36px 24px; color: var(--home-muted); }
.is-spinning { animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
:global(.home-video-dialog__overlay) { position: fixed; z-index: 100; inset: 0; background: rgba(0, 0, 0, .82); backdrop-filter: blur(8px); }
:global(.home-video-dialog__content) { position: fixed; z-index: 101; top: 50%; left: 50%; width: min(920px, calc(100vw - 28px)); max-height: calc(100vh - 28px); overflow: auto; transform: translate(-50%, -50%); border: 1px solid rgba(255, 153, 0, .46); border-radius: 16px; padding: 18px; color: #f8fafc; background: #090909; box-shadow: 0 28px 100px rgba(0,0,0,.65); }
:global(.home-video-dialog__header) { display: flex; justify-content: space-between; gap: 18px; margin-bottom: 15px; }
:global(.home-video-dialog__title) { display: block; font-size: 19px; font-weight: 900; }
:global(.home-video-dialog__description) { display: block; max-width: 760px; margin-top: 6px; color: #aaa; font-size: 12px; line-height: 1.45; }
:global(.home-video-dialog__close) { width: 38px; height: 38px; flex: 0 0 auto; display: grid; place-items: center; border: 1px solid #333; border-radius: 9px; color: #fff; background: #171717; cursor: pointer; }
:global(.home-video-dialog__player) { aspect-ratio: 16 / 9; display: grid; place-items: center; overflow: hidden; border-radius: 12px; color: #aaa; background: #020202; }
:global(.home-video-dialog__player video) { width: 100%; height: 100%; object-fit: contain; }
@media (max-width: 980px) { .video-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 650px) { .video-recommendations > header { align-items: start; flex-direction: column; } .recommendation-meta { width: 100%; display: flex; align-items: center; justify-content: space-between; } .video-grid { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .recommendation-meta button { transition: none; } .is-spinning { animation: none; } }
</style>
