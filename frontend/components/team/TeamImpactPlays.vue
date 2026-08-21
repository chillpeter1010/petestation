<template>
  <section class="impact-plays">
    <header>
      <div>
        <span><TrendingUp :size="15" /> Momentum reel</span>
        <h2>Recent high-WPA plays</h2>
      </div>
      <div class="impact-plays__controls" aria-label="Impact play unit">
        <button v-for="unit in units" :key="unit" type="button" :aria-pressed="selectedUnit === unit" @click="selectedUnit = unit">
          {{ unit }}
        </button>
      </div>
    </header>

    <div v-if="filteredRows.length" class="impact-plays__grid">
      <button
        v-for="row in filteredRows"
        :key="row.play_id"
        type="button"
        class="impact-card"
        @click="openPlay(row)"
        @mouseenter="previewVideo($event, row)"
        @mouseleave="stopPreview($event)"
        @focus="previewVideo($event, row)"
        @blur="stopPreview($event)"
      >
        <span class="impact-card__visual">
          <video v-if="videoUrls[row.play_id]" :src="videoUrls[row.play_id]" muted loop playsinline preload="metadata" />
          <span v-else class="impact-card__loading"><Play :size="24" fill="currentColor" /><small>Loading preview</small></span>
          <strong>+{{ formatWpa(row.team_wpa) }}</strong>
        </span>
        <span class="impact-card__meta">{{ formatDate(row.game_date) }} · {{ row.home_away === 'Home' ? 'vs' : '@' }} {{ row.opponent }} · {{ inningLabel(row) }}</span>
        <strong class="impact-card__title">{{ row.batter_name }} vs {{ row.pitcher_name }}</strong>
        <span class="impact-card__description">{{ row.description }}</span>
        <span class="impact-card__pitch">{{ row.pitch_name || 'Pitch' }} · {{ formatEvent(row.event) }}</span>
      </button>
    </div>
    <p v-else class="impact-plays__empty">No linked high-impact videos are available for this period.</p>

    <DialogRoot v-model:open="dialogOpen">
      <DialogPortal>
        <DialogOverlay class="impact-dialog__overlay" />
        <DialogContent class="impact-dialog__content" @escape-key-down="closeDialog">
          <div class="impact-dialog__header">
            <div>
              <DialogTitle class="impact-dialog__title">{{ selected?.batter_name }} vs {{ selected?.pitcher_name }}</DialogTitle>
              <DialogDescription class="impact-dialog__description">{{ selected?.description }}</DialogDescription>
            </div>
            <DialogClose class="impact-dialog__close" aria-label="Close video"><X :size="20" /></DialogClose>
          </div>
          <div class="impact-dialog__player">
            <div v-if="videoLoading" class="impact-dialog__loading">Loading video…</div>
            <video v-else-if="directVideoUrl" :src="directVideoUrl" controls autoplay playsinline @error="directVideoUrl = ''" />
            <div v-else class="impact-dialog__fallback">
              <CircleAlert :size="28" />
              <p>The direct stream could not be loaded here.</p>
              <a v-if="selected" :href="selected.video_url" target="_blank" rel="noopener">Open video on Baseball Savant <ExternalLink :size="15" /></a>
            </div>
          </div>
        </DialogContent>
      </DialogPortal>
    </DialogRoot>
  </section>
</template>

<script setup lang="ts">
import { CircleAlert, ExternalLink, Play, TrendingUp, X } from '@lucide/vue'
import { DialogClose, DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'
import type { TeamImpactPlay } from '~/types/api'

const props = defineProps<{ rows: TeamImpactPlay[] }>()
const api = useApi()
const units = ['Batter', 'Pitcher'] as const
const selectedUnit = ref<(typeof units)[number]>('Batter')
const videoUrls = reactive<Record<string, string>>({})
const resolving = new Set<string>()
const dialogOpen = ref(false)
const selected = ref<TeamImpactPlay | null>(null)
const directVideoUrl = ref('')
const videoLoading = ref(false)
const filteredRows = computed(() => props.rows.filter(row => row.team_unit === selectedUnit.value).slice(0, 6))

onMounted(() => {
  watch(filteredRows, rows => { void preloadRows(rows) }, { immediate: true })
})

async function preloadRows(rows: TeamImpactPlay[]) {
  for (const row of rows) await resolvePreview(row)
}

async function resolvePreview(row: TeamImpactPlay) {
  if (videoUrls[row.play_id] || resolving.has(row.play_id)) return
  resolving.add(row.play_id)
  try {
    const meta = await api.teamDirectVideo(row.play_id)
    videoUrls[row.play_id] = cleanValue(meta.direct_video_url)
  } catch {
    videoUrls[row.play_id] = ''
  } finally {
    resolving.delete(row.play_id)
  }
}

async function previewVideo(event: Event, row: TeamImpactPlay) {
  const target = event.currentTarget as HTMLElement | null
  await resolvePreview(row)
  await nextTick()
  const video = target?.querySelector('video')
  if (video) void video.play().catch(() => undefined)
}

function stopPreview(event: Event) {
  const video = (event.currentTarget as HTMLElement | null)?.querySelector('video')
  if (!video) return
  video.pause()
  video.currentTime = 0
}

async function openPlay(row: TeamImpactPlay) {
  selected.value = row
  directVideoUrl.value = videoUrls[row.play_id] || ''
  videoLoading.value = false
  dialogOpen.value = true
  if (directVideoUrl.value) return
  videoLoading.value = true
  try {
    const meta = await api.teamDirectVideo(row.play_id)
    directVideoUrl.value = cleanValue(meta.direct_video_url)
  } catch {
    directVideoUrl.value = ''
  } finally {
    videoLoading.value = false
  }
}

function closeDialog() { dialogOpen.value = false }
function cleanValue(value: unknown) { const text = String(value ?? '').trim(); return text && !['None', 'nan', 'NaN'].includes(text) ? text : '' }
function formatWpa(value: number) { return `${Math.round(value * 100)}% WPA` }
function formatDate(value: string) { return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(`${value}T00:00:00`)) }
function inningLabel(row: TeamImpactPlay) { return `${row.inning_half === 'Top' ? 'Top' : 'Bot'} ${row.inning}` }
function formatEvent(value: string | null) { return (value || 'impact play').replaceAll('_', ' ') }
</script>

<style scoped>
.impact-plays { border: 1px solid var(--team-panel-border); border-radius: 16px; padding: clamp(18px, 3vw, 28px); background: var(--team-panel-bg); box-shadow: var(--shadow-sm); }
.impact-plays > header { display: flex; justify-content: space-between; gap: 24px; margin-bottom: 18px; }
.impact-plays > header span { display: flex; align-items: center; gap: 7px; color: var(--team-accent); font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.impact-plays h2 { margin: 5px 0 0; color: var(--color-text); font-size: 25px; }
.impact-plays__controls { display: flex; align-self: center; gap: 5px; border: 1px solid var(--team-panel-border); border-radius: 10px; padding: 4px; background: var(--color-surface); }
.impact-plays__controls button { min-height: 34px; border: 0; border-radius: 7px; padding: 6px 13px; color: var(--color-muted-text); background: transparent; font-size: 11px; font-weight: 900; cursor: pointer; }
.impact-plays__controls button[aria-pressed="true"] { color: #fff; background: var(--team-primary); }
.impact-plays__grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.impact-card { min-width: 0; display: flex; flex-direction: column; align-items: stretch; border: 1px solid var(--team-panel-border); border-radius: 14px; padding: 0; overflow: hidden; color: inherit; background: var(--color-surface); text-align: left; cursor: pointer; transition: transform .16s ease, border-color .16s ease; }
.impact-card:hover, .impact-card:focus-visible { border-color: var(--team-primary); transform: translateY(-2px); outline: none; }
.impact-card__visual { position: relative; min-height: 150px; display: flex; align-items: center; justify-content: center; overflow: hidden; color: #fff; background: #05070a; }
.impact-card__visual video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.impact-card__visual::after { content: ""; position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,.72), transparent 58%); pointer-events: none; }
.impact-card__visual > strong { position: absolute; z-index: 1; right: 12px; bottom: 10px; border-radius: 999px; padding: 5px 9px; background: color-mix(in srgb, var(--team-primary) 88%, #090b10); font: 900 13px "Fira Code", monospace; }
.impact-card__loading { display: grid; justify-items: center; gap: 7px; color: var(--color-muted-text); }
.impact-card__loading small { font-size: 10px; font-weight: 800; }
.impact-card__meta, .impact-card__title, .impact-card__description, .impact-card__pitch { margin-inline: 15px; }
.impact-card__meta { margin-top: 14px; color: var(--team-accent); font-size: 10px; font-weight: 900; text-transform: uppercase; }
.impact-card__title { margin-top: 7px; color: var(--color-text); font-size: 14px; }
.impact-card__description { display: -webkit-box; margin-top: 7px; overflow: hidden; color: var(--color-muted-text); font-size: 12px; line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.impact-card__pitch { margin-top: 12px; margin-bottom: 15px; color: var(--color-muted-text); font: 700 10px "Fira Code", monospace; text-transform: capitalize; }
.impact-plays__empty { color: var(--color-muted-text); }
:global(.impact-dialog__overlay) { position: fixed; z-index: 100; inset: 0; background: rgba(2, 5, 10, .8); backdrop-filter: blur(7px); }
:global(.impact-dialog__content) { position: fixed; z-index: 101; top: 50%; left: 50%; width: min(920px, calc(100vw - 28px)); max-height: calc(100vh - 28px); overflow: auto; transform: translate(-50%, -50%); border: 1px solid color-mix(in srgb, var(--team-primary) 50%, #394150); border-radius: 16px; padding: 18px; color: #f8fafc; background: #0a0d13; box-shadow: 0 28px 100px rgba(0,0,0,.55); }
:global(.impact-dialog__header) { display: flex; justify-content: space-between; gap: 18px; margin-bottom: 15px; }
:global(.impact-dialog__title) { display: block; font-size: 19px; font-weight: 900; }
:global(.impact-dialog__description) { display: block; max-width: 760px; margin-top: 6px; color: #aeb5c0; font-size: 12px; line-height: 1.45; }
:global(.impact-dialog__close) { width: 38px; height: 38px; flex: 0 0 auto; display: grid; place-items: center; border: 1px solid #313844; border-radius: 9px; color: #fff; background: #151a22; cursor: pointer; }
:global(.impact-dialog__player) { aspect-ratio: 16 / 9; display: grid; place-items: center; overflow: hidden; border-radius: 12px; background: #020305; }
:global(.impact-dialog__player video) { width: 100%; height: 100%; object-fit: contain; }
:global(.impact-dialog__loading), :global(.impact-dialog__fallback) { color: #aeb5c0; text-align: center; }
:global(.impact-dialog__fallback a) { display: inline-flex; align-items: center; gap: 7px; margin-top: 8px; color: #fff; font-weight: 800; }
@media (max-width: 980px) { .impact-plays__grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 620px) { .impact-plays > header { flex-direction: column; } .impact-plays__controls { align-self: flex-start; } .impact-plays__grid { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .impact-card { transition: none; } }
</style>
