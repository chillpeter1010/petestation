<template>
  <section class="period-module">
    <header class="module-header">
      <div>
        <h2>Videos</h2>
        <p>Select a pitch in Period Location to play its direct video.</p>
      </div>
      <span>{{ left.total.toLocaleString() }} A pitches / {{ right.total.toLocaleString() }} B pitches</span>
    </header>

    <div class="video-grid">
      <div class="video-slot">
        <h3>Period A Video</h3>
        <VideoPanel
          :state="leftVideo"
          empty-label="No Period A pitch selected"
          empty-help="Click a Period A location dot above."
          title="Period A selected pitch video"
        />
      </div>
      <div class="video-slot">
        <h3>Period B Video</h3>
        <VideoPanel
          :state="rightVideo"
          empty-label="No Period B pitch selected"
          empty-help="Click a Period B location dot above."
          title="Period B selected pitch video"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { defineComponent, h, type PropType } from 'vue'

const props = defineProps<{
  left: { rows: Record<string, unknown>[]; total: number }
  right: { rows: Record<string, unknown>[]; total: number }
  selectedLeftPoint?: Record<string, unknown> | null
  selectedRightPoint?: Record<string, unknown> | null
}>()

const api = useApi()
type VideoState = {
  directVideoUrl: string
  sportyVideoUrl: string
  loadingVideo: boolean
  directVideoFailed: boolean
  hasSelection: boolean
}

const leftVideo = reactive<VideoState>(createVideoState())
const rightVideo = reactive<VideoState>(createVideoState())

watch(
  () => [
    cleanValue(props.selectedLeftPoint?.play_id),
    cleanValue(props.selectedLeftPoint?.video_url),
    cleanValue(props.selectedLeftPoint?.game_pk),
    cleanValue(props.selectedLeftPoint?.at_bat_number),
    cleanValue(props.selectedLeftPoint?.pitch_number)
  ] as const,
  async ([playId, sourceUrl, gamePk, atBatNumber, pitchNumber]) => resolveVideo(leftVideo, props.selectedLeftPoint, { playId, sourceUrl, gamePk, atBatNumber, pitchNumber }),
  { immediate: true }
)

watch(
  () => [
    cleanValue(props.selectedRightPoint?.play_id),
    cleanValue(props.selectedRightPoint?.video_url),
    cleanValue(props.selectedRightPoint?.game_pk),
    cleanValue(props.selectedRightPoint?.at_bat_number),
    cleanValue(props.selectedRightPoint?.pitch_number)
  ] as const,
  async ([playId, sourceUrl, gamePk, atBatNumber, pitchNumber]) => resolveVideo(rightVideo, props.selectedRightPoint, { playId, sourceUrl, gamePk, atBatNumber, pitchNumber }),
  { immediate: true }
)

const VideoPanel = defineComponent({
  props: {
    state: {
      type: Object as PropType<VideoState>,
      required: true
    },
    emptyLabel: {
      type: String,
      required: true
    },
    emptyHelp: {
      type: String,
      required: true
    },
    title: {
      type: String,
      required: true
    }
  },
  setup(panelProps) {
    return () => {
      const state = panelProps.state
      let content
      if (!state.hasSelection) {
        content = h('div', { class: 'empty-state' }, [h('strong', panelProps.emptyLabel), h('span', panelProps.emptyHelp)])
      } else if (state.loadingVideo) {
        content = h('div', { class: 'empty-state' }, [h('strong', 'Loading video'), h('span', 'Resolving the direct MLB clip URL.')])
      } else if (state.directVideoUrl && !state.directVideoFailed) {
        content = h('video', {
          key: state.directVideoUrl,
          src: state.directVideoUrl,
          controls: true,
          playsinline: true,
          onError: () => {
            state.directVideoFailed = true
          }
        })
      } else if (state.sportyVideoUrl) {
        content = h('iframe', {
          key: state.sportyVideoUrl,
          src: state.sportyVideoUrl,
          title: panelProps.title
        })
      } else {
        content = h('div', { class: 'empty-state' }, [h('strong', 'No video mapping'), h('span', 'This pitch has no video URL or play ID available yet.')])
      }
      return h('div', { class: 'selected-video-panel' }, [content])
    }
  }
})

function createVideoState(): VideoState {
  return {
    directVideoUrl: '',
    sportyVideoUrl: '',
    loadingVideo: false,
    directVideoFailed: false,
    hasSelection: false
  }
}

async function resolveVideo(
  state: VideoState,
  point: Record<string, unknown> | null | undefined,
  fields: { playId: string; sourceUrl: string; gamePk: string; atBatNumber: string; pitchNumber: string }
) {
  state.directVideoUrl = ''
  state.sportyVideoUrl = ''
  state.directVideoFailed = false
  state.loadingVideo = false
  state.hasSelection = Boolean(point)
  if (!point) {
    return
  }
  if (isDirectVideoUrl(fields.sourceUrl)) {
    state.directVideoUrl = fields.sourceUrl
    return
  }
  let resolvedPlayId = fields.playId
  if (fields.sourceUrl) {
    state.sportyVideoUrl = fields.sourceUrl
    resolvedPlayId ||= playIdFromSportyUrl(fields.sourceUrl)
  } else if (!resolvedPlayId && fields.gamePk && fields.atBatNumber && fields.pitchNumber) {
    state.loadingVideo = true
    try {
      const pitchMeta = await api.comparisonPitchVideo({
        gamePk: Number(fields.gamePk),
        atBatNumber: Number(fields.atBatNumber),
        pitchNumber: Number(fields.pitchNumber)
      })
      resolvedPlayId = cleanValue(pitchMeta.play_id)
      state.sportyVideoUrl = cleanValue(pitchMeta.video_url)
      state.directVideoUrl = cleanValue(pitchMeta.direct_video_url)
    } catch {
      resolvedPlayId = ''
    } finally {
      state.loadingVideo = false
    }
  }
  if (!state.sportyVideoUrl && resolvedPlayId) {
    state.sportyVideoUrl = `https://baseballsavant.mlb.com/sporty-videos?playId=${encodeURIComponent(resolvedPlayId)}`
  }
  if (!resolvedPlayId || state.directVideoUrl) {
    return
  }
  state.loadingVideo = true
  try {
    const meta = await api.comparisonDirectVideo(resolvedPlayId)
    state.directVideoUrl = cleanValue(meta.direct_video_url)
    state.sportyVideoUrl ||= cleanValue(meta.video_url)
  } catch {
    state.directVideoUrl = ''
  } finally {
    state.loadingVideo = false
  }
}

function cleanValue(value: unknown) {
  const text = String(value ?? '').trim()
  return text && text !== 'None' && text !== 'nan' && text !== 'NaN' ? text : ''
}

function isDirectVideoUrl(value: string) {
  return /^https?:\/\/.+\.(mp4|m3u8)(\?|$)/i.test(value)
}

function playIdFromSportyUrl(value: string) {
  try {
    const url = new URL(value)
    return cleanValue(url.searchParams.get('playId'))
  } catch {
    return ''
  }
}
</script>

<style scoped>
.period-module {
  display: grid;
  gap: 14px;
  margin-top: 18px;
}

.module-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
}

.module-header h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 18px;
}

.module-header p,
.module-header span {
  margin: 4px 0 0;
  color: var(--color-muted-text);
  font-size: 13px;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.video-slot {
  display: grid;
  gap: 8px;
}

.video-slot h3 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

.selected-video-panel {
  position: relative;
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #020617;
  box-shadow: var(--shadow-sm);
  aspect-ratio: 16 / 9;
}

.video-slot :deep(video),
.video-slot :deep(iframe) {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
  background: #020617;
}

.video-slot :deep(video) {
  object-fit: cover;
}

.video-slot :deep(.empty-state) {
  display: grid;
  height: 100%;
  min-height: 360px;
  place-content: center;
  gap: 8px;
  padding: 24px;
  text-align: center;
  color: var(--color-muted-text);
}

.video-slot :deep(.empty-state strong) {
  color: var(--color-foreground);
  font-size: 18px;
}

@media (max-width: 980px) {
  .video-grid {
    grid-template-columns: 1fr;
  }
}
</style>
