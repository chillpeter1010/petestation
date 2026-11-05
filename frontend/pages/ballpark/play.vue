<template>
  <main class="walk-shell">
    <header class="walk-header">
      <PetehubLogo size="compact" aria-label="Petehub Ballpark" />
      <span class="walk-version">BALLPARK WALK · E5 / E6 · SCENES V4</span>
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
      <BallparkRuntime v-if="sessionReady" ref="runtimeView" :key="`${room}:${arrivalId}`" :room="room" :arrival-id="arrivalId" :saved-position="world.save.value.rooms[room]" :allow-admin="isBackstageAdmin" :paused="Boolean(activeObject)" :fallback-route="classicFallback" @portal="handlePortal" @object="openObject($event.objectId,$event.path)" @state="onWorldState" @classic="rememberClassic" />
      <p v-else class="loading" role="status">Restoring Ballpark…</p>
      <template #fallback><p class="loading">Preparing walk preview…</p></template>
    </ClientOnly>

    <p v-if="world.notice.value" role="status">{{ world.notice.value }}</p>
    <nav class="direct-nav" aria-label="Direct facility links" @click.capture="rememberDirectClassic">
      <NuxtLink to="/games/today">Game</NuxtLink><NuxtLink to="/pitchers">Pitcher Mound</NuxtLink>
      <NuxtLink to="/batters">Batting Cages</NuxtLink><NuxtLink to="/leaderboards">Leaderboard</NuxtLink>
      <NuxtLink to="/lab">Training &amp; Lab</NuxtLink><NuxtLink :to="teamRoute">Team &amp; roster</NuxtLink>
      <button type="button" @click="openRecommendations">Recommended videos</button>
    </nav>

    <section class="object-directory" aria-label="Room objects and travel">
      <details open><summary>Room objects · same actions without walking</summary><div class="object-buttons"><button v-for="entry in directEntries" :key="entry.key" type="button" :data-object-id="entry.id" @click="openObject(entry.id,entry.path)">{{ entry.label }}</button></div></details>
      <details><summary>Mini-map / fast travel</summary>
        <svg class="mini-map" viewBox="0 0 1672 941" role="img" :aria-label="`${ROOM_LABELS[room]} mini-map; gold dots are objects, cyan is your position`">
          <rect width="1672" height="941" fill="#223529" />
          <polygon v-for="shape in sceneKit.scenes[room].collision" :key="shape.id" :points="shape.polygon.map(p=>p.join(',')).join(' ')" fill="#4e5860" />
          <circle v-for="object in directObjects" :key="object.id" :cx="object.approach[0]" :cy="object.approach[1]" r="14" fill="#ffc25b"><title>{{ object.label }}</title></circle>
          <circle v-if="worldState" :cx="worldState.x" :cy="worldState.y" r="20" fill="#70f6ef" stroke="#071f25" stroke-width="5" />
        </svg>
        <label>Fast travel<select :value="room" @change="travel(($event.target as HTMLSelectElement).value as BallparkRoom)"><option v-for="item in rooms" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
      </details>
    </section>
    <p v-if="route.query.object && !activeObject" role="status">This object is unavailable in this room or for this account. <button type="button" @click="closeObject">Return to walking</button></p>
    <ClientOnly><BallparkOverlay v-if="activeObject && !directObjectRoute(activeObject)" :title="activeObject.label" :origin="ROOM_LABELS[room]" :team="viewedTeam" @close="closeObject"><BallparkObjectPanel :key="activeObject.id" :object="activeObject" :team="viewedTeam" @classic="rememberClassic" @travel="travel" /></BallparkOverlay></ClientOnly>
  </main>
</template>

<script setup lang="ts">
import type { BallparkPortalTarget, BallparkRoom, BallparkRuntimeState } from '~/components/ballpark/runtime/createBallparkGame'
import { roomInteractions, ROOM_LABELS, createActivationGate, type Interaction } from '~/components/ballpark/runtime/interactionCatalog'
import { PANEL_QUERY_KEYS, baseWalkQuery } from '~/components/ballpark/runtime/bridgeContract'
import { objectClassicDestination } from '~/components/ballpark/runtime/classicDestinations'
import { positiveId } from '~/components/ballpark/runtime/interactionCatalog'
import { MLB_TEAMS, normalizeMlbTeamCode } from '~/config/mlbTeams'
import sceneKit from '~/assets/ballpark/scenes/scene-kit-v4.json'

const route = useRoute()
const router = useRouter()
const { user, isBackstageAdmin } = useAuth()
const rooms: { id: BallparkRoom; label: string }[] = [
  { id: 'campus', label: 'Campus' },
  { id: 'game-center', label: 'Game Center' },
  { id: 'batting-cages', label: 'Batting Cages' },
  { id: 'pitcher-mound', label: 'Pitcher Mound' },
  { id: 'clubhouse', label: 'Clubhouse' },
  { id: 'clubhouse-smoking-area', label: 'Smoking area' },
  { id: 'team-office', label: 'Team Office' },
  { id: 'training-lab', label: 'Training & Lab' },
  { id: 'video-game-room', label: 'Video / Game Room' }
]
const room = computed<BallparkRoom>(() => rooms.find(item => item.id === route.query.room)?.id || 'campus')
const runtimeView=ref<{focusInteraction:()=>void;snapshot:()=>BallparkRuntimeState|undefined}|null>(null)
const worldState=ref<BallparkRuntimeState|null>(null)
const world=useBallparkWorld()
const sessionReady=ref(false)
const availableObjects=computed(()=>roomInteractions(room.value,isBackstageAdmin.value))
const directObjects=computed(()=>availableObjects.value.filter(o=>!o.adminOnly))
const directEntries=computed(()=>directObjects.value.flatMap<{id:string;key:string;label:string;path?:string}>(o=>o.kind==='links'&&o.links.length>1?o.links.map((link,i)=>({id:o.id,key:`${o.id}:${i}`,label:link.label,path:link.path})):[{id:o.id,key:o.id,label:o.label+(o.kind==='unavailable'?' · unavailable':''),path:undefined}]))
const activeObject=computed(()=>availableObjects.value.find(o=>o.id===route.query.object))
const acceptActivation=createActivationGate()
const {remember}=useBallparkReturn()
const selections=ref<Record<string,Record<string,string>>>({})
function selectionKey(kind:string){return `${viewedTeam.value}:${['in-game','pitcher'].includes(kind)?'pitcher':kind}`}
watch(()=>[activeObject.value?.id,route.query.year,route.query.player,route.query.game,route.query.date,route.query.mode],()=>{
  if(!activeObject.value)return
  selections.value[selectionKey(activeObject.value.kind)]=Object.fromEntries(PANEL_QUERY_KEYS.filter(k=>k!=='object').flatMap(k=>typeof route.query[k]==='string'?[[k,route.query[k] as string]]:[]))
})
let opening=false
const arrivalId = ref(typeof route.query.spawn === 'string' ? route.query.spawn : undefined)
const viewedTeam = computed(() => normalizeMlbTeamCode(route.query.team) || normalizeMlbTeamCode(world.save.value.viewing_team) || normalizeMlbTeamCode(user.value?.favorite_team_code))
const teamRoute = computed(() => viewedTeam.value ? `/teams/${viewedTeam.value}` : '/teams')
const classicFallback = computed(() => {
  const activeRoom = room.value
  const target = sceneKit.scenes[activeRoom].fallback.classic_route
  return target === '/teams' ? teamRoute.value : target
})

function roomLink(id: BallparkRoom, spawn?: string) {
  return { path: '/ballpark/play', query: { room:id, ...(viewedTeam.value ? { team: viewedTeam.value } : {}), ...(spawn ? { spawn } : {}) } }
}
function saveState(state:BallparkRuntimeState){
  world.update(state.room,{x:state.x,y:state.y,facing:state.facing,objectId:state.room===room.value?activeObject.value?.id||state.nearbyObject||undefined:state.nearbyObject||undefined},viewedTeam.value)
}
function checkpoint(){const state=runtimeView.value?.snapshot();if(state)saveState(state);world.flush()}
let consumingArrival=false
function onWorldState(state:BallparkRuntimeState){
  if(state.room!==room.value)return
  worldState.value=state;saveState(state)
  // Arrival applies once. Removing it from the URL lets refresh restore the saved position.
  if(route.query.spawn && !consumingArrival){consumingArrival=true;void router.replace({query:{...route.query,spawn:undefined},state:{ballparkOverlay:window.history.state.ballparkOverlay}}).finally(()=>{consumingArrival=false})}
}
function rememberDirectClassic(event:MouseEvent){if((event.target as Element).closest('a[href]'))rememberClassic()}
watch(()=>room.value,()=>{checkpoint();arrivalId.value=typeof route.query.spawn==='string'?route.query.spawn:undefined;worldState.value=null},{flush:'sync'})
watch(()=>route.query.spawn,value=>{if(typeof value==='string')arrivalId.value=value},{flush:'sync'})
function saveWhenHidden(){if(document.hidden)checkpoint()}
let disposed=false
onMounted(async()=>{
  world.load()
  if(!route.query.room){await router.replace({query:{...route.query,room:world.save.value.last_room,team:normalizeMlbTeamCode(route.query.team)||world.save.value.viewing_team||undefined}})}
  if(disposed)return
  sessionReady.value=true
  window.addEventListener('pagehide',checkpoint)
  document.addEventListener('visibilitychange',saveWhenHidden)
})
onBeforeRouteLeave(()=>{checkpoint()})
onBeforeUnmount(()=>{disposed=true;checkpoint();window.removeEventListener('pagehide',checkpoint);document.removeEventListener('visibilitychange',saveWhenHidden)})
function baseQuery() {
  return baseWalkQuery(route.query)
}
async function openObject(id:string,path?:string) {
  if(opening || !availableObjects.value.some(o=>o.id===id) || !acceptActivation(performance.now()))return
  const target=availableObjects.value.find(o=>o.id===id)!
  if(target.adminOnly){if(isBackstageAdmin.value){rememberClassic();await navigateTo('/admin/updates')}return}
  opening=true
  try{
    const direct=directObjectRoute(target,path)
    if(direct){rememberClassic();return await navigateTo(direct)}
    await router.push({path:'/ballpark/play',query:{...baseQuery(),...selections.value[selectionKey(target.kind)],object:id},state:{ballparkOverlay:router.resolve({path:'/ballpark/play',query:baseQuery()}).fullPath}})
  }finally{opening=false}
}
function directObjectRoute(target:Interaction,path?:string){
  const requestedYear=Number(route.query.year||selections.value[selectionKey(target.kind)]?.year)
  const saved=selections.value[selectionKey(target.kind)]
  const destination=objectClassicDestination(target,{path,team:viewedTeam.value,year:[2026,2025,2024,2023,2022,2021].includes(requestedYear)?requestedYear:2026,player:positiveId(route.query.player||saved?.player),game:positiveId(route.query.game||saved?.game)})
  if(!destination)return null
  return {...destination,query:{...destination.query,ballpark_from:router.resolve({path:'/ballpark/play',query:baseQuery()}).fullPath}}
}
// Existing object deep links use the same direct destination, without flashing the old intermediary.
watch(activeObject,target=>{
  if(!import.meta.client||!target)return
  const direct=directObjectRoute(target)
  if(direct){rememberClassic();void navigateTo(direct,{replace:true})}
},{immediate:true,flush:'post'})
async function closeObject(){
  const base=router.resolve({path:'/ballpark/play',query:baseQuery()}).fullPath
  if(window.history.state.ballparkOverlay===base)router.back()
  else await router.replace({path:'/ballpark/play',query:baseQuery(),state:{ballparkOverlay:null}})
}
function rememberClassic(){
  checkpoint()
  remember(router.resolve({path:'/ballpark/play',query:baseQuery()}).fullPath,ROOM_LABELS[room.value])
}
function travel(id:BallparkRoom){if(rooms.some(r=>r.id===id))return navigateTo(roomLink(id))}
async function openRecommendations(){
  if(room.value!=='video-game-room')await navigateTo(roomLink('video-game-room'))
  await nextTick();await openObject('video-game-room/recommended-screen')
}
watch(()=>Boolean(activeObject.value),async(open,wasOpen)=>{if(wasOpen&&!open){await nextTick();runtimeView.value?.focusInteraction()}})
function selectTeam(event: Event) {
  const team = normalizeMlbTeamCode((event.target as HTMLSelectElement).value)
  return navigateTo({ path: '/ballpark/play', query: { ...route.query, team: team || undefined } })
}

function handlePortal(target: BallparkPortalTarget) {
  if (target.action === 'admin') { if (isBackstageAdmin.value) {rememberClassic();return navigateTo('/admin/updates')} return }
  if (target.room) return navigateTo(roomLink(target.room, target.spawn || 'default'))
  if (target.route === '/teams') return openObject(room.value==='team-office'?'team-office/coach-workspace':'clubhouse/player-list')
  if (target.route) {rememberClassic();return navigateTo(target.route)}
  if (target.action === 'video') return openRecommendations()
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
.object-directory{display:grid;grid-template-columns:2fr 1fr;gap:16px}.object-directory details{border:1px solid #465044;border-radius:9px;padding:14px}.object-directory summary{font-weight:800;cursor:pointer}.object-buttons{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.object-buttons button,.object-directory select{min-height:44px;padding:8px 12px;border:1px solid #6d705c;border-radius:6px;background:#19241c;color:#f6f0dd;font:inherit;cursor:pointer}.mini-map{width:100%;max-height:260px;margin:12px 0}.object-directory label{display:grid;gap:8px}@media(max-width:800px){.object-directory{grid-template-columns:1fr}}
@media (max-width: 1100px) { .walk-shell { width: 100%; } }
.loading { min-height: 400px; display: grid; place-items: center; }
</style>
