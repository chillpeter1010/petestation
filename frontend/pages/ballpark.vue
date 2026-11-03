<template>
  <NuxtPage v-if="route.path.startsWith('/ballpark/play')" />
  <main v-else class="ballpark-shell">
    <header class="topbar">
      <div class="brand-block">
        <PetehubLogo size="compact" aria-label="Petehub Classic UI home" />
        <span class="version-label">{{ ballparkVersion }}</span>
      </div>
      <NuxtLink class="walk-open" to="/ballpark/play">Walk V0</NuxtLink>
      <button ref="avatarButton" class="avatar-open" type="button" @click="openAvatarCreator">Character</button>
    </header>

    <section class="scene" :aria-label="viewTitle">
      <div v-if="activeView === 'campus'" class="scene-art scene-art--campus">
        <div class="campus-toolbar">
        <div class="image-hud image-hud--home">{{ homeTeam || 'MLB' }} HOME CAMPUS</div>
        <nav class="image-nav" aria-label="Ballpark navigation">
          <button type="button" aria-current="page" @click="openView('campus')"><MapIcon /><span>Ballpark</span></button>
          <NuxtLink to="/games/today"><Gamepad2 /><span>Game</span></NuxtLink>
          <NuxtLink to="/pitchers"><Crosshair /><span>Pitcher Mound</span></NuxtLink>
          <NuxtLink to="/batters"><Dumbbell /><span>Batting Cages</span></NuxtLink>
          <button type="button" @click="openView('clubhouse')"><House /><span>Clubhouse</span></button>
          <button type="button" @click="openView('team-office')"><Briefcase /><span>Team Office</span></button>
          <NuxtLink to="/lab"><FlaskConical /><span>Training &amp; Lab</span></NuxtLink>
        </nav>
        <label class="image-hud image-team-picker">
          <span>Home team</span>
          <select v-model="homeTeam" aria-label="Home team" @change="persistHomeTeam">
            <option value="">Choose later</option>
            <option v-for="team in MLB_TEAMS" :key="team.code" :value="team.code">{{ team.code }} · {{ team.name }}</option>
          </select>
        </label>
        </div>
        <div class="campus-map">
        <img :src="mainCampusImage" alt="Pixel-art Petehub baseball campus with Game field, leaderboard, clubhouse, training lab, video room and team office">
        <NuxtLink class="hotspot hotspot--game" to="/games/today"><span><Gamepad2 />Game</span></NuxtLink>
        <NuxtLink class="hotspot hotspot--leaderboard" to="/leaderboards"><span><Trophy />Leaderboard</span></NuxtLink>
        <NuxtLink class="hotspot hotspot--pitcher" to="/pitchers"><span><Crosshair />Pitcher Mound</span></NuxtLink>
        <NuxtLink class="hotspot hotspot--batting" to="/batters"><span><Dumbbell />Batting Cages</span></NuxtLink>
        <button class="hotspot hotspot--clubhouse" type="button" @click="openView('clubhouse')"><span><House />Clubhouse</span></button>
        <button class="hotspot hotspot--office" type="button" @click="openView('team-office')"><span><Briefcase />Team Office</span></button>
        <NuxtLink class="hotspot hotspot--training" to="/lab"><span><FlaskConical />Training &amp; Lab</span></NuxtLink>
        <button class="hotspot hotspot--video" type="button" @click="videoPanelOpen = true"><span><MonitorPlay />Video Room</span></button>
        </div>
      </div>

      <div v-else class="scene-art scene-art--interior">
        <img
          :src="activeView === 'clubhouse' ? clubhouseImage : teamOfficeImage"
          :alt="activeView === 'clubhouse' ? `${viewedTeam || 'MLB'} pixel-art clubhouse with lockers, player lounge and roster menu` : `${viewedTeam || 'MLB'} pixel-art team office with coach and general manager rooms`"
        >
        <div class="interior-toolbar">
          <nav class="interior-nav" aria-label="Ballpark navigation">
            <button class="interior-nav__home" type="button" @click="openView('campus')"><MapIcon /><span>Ballpark</span></button>
            <NuxtLink to="/games/today"><Gamepad2 /><span>Game</span></NuxtLink>
            <NuxtLink to="/pitchers"><Crosshair /><span>Pitcher Mound</span></NuxtLink>
            <NuxtLink to="/batters"><Dumbbell /><span>Batting Cages</span></NuxtLink>
            <button type="button" :aria-current="activeView === 'clubhouse' ? 'page' : undefined" @click="openView('clubhouse')"><House /><span>Clubhouse</span></button>
            <button type="button" :aria-current="activeView === 'team-office' ? 'page' : undefined" @click="openView('team-office')"><Briefcase /><span>Team Office</span></button>
            <NuxtLink to="/lab"><FlaskConical /><span>Training &amp; Lab</span></NuxtLink>
          </nav>
          <label class="interior-team-picker"><span>Viewing team</span>
            <select :value="viewedTeam" :aria-label="`${viewTitle} team`" @change="selectViewedTeam">
            <option v-if="!viewedTeam" value="">Choose team</option>
            <option v-for="team in MLB_TEAMS" :key="team.id" :value="team.code">{{ team.code }} · {{ team.name }}</option>
            </select>
          </label>
        </div>
        <NuxtLink v-if="viewedTeam" class="hotspot hotspot--team-page" :to="`/teams/${viewedTeam}`"><span>Open {{ viewedTeam }} {{ activeView === 'clubhouse' ? 'roster' : 'team page' }}</span></NuxtLink>
        <button v-else class="hotspot hotspot--team-page" type="button" @click="bootstrapOpen = true"><span>Choose home team</span></button>
        <NuxtLink v-if="activeView === 'team-office' && isBackstageAdmin" class="hotspot hotspot--easter-egg" to="/admin/updates" aria-label="點擊 Per aspera ad astra 畫框進入後台" />
      </div>
    </section>

    <div v-if="bootstrapOpen" class="overlay" role="presentation">
      <section role="dialog" aria-modal="true" aria-labelledby="bootstrap-title" class="video-panel bootstrap-panel">
        <span class="panel-label">C1 · Ballpark profile</span>
        <h2 id="bootstrap-title">Choose your home team</h2>
        <p>Your team becomes the default context for the campus. You can customize your neutral Petehub character after entering.</p>
        <label for="bootstrap-team">Home team</label>
        <select id="bootstrap-team" v-model="homeTeam">
          <option value="">Choose later</option>
          <option v-for="team in MLB_TEAMS" :key="`bootstrap-${team.id}`" :value="team.code">{{ team.code }} · {{ team.name }}</option>
        </select>
        <p v-if="profileError" class="profile-error" role="alert">{{ profileError }}</p>
        <div class="panel-actions">
          <button class="primary-action" type="button" :disabled="profileSaving" @click="completeBootstrap(false)">
            {{ profileSaving ? 'Saving…' : 'Continue with default avatar' }}
          </button>
          <button type="button" :disabled="profileSaving" @click="completeBootstrap(true)">Skip for now</button>
        </div>
      </section>
    </div>

    <div v-if="avatarOpen" class="overlay" role="presentation" @click.self="closeAvatarCreator">
      <section ref="avatarPanel" class="video-panel avatar-panel" role="dialog" aria-modal="true" aria-labelledby="avatar-title" @keydown="handleAvatarKeydown">
        <span class="panel-label">D4 · Character creator</span>
        <h2 id="avatar-title">Your Ballpark character</h2>
        <p class="avatar-note">Preview all four directions and animations. Your saved appearance is used in the walking scene.</p>
        <p v-if="user?.avatar_recovery_needed" class="profile-error" role="alert">Your previous character data could not be read. The original is retained for recovery; a neutral preview is shown.</p>
        <div class="avatar-layout">
          <div class="avatar-preview">
            <BallparkCharacterPreview :avatar="avatarDraft" :favorite-team="user?.favorite_team_code" />
          </div>
          <div class="avatar-fields">
            <label>Skin tone<select ref="avatarFirstField" v-model="avatarDraft.body_id"><option v-for="tone in avatarTones" :key="tone" :value="tone">{{ tone.replace('_', ' ') }}</option></select></label>
            <label>Uniform<select v-model="avatarDraft.uniform_id"><option value="neutral_home">{{ user?.favorite_team_code || 'Petehub' }} home colors</option><option value="neutral_away">{{ user?.favorite_team_code || 'Petehub' }} away colors</option></select></label>
            <label>Accent<select v-model="avatarDraft.palette_id" :disabled="Boolean(user?.favorite_team_code)"><option v-if="user?.favorite_team_code" :value="avatarDraft.palette_id">{{ user.favorite_team_code }} team colors</option><template v-else><option value="orange">Orange</option><option value="teal">Teal</option><option value="slate">Slate</option></template></select></label>
            <label>Number<input type="number" min="0" max="99" :value="avatarDraft.number ?? ''" placeholder="None" @input="setAvatarNumber"></label>
            <label>Bats<select v-model="avatarDraft.bats"><option value="R">R</option><option value="L">L</option><option value="S">S</option></select></label>
            <label>Throws<select v-model="avatarDraft.throws"><option value="R">R</option><option value="L">L</option><option value="S">S</option></select></label>
          </div>
        </div>
        <p v-if="avatarError" class="profile-error" role="alert">{{ avatarError }}</p>
        <div class="panel-actions">
          <button type="button" :disabled="avatarSaving" @click="randomizeAvatar">Randomize</button>
          <button type="button" :disabled="avatarSaving || !avatarHistory.length" @click="undoAvatar">Undo</button>
          <button type="button" :disabled="avatarSaving" @click="resetAvatar">Reset</button>
          <button type="button" :disabled="avatarSaving" @click="closeAvatarCreator">Cancel</button>
          <button class="primary-action" type="button" :disabled="avatarSaving" @click="saveAvatar">{{ avatarSaving ? 'Saving…' : 'Save character' }}</button>
        </div>
      </section>
    </div>

    <div v-if="videoPanelOpen" class="overlay" role="presentation" @click.self="videoPanelOpen = false">
      <section role="dialog" aria-modal="true" aria-labelledby="video-title" class="video-panel">
        <span class="panel-label">Video Room · future Game Room</span>
        <h2 id="video-title">Petehub recommendations</h2>
        <p>現階段沿用 Petehub 主頁的推薦影片；小遊戲與 Game Room 會等核心球場流程穩定後再獨立開發。</p>
        <div class="panel-actions">
          <NuxtLink class="primary-action" to="/">Open recommendations</NuxtLink>
          <button type="button" @click="videoPanelOpen = false">Back to Ballpark</button>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { Briefcase, Crosshair, Dumbbell, FlaskConical, Gamepad2, House, Map as MapIcon, MonitorPlay, Trophy } from '@lucide/vue'
import mainCampusImage from '~/assets/ballpark/main-campus-v5.png'
import clubhouseImage from '~/assets/ballpark/clubhouse-v2.png'
import teamOfficeImage from '~/assets/ballpark/team-office-v4.png'
import { MLB_TEAMS, normalizeMlbTeamCode, teamIdForCode } from '~/config/mlbTeams'
import type { BallparkAvatarV1 } from '~/composables/useAuth'

type BallparkView = 'campus' | 'clubhouse' | 'team-office'

const route = useRoute()
const activeView = computed<BallparkView>(() => route.query.room === 'clubhouse' || route.query.room === 'team-office' ? route.query.room : 'campus')
const homeTeam = ref('')
const videoPanelOpen = ref(false)
const bootstrapOpen = ref(false)
const profileSaving = ref(false)
const profileError = ref('')
const avatarButton = ref<HTMLButtonElement | null>(null)
const avatarFirstField = ref<HTMLSelectElement | null>(null)
const avatarPanel = ref<HTMLElement | null>(null)
const avatarOpen = ref(false)
const avatarSaving = ref(false)
const avatarError = ref('')
const defaultAvatar: BallparkAvatarV1 = { avatar_version: 1, body_id: 'tone_2', uniform_id: 'neutral_home', palette_id: 'orange', number: null, bats: 'R', throws: 'R' }
const avatarTones: BallparkAvatarV1['body_id'][] = ['tone_1', 'tone_2', 'tone_3', 'tone_4']
const avatarDraft = ref<BallparkAvatarV1>({ ...defaultAvatar })
const avatarHistory = ref<BallparkAvatarV1[]>([])
const avatarRestoring = ref(false)
const ballparkVersion = 'v0.1.0-design-preview'
const auth = useAuth()
const user = auth.user
const viewedTeam = computed(() => normalizeMlbTeamCode(route.query.team) || homeTeam.value)

const isBackstageAdmin = auth.isBackstageAdmin
const viewTitle = computed(() => ({ campus: 'Petehub Ballpark', clubhouse: 'Clubhouse', 'team-office': 'Team Office' })[activeView.value])

watch(() => JSON.stringify(avatarDraft.value), (_current, previous) => {
  if (avatarOpen.value && previous && !avatarRestoring.value) avatarHistory.value.push(JSON.parse(previous) as BallparkAvatarV1)
})

async function openAvatarCreator() {
  avatarDraft.value = { ...(user.value?.avatar || defaultAvatar) }
  // Legacy unknown remains readable by the API; new UI choices are R/L/S only.
  if (avatarDraft.value.bats === 'unknown') avatarDraft.value.bats = 'R'
  if (avatarDraft.value.throws === 'unknown') avatarDraft.value.throws = 'R'
  avatarHistory.value = []
  avatarError.value = ''
  avatarOpen.value = true
  await nextTick()
  avatarFirstField.value?.focus()
}

function closeAvatarCreator() {
  if (avatarSaving.value) return
  avatarOpen.value = false
  nextTick(() => avatarButton.value?.focus())
}

function setAvatarNumber(event: Event) {
  const value = (event.target as HTMLInputElement).value
  avatarDraft.value.number = value === '' ? null : Number(value)
}

function randomizeAvatar() {
  const pick = <T,>(items: readonly T[]) => items[Math.floor(Math.random() * items.length)]!
  avatarDraft.value = { ...avatarDraft.value, body_id: pick(avatarTones), uniform_id: pick(['neutral_home', 'neutral_away'] as const), palette_id: pick(['orange', 'teal', 'slate'] as const), number: Math.floor(Math.random() * 100) }
}

function resetAvatar() {
  avatarDraft.value = { ...defaultAvatar }
}

async function undoAvatar() {
  const previous = avatarHistory.value.pop()
  if (!previous) return
  avatarRestoring.value = true
  avatarDraft.value = previous
  await nextTick()
  avatarRestoring.value = false
}

async function saveAvatar() {
  avatarError.value = ''
  if (avatarDraft.value.number !== null && (!Number.isInteger(avatarDraft.value.number) || avatarDraft.value.number < 0 || avatarDraft.value.number > 99)) {
    avatarError.value = 'Number must be between 0 and 99.'
    return
  }
  avatarSaving.value = true
  try {
    await auth.updateAvatar({ ...avatarDraft.value })
    avatarOpen.value = false
    await nextTick()
    avatarButton.value?.focus()
  } catch (error) {
    avatarError.value = error instanceof Error ? error.message : 'Unable to save your character.'
  } finally {
    avatarSaving.value = false
  }
}

function handleAvatarKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeAvatarCreator()
  }
  if (event.key !== 'Tab' || !avatarPanel.value) return
  const controls = [...avatarPanel.value.querySelectorAll<HTMLElement>('select, input, button:not(:disabled)')]
  if (!controls.length) return
  if (event.shiftKey && document.activeElement === controls[0]) {
    event.preventDefault()
    controls[controls.length - 1]?.focus()
  } else if (!event.shiftKey && document.activeElement === controls[controls.length - 1]) {
    event.preventDefault()
    controls[0]?.focus()
  }
}

function openView(view: BallparkView) {
  const team = normalizeMlbTeamCode(route.query.team)
  return navigateTo({ path: '/ballpark', query: view === 'campus' ? {} : { room: view, ...(team ? { team } : {}) } })
}

function selectViewedTeam(event: Event) {
  const team = normalizeMlbTeamCode((event.target as HTMLSelectElement).value)
  return navigateTo({ path: '/ballpark', query: { room: activeView.value, ...(team ? { team } : {}) } })
}

async function persistHomeTeam() {
  profileError.value = ''
  try {
    await auth.updateProfile({
      favorite_team_id: teamIdForCode(homeTeam.value),
      avatar_setup_status: user.value?.avatar_setup_status || 'pending'
    })
  } catch (error) {
    homeTeam.value = normalizeMlbTeamCode(user.value?.favorite_team_code)
    profileError.value = error instanceof Error ? error.message : 'Unable to save your home team.'
  }
}

async function completeBootstrap(skipTeam = false) {
  profileError.value = ''
  profileSaving.value = true
  try {
    if (skipTeam) homeTeam.value = ''
    await auth.updateProfile({
      favorite_team_id: teamIdForCode(homeTeam.value),
      avatar_setup_status: 'default'
    })
    bootstrapOpen.value = false
  } catch (error) {
    profileError.value = error instanceof Error ? error.message : 'Unable to save your Ballpark profile.'
  } finally {
    profileSaving.value = false
  }
}

function handleEscape(event: KeyboardEvent) {
  if (event.key === 'Escape') videoPanelOpen.value = false
}

watch(() => user.value?.favorite_team_code, code => {
  homeTeam.value = normalizeMlbTeamCode(code)
}, { immediate: true })

onMounted(() => {
  bootstrapOpen.value = user.value?.avatar_setup_status !== 'default'
  window.addEventListener('keydown', handleEscape)
})

onBeforeUnmount(() => window.removeEventListener('keydown', handleEscape))

useHead({
  title: 'Petehub Ballpark · Pixel RPG Prototype',
  meta: [{ name: 'description', content: 'Interactive pixel RPG baseball campus prototype for Petehub.' }]
})
</script>

<style scoped>
:global(body) { background: #080a08; }
.ballpark-shell { --orange: #f3a22c; min-height: 100dvh; color: #f6f0dd; background: radial-gradient(circle at 50% 0, #273b22, #080a08 42rem); }
.topbar, .scene { max-width: 1500px; margin-inline: auto; }
.topbar { min-height: 68px; display: flex; align-items: center; gap: 20px; padding: 12px clamp(14px, 2vw, 28px); }
.brand-block { display: flex; align-items: center; gap: 13px; }
.avatar-open { margin-left: auto; border: 1px solid #bd7a2f; border-radius: 7px; padding: 9px 14px; color: #f7ebd6; background: #1a2024; font: 850 12px/1.2 Consolas, monospace; letter-spacing: .04em; cursor: pointer; }
.walk-open { margin-left: auto; border: 1px solid #bd7a2f; border-radius: 7px; padding: 9px 14px; color: #121923; background: #f3a22c; font: 850 12px/1.2 Consolas, monospace; letter-spacing: .04em; text-decoration: none; }
.walk-open + .avatar-open { margin-left: 0; }
.avatar-open:hover { background: #27313a; }
.version-label, .panel-label { color: #ff9900; font: 850 11px/1.2 Consolas, monospace; letter-spacing: .09em; text-transform: uppercase; }
.panel-actions a, .panel-actions button { border: 1px solid #465044; border-radius: 7px; padding: 9px 12px; color: #f6f0dd; background: #151a15; font: inherit; font-weight: 800; text-decoration: none; }
.scene { padding: 0 clamp(0px, 2vw, 28px) 28px; }
.scene-art { position: relative; overflow: hidden; border: 1px solid #394237; border-radius: 12px; background: #111; box-shadow: 0 24px 80px rgb(0 0 0 / 45%); }
.scene-art img { display: block; width: 100%; height: auto; }
.campus-toolbar { display: flex; height: clamp(48px, 4vw, 68px); }
.campus-map { position: relative; }
.image-hud, .image-nav { z-index: 5; height: 100%; background: #121923; }
.image-hud--home { left: 0; width: 19%; display: flex; align-items: center; padding-left: 2.2%; color: var(--orange); font-size: clamp(8px, .95vw, 15px); font-weight: 950; letter-spacing: .08em; }
.image-nav { left: 19%; width: 59%; display: flex; align-items: stretch; overflow: hidden; border-inline: 1px solid #3b4552; background: linear-gradient(180deg, #1a2230, #111721); box-shadow: inset 0 -2px #35404d; }
.image-team-picker { right: 0; width: 22%; display: flex; align-items: center; justify-content: center; gap: clamp(5px, .7vw, 10px); border-left: 1px solid #3b4552; padding-inline: 1%; color: #d8d6cb; font-family: "Aptos", "Segoe UI", sans-serif; font-size: clamp(8px, .8vw, 13px); font-weight: 850; }
.image-team-picker select { min-width: 0; width: min(185px, 68%); border: 1px solid #465363; border-radius: 6px; padding: clamp(3px, .45vw, 7px) 8px; color: #f6f0dd; background: #0d1219; font: inherit; font-weight: 850; }
.image-nav a, .image-nav button, .interior-nav a, .interior-nav button { min-width: 0; flex: 1 1 0; display: flex; align-items: center; justify-content: center; gap: clamp(3px, .4vw, 7px); border: 0; border-right: 1px solid #3b4552; border-radius: 0; padding: 0 6px; color: #f6f0dd; background: transparent; font-family: "Aptos", "Segoe UI", sans-serif; font-size: clamp(9px, .9vw, 15px); font-weight: 850; line-height: 1; text-align: center; text-decoration: none; text-shadow: 0 1px 2px #000; cursor: pointer; }
.image-nav svg, .interior-nav svg { flex: 0 0 auto; width: clamp(13px, 1.1vw, 18px); height: clamp(13px, 1.1vw, 18px); stroke-width: 2.4; }
.image-nav a:last-child { border-right: 0; }
.image-nav [aria-current="page"] { color: #171109; background: linear-gradient(180deg, #f5b348, #dc9026); box-shadow: inset 0 -3px #a85d13; text-shadow: none; }
.image-nav a:hover, .image-nav button:hover, .image-nav a:focus-visible, .image-nav button:focus-visible, .interior-nav a:hover, .interior-nav button:hover, .interior-nav a:focus-visible, .interior-nav button:focus-visible { color: #fff2d7; background: #293342; box-shadow: inset 0 -3px var(--orange); outline: none; }
.interior-toolbar { position: absolute; z-index: 8; top: 0; left: 0; right: 0; height: 6.7%; min-height: 56px; display: flex; border-bottom: 2px solid #b37a2b; background: #121923; box-shadow: 0 4px 14px rgb(0 0 0 / 35%); }
.interior-nav { min-width: 0; flex: 1 1 auto; display: flex; align-items: stretch; overflow-x: auto; background: linear-gradient(180deg, #1a2230, #111721); scrollbar-width: thin; }
.interior-nav a, .interior-nav button { min-width: 100px; }
.interior-nav .interior-nav__home { position: sticky; z-index: 1; left: 0; flex: 0 0 124px; color: #171109; background: linear-gradient(180deg, #f5b348, #dc9026); text-shadow: none; }
.interior-nav [aria-current="page"] { color: #ffbf5c; box-shadow: inset 0 -3px var(--orange); }
.interior-team-picker { flex: 0 0 260px; min-width: 0; display: flex; align-items: center; justify-content: center; gap: 8px; border-left: 1px solid #3b4552; padding: 0 10px; color: #f6f0dd; background: #121923; font-family: "Aptos", "Segoe UI", sans-serif; font-size: 12px; font-weight: 850; white-space: nowrap; }
.interior-team-picker select { min-width: 0; width: 150px; border: 1px solid #596354; border-radius: 5px; padding: 7px 6px; color: #f6f0dd; background: #111923; font: inherit; }
.hotspot { position: absolute; display: grid; place-items: center; border: 2px solid transparent; border-radius: 8px; color: transparent; background: transparent; cursor: pointer; text-decoration: none; }
.hotspot span { display: flex; align-items: center; gap: 6px; border: 1px solid var(--orange); border-radius: 5px; padding: 7px 10px; color: #fff; background: rgb(8 10 8 / 92%); box-shadow: 0 4px 18px #000; font-family: "Aptos", "Segoe UI", sans-serif; font-size: clamp(10px, .8vw, 13px); font-weight: 850; letter-spacing: .035em; line-height: 1; text-transform: uppercase; opacity: 0; transform: translateY(5px); transition: opacity .15s ease, transform .15s ease; white-space: nowrap; }
.hotspot span svg { width: 15px; height: 15px; stroke: var(--orange); stroke-width: 2.5; }
.hotspot:hover, .hotspot:focus-visible { border-color: var(--orange); background: rgb(243 162 44 / 13%); outline: none; }
.hotspot:hover span, .hotspot:focus-visible span { opacity: 1; transform: none; }
.hotspot--game { top: 23%; left: 32%; width: 37%; height: 31%; }
.hotspot--leaderboard { top: 7%; left: 34%; width: 33%; height: 11%; }
.hotspot--pitcher { top: 8%; right: 2%; width: 18%; height: 29%; }
.hotspot--batting { top: 8%; left: 2%; width: 27%; height: 34%; }
.hotspot--clubhouse { bottom: 5%; left: 3%; width: 28%; height: 25%; }
.hotspot--office { right: 3%; bottom: 5%; width: 28%; height: 25%; }
.hotspot--training { top: 40%; left: 2%; width: 27%; height: 24%; }
.hotspot--video { top: 37%; right: 2%; width: 26%; height: 25%; }
.hotspot--team-page { right: 2%; bottom: 4%; width: 25%; height: 18%; }
.hotspot--easter-egg { top: 16.2%; left: 46.8%; width: 6.7%; height: 5.8%; }
.hotspot--easter-egg:hover, .hotspot--easter-egg:focus-visible { border-color: transparent; background: transparent; }
.hotspot--easter-egg:focus-visible { outline: 3px solid #ffd166; outline-offset: 2px; }
.overlay { position: fixed; z-index: 50; inset: 0; display: grid; place-items: center; padding: 18px; background: rgb(0 0 0 / 76%); backdrop-filter: blur(4px); }
.video-panel { width: min(590px, 100%); border: 1px solid #596354; border-radius: 12px; padding: 25px; background: #111611; box-shadow: 0 30px 90px #000; }
.video-panel h2 { margin: 7px 0 10px; font-size: 28px; }
.video-panel p { color: #c2c1b6; line-height: 1.65; }
.bootstrap-panel label { display: grid; gap: 7px; margin-top: 18px; color: #f6f0dd; font-size: 12px; font-weight: 850; }
.bootstrap-panel select { width: 100%; height: 46px; border: 1px solid #596354; border-radius: 7px; padding: 0 12px; color: #f6f0dd; background: #0b0f0b; }
.bootstrap-panel .profile-error { margin: 10px 0 0; color: #f4a4a0; font-size: 12px; }
.avatar-panel { width: min(780px, 100%); max-height: min(92dvh, 850px); overflow-y: auto; }
.avatar-panel h2 { margin-bottom: 4px; }
.avatar-note { margin-top: 0; font-size: 13px; }
.avatar-layout { display: grid; grid-template-columns: minmax(180px, .8fr) minmax(260px, 1.2fr); gap: 18px; margin-top: 18px; }
.avatar-preview { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 15px; min-height: 265px; border: 1px solid #465363; border-radius: 8px; background: repeating-linear-gradient(0deg, #1b2830 0 16px, #203238 16px 32px); }
.avatar-preview svg { width: 128px; height: 192px; filter: drop-shadow(0 9px 0 #0a1119); }
.avatar-preview span { color: #d5cfbf; font: 850 10px/1.2 Consolas, monospace; letter-spacing: .03em; }
.avatar-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-content: start; gap: 12px; }
.avatar-fields label { display: grid; gap: 6px; color: #e9dcc8; font-size: 12px; font-weight: 800; }
.avatar-fields select, .avatar-fields input { min-width: 0; width: 100%; height: 42px; border: 1px solid #596354; border-radius: 6px; padding: 0 9px; color: #f6f0dd; background: #101820; font: inherit; }
.panel-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 20px; }
.panel-actions .primary-action { border-color: var(--orange); color: #151009; background: var(--orange); }
.panel-actions button { cursor: pointer; }
.panel-actions button:disabled { cursor: wait; opacity: .62; }
button:focus-visible, a:focus-visible, select:focus-visible { outline: 3px solid #ffe08a; outline-offset: 2px; }
@media (max-width: 760px) {
  .topbar { align-items: flex-start; }
  .version-label { font-size: 9px; }
  .image-hud--home { width: 27%; }
  .image-nav { width: 53%; overflow-x: auto; }
  .image-nav a, .image-nav button { min-width: 86px; flex: 0 0 86px; font-size: 9px; }
  .image-team-picker { width: 20%; padding-inline: 3px; }
  .image-team-picker span { display: none; }
  .image-team-picker select { width: 100%; padding-inline: 3px; font-size: 7px; }
  .interior-nav a, .interior-nav button { min-width: 86px; flex: 0 0 86px; font-size: 9px; }
  .interior-nav .interior-nav__home { flex-basis: 92px; }
  .interior-team-picker { flex: 0 0 138px; flex-direction: column; gap: 2px; padding: 3px 5px; font-size: 9px; }
  .interior-team-picker select { width: 100%; padding: 3px; font-size: 9px; }
  .hotspot span { display: none; }
  .avatar-layout { grid-template-columns: 1fr; }
  .avatar-preview { min-height: 220px; }
  .avatar-preview svg { width: 96px; height: 144px; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; } }
</style>
