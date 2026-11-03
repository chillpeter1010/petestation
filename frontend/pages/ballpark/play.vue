<template>
  <main class="walk-shell">
    <header class="walk-header">
      <PetehubLogo size="compact" aria-label="Petehub Ballpark" />
      <span class="walk-version">V0 WALK PREVIEW · D2 SCENES V3</span>
      <NuxtLink class="static-link" to="/ballpark">Static map</NuxtLink>
    </header>

    <nav class="room-nav" aria-label="Walk preview rooms">
      <NuxtLink v-for="item in rooms" :key="item.id" :to="roomLink(item.id)" :aria-current="room === item.id ? 'page' : undefined">
        {{ item.label }}
      </NuxtLink>
      <label class="team-selector">Viewing team
        <select :value="viewedTeam" aria-label="Viewing team" @change="selectTeam">
          <option value="">MLB</option>
          <option v-for="team in MLB_TEAMS" :key="team.id" :value="team.code">{{ team.code }} · {{ team.name }}</option>
        </select>
      </label>
    </nav>

    <ClientOnly>
      <BallparkRuntime :key="`${room}:${arrivalId}`" :room="room" :arrival-id="arrivalId" :allow-admin="isBackstageAdmin" :paused="videoOpen" :fallback-route="classicFallback" @portal="handlePortal" />
      <template #fallback><p class="loading">Preparing walk preview…</p></template>
    </ClientOnly>

    <nav class="direct-nav" aria-label="Direct facility links">
      <NuxtLink to="/games/today">Game</NuxtLink><NuxtLink to="/pitchers">Pitcher Mound</NuxtLink>
      <NuxtLink to="/batters">Batting Cages</NuxtLink><NuxtLink to="/leaderboards">Leaderboard</NuxtLink>
      <NuxtLink to="/lab">Training &amp; Lab</NuxtLink><NuxtLink :to="teamRoute">Team &amp; roster</NuxtLink>
      <button type="button" @click="videoOpen = true">Recommended videos</button>
    </nav>

    <div v-if="videoOpen" class="notice" role="dialog" aria-modal="true" aria-labelledby="video-title">
      <div>
        <h2 id="video-title">Video Room</h2>
        <p>Watch Petehub’s recommended videos on the homepage. Game Room activities are reserved for a later release.</p>
        <NuxtLink to="/">Open recommendations</NuxtLink>
        <button type="button" @click="videoOpen = false">Continue walking</button>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import type { BallparkPortalTarget, BallparkRoom } from '~/components/ballpark/runtime/createBallparkGame'
import { MLB_TEAMS, normalizeMlbTeamCode } from '~/config/mlbTeams'
import sceneKit from '~/assets/ballpark/scenes/scene-kit-v3.json'

const route = useRoute()
const { user, isBackstageAdmin } = useAuth()
const rooms: { id: BallparkRoom; label: string }[] = [
  { id: 'campus', label: 'Campus' },
  { id: 'clubhouse', label: 'Clubhouse' },
  { id: 'team-office', label: 'Team Office' },
  { id: 'training-lab', label: 'Training & Lab' },
  { id: 'video-game-room', label: 'Video / Game Room' }
]
const room = computed<BallparkRoom>(() => rooms.find(item => item.id === route.query.room)?.id || 'campus')
const videoOpen = ref(false)
const arrivalId = computed(() => typeof route.query.spawn === 'string' ? route.query.spawn : undefined)
const viewedTeam = computed(() => normalizeMlbTeamCode(route.query.team) || normalizeMlbTeamCode(user.value?.favorite_team_code))
const teamRoute = computed(() => viewedTeam.value ? `/teams/${viewedTeam.value}` : '/teams')
const classicFallback = computed(() => {
  const target = sceneKit.scenes[room.value].fallback.classic_route
  return target === '/teams' ? teamRoute.value : target
})

function roomLink(id: BallparkRoom, spawn?: string) {
  return { path: '/ballpark/play', query: { ...(id === 'campus' ? {} : { room: id }), ...(viewedTeam.value ? { team: viewedTeam.value } : {}), ...(spawn ? { spawn } : {}) } }
}
function selectTeam(event: Event) {
  const team = normalizeMlbTeamCode((event.target as HTMLSelectElement).value)
  return navigateTo({ path: '/ballpark/play', query: { ...route.query, team: team || undefined } })
}

function handlePortal(target: BallparkPortalTarget) {
  if (target.action === 'admin') { if (isBackstageAdmin.value) return navigateTo('/admin/updates'); return }
  if (target.room) return navigateTo(roomLink(target.room, target.spawn))
  if (target.route === '/teams') return navigateTo(teamRoute.value)
  if (target.route) return navigateTo(target.route)
  if (target.action === 'video') videoOpen.value = true
}
</script>

<style scoped>
:global(body) { background: #080a08; }
.walk-shell { width: min(2000px, 70vw); max-width: 100%; min-height: 100dvh; margin: auto; padding: 12px clamp(12px, 2vw, 28px) 32px; color: #f6f0dd; background: radial-gradient(circle at 50% 0, #273b22, #080a08 42rem); }
.walk-header { display: flex; align-items: center; gap: 14px; min-height: 56px; }
.walk-version { color: #f3a22c; font: 850 12px/1.2 Consolas, monospace; letter-spacing: .08em; }
.static-link { margin-left: auto; color: #f6f0dd; text-decoration: none; }
.room-nav { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.room-nav a, .static-link { border: 1px solid #465044; border-radius: 7px; padding: 9px 14px; background: #151a15; font-weight: 800; }
.room-nav a { color: #f6f0dd; text-decoration: none; }
.room-nav a[aria-current="page"] { color: #121923; background: #f3a22c; border-color: #f3a22c; }
.team-selector { margin-left: auto; display: flex; align-items: center; gap: 10px; font-weight: 800; }
.team-selector select { max-width: 230px; border: 1px solid #465044; border-radius: 7px; padding: 9px 12px; color: #f6f0dd; background: #151a15; font: inherit; }
.direct-nav { display: flex; flex-wrap: wrap; gap: 8px 20px; padding: 16px 2px; }
.direct-nav a, .direct-nav button { color: #e7c080; background: none; border: 0; font: inherit; text-decoration: underline; cursor: pointer; }
@media (max-width: 1100px) { .walk-shell { width: 100%; } }
.loading { min-height: 400px; display: grid; place-items: center; }
.notice { position: fixed; z-index: 50; inset: 0; display: grid; place-items: center; padding: 16px; background: rgb(0 0 0 / 70%); }
.notice > div { max-width: 440px; padding: 24px; border: 1px solid #bd7a2f; border-radius: 12px; background: #121923; }
.notice a, .notice button { display: inline-block; margin: 8px 8px 0 0; border: 1px solid #bd7a2f; border-radius: 6px; padding: 8px 12px; color: #f6f0dd; background: #1a2024; text-decoration: none; cursor: pointer; }
</style>
