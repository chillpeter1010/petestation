<template>
  <span
    class="mlb-headshot"
    :class="[`mlb-headshot--${shape}`, { 'mlb-headshot--fallback': !canLoadPhoto || failed }]"
    :style="{ '--headshot-size': `${size}px` }"
  >
    <img
      v-if="canLoadPhoto && !failed"
      :src="photoUrl"
      :alt="decorative ? '' : `${name || 'MLB player'} headshot`"
      :width="size"
      :height="size"
      :loading="priority ? 'eager' : 'lazy'"
      :fetchpriority="priority ? 'high' : 'auto'"
      decoding="async"
      @error="failed = true"
    >
    <span v-else aria-hidden="true">{{ initials }}</span>
  </span>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  playerId: number | null | undefined
  name: string
  size?: number
  sourceWidth?: 160 | 320 | 640
  priority?: boolean
  decorative?: boolean
  shape?: 'circle' | 'rounded'
}>(), {
  size: 48,
  sourceWidth: 160,
  priority: false,
  decorative: false,
  shape: 'rounded'
})

const failed = ref(false)
const numericPlayerId = computed(() => Number(props.playerId))
const canLoadPhoto = computed(() => Number.isInteger(numericPlayerId.value) && numericPlayerId.value > 0)
const photoUrl = computed(() => `https://img.mlbstatic.com/mlb-photos/image/upload/w_${props.sourceWidth},q_auto:best,f_auto/v1/people/${numericPlayerId.value}/headshot/silo/current`)
const initials = computed(() => {
  const parts = props.name.trim().split(/\s+/).filter(Boolean)
  return (parts.length ? parts.slice(-2).map(part => part[0]) : ['?']).join('').toUpperCase()
})

watch(() => props.playerId, () => { failed.value = false })
</script>

<style scoped>
.mlb-headshot { width: var(--headshot-size); height: var(--headshot-size); flex: 0 0 auto; display: grid; place-items: center; overflow: hidden; border: 1px solid color-mix(in srgb, currentColor 18%, transparent); color: var(--color-muted-text); background: color-mix(in srgb, var(--color-muted) 82%, #10141c); }
.mlb-headshot--circle { border-radius: 50%; }
.mlb-headshot--rounded { border-radius: min(22%, 14px); }
.mlb-headshot img { width: 100%; height: 100%; display: block; object-fit: contain; object-position: center bottom; }
.mlb-headshot--fallback > span { font: 900 max(10px, calc(var(--headshot-size) * .25)) "Fira Code", monospace; }
</style>
