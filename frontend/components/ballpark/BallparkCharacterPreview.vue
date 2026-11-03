<template>
  <section class="character-study" :aria-label="sample ? 'Gabriel Moreno player sample' : 'Your character preview'">
    <svg :viewBox="`0 0 ${size[0]} ${size[1]}`" role="img" :aria-label="`${sample ? 'Gabriel Moreno' : 'Your character'}, ${facing}, ${action}`" class="character-study__sprite">
      <defs>
        <filter v-for="(color, material) in colors" :id="`${previewId}-${material}`" :key="material" color-interpolation-filters="sRGB">
          <feColorMatrix type="matrix" :values="colorMatrix(color)" />
        </filter>
      </defs>
      <image v-for="layer in images" :key="layer.name" :href="layer.url" :x="-(frame % 6) * size[0]" :y="-Math.floor(frame / 6) * size[1]" :width="size[0] * 6" :height="size[1] * 8" :filter="layer.name in colors ? `url(#${previewId}-${layer.name})` : undefined" @error="failedArtwork = Math.min(2, failedArtwork + 1)" />
      <rect v-if="failedArtwork === 2" x="30" y="20" width="36" height="118" rx="9" fill="#53677d" />
      <svg v-if="!sample && !failedArtwork && avatar.number !== null && numberPosition" :x="numberPosition[0]! - 6" :y="numberPosition[1]! - 5" width="12" height="10" :viewBox="`${avatar.number % 10 * 12} ${Math.floor(avatar.number / 10) * 10} 12 10`">
        <image :href="numbersUrl" width="120" height="100" />
      </svg>
    </svg>
    <p>{{ sample ? 'V2 · Gabriel Moreno · player sample' : 'V3 · modular User' }}</p>
    <small v-if="failedArtwork" role="status">Artwork unavailable: {{ failedArtwork === 1 ? 'neutral fallback' : 'temporary silhouette' }}. Your appearance is retained.</small>
    <div class="character-study__options" aria-label="Preview facing">
      <button v-for="direction in directions" :key="direction" type="button" :aria-pressed="facing === direction" @click="facing = direction; tick = 0">{{ direction }}</button>
    </div>
    <div class="character-study__options" aria-label="Preview animation">
      <button type="button" :aria-pressed="action === 'idle'" @click="action = 'idle'; tick = 0">Idle</button>
      <button type="button" :aria-pressed="action === 'walk'" @click="action = 'walk'; tick = 0">Walk</button>
      <button type="button" :aria-pressed="playing" @click="playing = !playing">{{ playing ? 'Pause' : 'Play' }}</button>
    </div>
    <small v-if="reducedMotion">Reduced motion: static poses.</small>
  </section>
</template>

<script setup lang="ts">
import type { BallparkAvatarV1 } from '~/composables/useAuth'
import { ballparkCharacterColors } from '~/config/ballparkUniform'
import kit from '~/assets/ballpark/characters/character-kit-v1.json'
import detailUrl from '~/assets/ballpark/characters/user-detail-v1.png'
import skinUrl from '~/assets/ballpark/characters/user-skin-v1.png'
import uniformUrl from '~/assets/ballpark/characters/user-uniform-v1.png'
import accentUrl from '~/assets/ballpark/characters/user-accent-v1.png'
import playerUrl from '~/assets/ballpark/characters/player-preview-v1.png'
import numbersUrl from '~/assets/ballpark/characters/numbers-v1.png'
import neutralUrl from '~/assets/ballpark/characters/user-preview-v1.png'

const props = defineProps<{ avatar: BallparkAvatarV1; sample?: boolean; favoriteTeam?: string | null }>()
const previewId = useId().replace(/[^a-zA-Z0-9_-]/g, '')
const directions = ['north', 'east', 'south', 'west'] as const
const facing = ref<(typeof directions)[number]>('south')
const action = ref<'idle' | 'walk'>('idle')
const tick = ref(0), playing = ref(true), reducedMotion = ref(false)
const failedArtwork = ref(0)
watch(() => props.sample, () => { failedArtwork.value = 0 })
const role = computed(() => props.sample && !failedArtwork.value ? kit.roles.player : kit.roles.user)
const size = computed(() => role.value.frame_size as [number, number])
const frame = computed(() => directions.indexOf(facing.value) * 12 + (action.value === 'walk' ? 4 : 0) + (reducedMotion.value ? 0 : tick.value % kit.clips[action.value].frames))
const numberPosition = computed(() => kit.roles.user.number_positions[frame.value])
const images = computed(() => failedArtwork.value === 2 ? [] : failedArtwork.value === 1 ? [{ name: 'neutral', url: neutralUrl }] : props.sample ? [{ name: 'player', url: playerUrl }] : [{ name: 'detail', url: detailUrl }, { name: 'skin', url: skinUrl }, { name: 'uniform', url: uniformUrl }, { name: 'accent', url: accentUrl }])
const colors = computed<Record<string, string>>(() => ballparkCharacterColors(props.avatar, props.favoriteTeam))
function colorMatrix(hex: string) {
  const [r, g, b] = [1, 3, 5].map(i => Number.parseInt(hex.slice(i, i + 2), 16) / 255)
  return `${r} 0 0 0 0 0 ${g} 0 0 0 0 0 ${b} 0 0 0 0 0 1 0`
}
let timer: ReturnType<typeof setInterval> | undefined
let media: MediaQueryList | undefined
let accumulated = 0
function preference() { reducedMotion.value = Boolean(media?.matches) }
onMounted(() => {
  media = window.matchMedia('(prefers-reduced-motion: reduce)')
  preference(); media.addEventListener('change', preference)
  timer = setInterval(() => {
    if (!playing.value || reducedMotion.value || document.hidden) return
    accumulated += 50
    const duration = 1000 / kit.clips[action.value].fps
    if (accumulated >= duration) { tick.value += 1; accumulated %= duration }
  }, 50)
})
onBeforeUnmount(() => { clearInterval(timer); media?.removeEventListener('change', preference) })
</script>

<style scoped>
.character-study { display: grid; justify-items: center; gap: 10px; padding: 14px; color: #f3efe3; background: #17232b; border: 1px solid #465363; border-radius: 8px; }
.character-study__sprite { width: 144px; height: 216px; overflow: hidden; image-rendering: pixelated; }
.character-study p { margin: 0; font: 700 11px/1.5 Consolas, monospace; text-align: center; }
.character-study__options { display: flex; flex-wrap: wrap; justify-content: center; gap: 5px; }
.character-study button { min-height: 34px; padding: 5px 8px; border: 1px solid #65717a; border-radius: 5px; background: #111923; color: #f3efe3; font: 700 11px/1.2 Consolas, monospace; cursor: pointer; }
.character-study button[aria-pressed="true"] { color: #111923; background: #f3a22c; }
.character-study button:focus-visible { outline: 3px solid #ffd166; outline-offset: 2px; }
</style>
