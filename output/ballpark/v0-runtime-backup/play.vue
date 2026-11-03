<template>
  <main class="walk-shell">
    <header class="walk-header">
      <PetehubLogo size="compact" aria-label="Petehub Ballpark" />
      <span class="walk-version">V0 WALK PREVIEW</span>
      <NuxtLink class="static-link" to="/ballpark">Static map</NuxtLink>
    </header>

    <nav class="room-nav" aria-label="Walk preview rooms">
      <NuxtLink v-for="item in rooms" :key="item.id" :to="{ path: '/ballpark/play', query: item.id === 'campus' ? {} : { room: item.id } }" :aria-current="room === item.id ? 'page' : undefined">
        {{ item.label }}
      </NuxtLink>
    </nav>

    <ClientOnly>
      <BallparkRuntime :key="room" :room="room" @portal="handlePortal" />
      <template #fallback><p class="loading">Preparing walk preview…</p></template>
    </ClientOnly>

    <div v-if="videoOpen" class="notice" role="dialog" aria-modal="true" aria-labelledby="video-title">
      <div>
        <h2 id="video-title">Video Room</h2>
        <p>The recommendation panel remains on the static Ballpark map in V0.</p>
        <NuxtLink to="/ballpark">Open static map</NuxtLink>
        <button type="button" @click="videoOpen = false">Continue walking</button>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import type { BallparkPortalTarget, BallparkRoom } from '~/components/ballpark/runtime/createBallparkGame'

const route = useRoute()
const rooms: { id: BallparkRoom; label: string }[] = [
  { id: 'campus', label: 'Campus' },
  { id: 'clubhouse', label: 'Clubhouse' },
  { id: 'team-office', label: 'Team Office' }
]
const room = computed<BallparkRoom>(() => route.query.room === 'clubhouse' || route.query.room === 'team-office' ? route.query.room : 'campus')
const videoOpen = ref(false)

function handlePortal(target: BallparkPortalTarget) {
  if (target.room) return navigateTo({ path: '/ballpark/play', query: target.room === 'campus' ? {} : { room: target.room } })
  if (target.route) return navigateTo(target.route)
  if (target.action === 'video') videoOpen.value = true
}
</script>

<style scoped>
:global(body) { background: #080a08; }
.walk-shell { max-width: 1500px; min-height: 100dvh; margin: auto; padding: 12px clamp(12px, 2vw, 28px) 32px; color: #f6f0dd; background: radial-gradient(circle at 50% 0, #273b22, #080a08 42rem); }
.walk-header { display: flex; align-items: center; gap: 14px; min-height: 56px; }
.walk-version { color: #f3a22c; font: 850 12px/1.2 Consolas, monospace; letter-spacing: .08em; }
.static-link { margin-left: auto; color: #f6f0dd; text-decoration: none; }
.room-nav { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.room-nav a, .static-link { border: 1px solid #465044; border-radius: 7px; padding: 9px 14px; background: #151a15; font-weight: 800; }
.room-nav a { color: #f6f0dd; text-decoration: none; }
.room-nav a[aria-current="page"] { color: #121923; background: #f3a22c; border-color: #f3a22c; }
.loading { min-height: 400px; display: grid; place-items: center; }
.notice { position: fixed; z-index: 50; inset: 0; display: grid; place-items: center; padding: 16px; background: rgb(0 0 0 / 70%); }
.notice > div { max-width: 440px; padding: 24px; border: 1px solid #bd7a2f; border-radius: 12px; background: #121923; }
.notice a, .notice button { display: inline-block; margin: 8px 8px 0 0; border: 1px solid #bd7a2f; border-radius: 6px; padding: 8px 12px; color: #f6f0dd; background: #1a2024; text-decoration: none; cursor: pointer; }
</style>
