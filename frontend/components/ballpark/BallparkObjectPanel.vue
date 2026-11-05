<template>
  <div class="object-panel">
    <p v-if="object.message">{{ object.message }}</p>
    <div v-if="!['dialogue','unavailable'].includes(object.kind)" class="toolbar">
      <label>Season<select :value="year" @change="setYear(Number(($event.target as HTMLSelectElement).value))"><option v-for="value in years" :key="value" :value="value">{{ value }}</option></select></label>
      <span>{{ team || 'MLB' }} · {{ object.id }}</span>
    </div>

    <template v-if="object.kind==='dialogue'">
      <p><strong>{{ object.label }}</strong> · fictional guide</p>
      <p>{{ dialogue }}</p>
      <div class="actions"><button type="button" @click="answer='features'">What can I do here?</button><button type="button" @click="answer='players'">About the players</button><button type="button" @click="answer='travel'">Travel directions</button></div>
      <p v-if="answer==='features'">Use the room’s object menu or walk to an interaction marker and press E / Enter. R works near room exits; C opens the Clubhouse courtyard door.</p>
      <p v-if="answer==='players'">I am a generic guide, not an official player. Real team NPCs, personal stories and activity animations are planned for F4 and later motion work.</p>
      <p v-if="answer==='travel'">Choose a destination below; the viewing team stays selected.</p>
      <nav class="actions" aria-label="Dialogue fast travel"><button v-for="(label,id) in ROOM_LABELS" :key="id" type="button" @click="emit('travel', id)">{{ label }}</button></nav>
    </template>

    <LazyBallparkGamePanel v-else-if="object.kind==='games'" :year="year" :team="team" :initial-mode="object.id.endsWith('replay-screen')?'replay':undefined" @pitch="openPitch" />

    <template v-else-if="['roster','pitcher','batter','in-game'].includes(object.kind)">
      <label>Search players<input v-model="search" type="search" placeholder="Player name"></label>
      <p v-if="loading" role="status">Loading player directory…</p>
      <p v-if="error" role="alert">{{ error }} <button type="button" @click="loadPlayers">Retry</button></p>
      <p v-if="roster">Official active roster: <strong>{{ roster.freshness }}</strong> · retrieved {{ roster.retrieved_at || 'unavailable' }}<span v-if="roster.source_as_of"> · source {{ roster.source_as_of }}</span></p>
      <p v-if="!loading && !error && !players.length">No players available for this selection. No season-participant roster is substituted.</p>
      <label v-if="players.length">Player<select :value="selectedId || ''" @change="selectPlayer(Number(($event.target as HTMLSelectElement).value))"><option value="">Select player</option><option v-for="p in filteredPlayers" :key="p.id" :value="p.id">{{ p.name }} · {{ p.role }}</option></select></label>
      <div v-if="object.kind==='roster'" class="players"><button v-for="p in filteredPlayers" :key="p.id" type="button" @click="selectPlayer(p.id)">{{ p.name }} · {{ p.role }}</button></div>
      <template v-if="selectedPlayer && !loading && !error">
        <p>{{ selectedPlayer.name }} · {{ selectedPlayer.role }}</p>
        <LazyPitcherInGameTab v-if="object.kind==='in-game'" :key="`${year}:${team}:${selectedId}`" :year="year" :pitcher-id="selectedPlayer.id" :pitcher-name="selectedPlayer.name" :initial-game-pk="initialGame" @select-pitch="openPitch" @select-game="selectOuting" />
        <NuxtLink v-else :to="personalLink" @click="emit('classic')">Open {{ selectedPlayer.name }} in Classic UI</NuxtLink>
      </template>
    </template>

    <template v-else-if="object.kind==='videos'">
      <p v-if="loading" role="status">Loading recommendations…</p><p v-if="error" role="alert">{{ error }} <button type="button" @click="loadVideos">Retry</button></p>
      <p v-if="!loading && !error && !videos.length">No recommended videos are available.</p>
      <div class="players"><button v-for="video in videos" :key="video.play_id" type="button" @click="videoUrl=safeVideo(video.video_url); videoLabel=`${video.game_date} · ${video.batter_name} vs ${video.pitcher_name}`">{{ video.game_date }} · {{ video.away_team }} @ {{ video.home_team }} · {{ video.batter_name }} / {{ video.pitcher_name }}</button></div>
    </template>

    <p v-if="object.kind==='links'">Choose an existing Classic tool below. Full in-room business panels are delivered in Section F.</p>
    <nav class="actions" aria-label="Classic equivalents"><NuxtLink v-for="item in object.links" :key="item.path" :to="classicLink(item.path)" @click="emit('classic')">{{ item.label }} ↗</NuxtLink></nav>
    <section v-if="videoUrl" class="pitch-video" aria-label="Selected pitch video">
      <header><strong>{{ videoLabel }}</strong><button type="button" @click="videoUrl=''">Close video</button></header>
      <iframe :src="videoUrl" title="Selected game / pitch video" allowfullscreen />
    </section>
  </div>
</template>

<script setup lang="ts">
import type { HomeVideoRecommendation } from '~/types/api'
import { inGamePitchVideoUrl } from '~/utils/pitcherInGame'
import { ROOM_LABELS, positiveId, type Interaction, type Room } from './runtime/interactionCatalog'
type Player={id:number;name:string;role:string;pitcher:boolean}
type Roster={freshness:'fresh'|'stale'|'unavailable';retrieved_at:string|null;source_as_of:string|null;players:{player_id:number;name:string;position_type:string|null;position_name:string|null}[]}
const props=defineProps<{object:Interaction;team:string}>()
const emit=defineEmits<{classic:[];travel:[room:Room]}>()
const api=useApi(),route=useRoute(),router=useRouter(),config=useRuntimeConfig()
const years=[2026,2025,2024,2023,2022,2021]
const year=computed(()=>years.includes(Number(route.query.year))?Number(route.query.year):2026)
const selectedId=computed(()=>positiveId(route.query.player)),initialGame=computed(()=>positiveId(route.query.game))
const players=ref<Player[]>([]),roster=ref<Roster|null>(null),search=ref(''),loading=ref(false),error=ref('')
const videos=ref<HomeVideoRecommendation[]>([]),videoUrl=ref(''),videoLabel=ref(''),answer=ref('')
const selectedPlayer=computed(()=>players.value.find(p=>p.id===selectedId.value))
const filteredPlayers=computed(()=>players.value.filter(p=>p.id===selectedId.value || p.name.toLocaleLowerCase().includes(search.value.toLocaleLowerCase())))
const personalLink=computed(()=>({path:selectedPlayer.value?.pitcher?'/pitcher-personal':'/batter-personal',query:{year:year.value,team:props.team||undefined,...(selectedPlayer.value?.pitcher?{pitcher_id:selectedId.value,role:['SP','RP'].includes(selectedPlayer.value.role)?selectedPlayer.value.role:undefined,tab:'movement'}:{batter_id:selectedId.value})}}))
const dialogue=computed(()=>props.object.room==='clubhouse-smoking-area'?'Welcome to the courtyard. This is a quiet chat area; real player appearances and smoking animations are reserved for later.':`Welcome to ${ROOM_LABELS[props.object.room]}. I can explain this room or help you travel.`)
let request=0
function query(values:Record<string,string|number|undefined>){return router.replace({query:{...route.query,...values},state:{ballparkOverlay:window.history.state.ballparkOverlay}})}
function setYear(value:number){void query({year:value,player:undefined,game:undefined,date:undefined})}
function selectPlayer(id:number){videoUrl.value='';void query({player:id||undefined,game:undefined})}
function selectOuting(id:number){void query({game:id})}
function classicLink(path:string){
  if(path==='/pitcher-personal' && selectedPlayer.value)return {...personalLink.value,query:{...personalLink.value.query,tab:props.object.kind==='in-game'?'in-game':'movement',game_pk:initialGame.value}}
  return {path:path==='/teams'?(props.team?`/teams/${props.team}`:'/teams'):path,query:path==='/'||path==='/admin/updates'?{}:{year:year.value,team:props.team||undefined}}
}
function safeVideo(value:string){try{const url=new URL(value);return url.protocol==='https:' && (url.hostname==='baseballsavant.mlb.com'||url.hostname.endsWith('.mlb.com'))?url.href:''}catch{return ''}}
function openPitch(row:Record<string,unknown>){videoUrl.value=safeVideo(inGamePitchVideoUrl(row));videoLabel.value=`${row.pitch_name || 'Pitch'} · Game ${row.game_pk || initialGame.value || '—'} · PA ${row.at_bat_number ?? '—'} · Pitch ${row.pitch_number ?? '—'}`}
async function loadPlayers(){
  const current=++request;players.value=[];roster.value=null;loading.value=true;error.value='';videoUrl.value=''
  try{
    if(props.object.kind==='roster' || props.object.kind==='in-game'){
      if(!props.team){error.value='Choose a viewing team to load its official active roster.';return}
      const result=await $fetch<Roster>(`${config.public.apiBase}/teams/${props.team}/active-roster`,{query:{year:year.value},credentials:'include'})
      if(current!==request)return
      roster.value=result
      players.value=result.players.filter(p=>props.object.kind!=='in-game'||p.position_type==='Pitcher').map(p=>({id:p.player_id,name:p.name,role:p.position_name||'Player',pitcher:p.position_type==='Pitcher'}))
    }else if(props.object.kind==='pitcher'){
      const groups=await Promise.all([api.pitchers({year:year.value,role:'SP'}),api.pitchers({year:year.value,role:'RP'})])
      if(current!==request)return
      players.value=Array.from(new Map(groups.flat().filter(p=>!props.team || p.team===props.team).map(p=>[p.value,{id:p.value,name:p.name,role:p.role,pitcher:true}])).values())
    }else{
      const result=await api.batters({year:year.value,team:props.team||'All'})
      if(current!==request)return
      players.value=result.map(p=>({id:p.value,name:p.name,role:'Batter',pitcher:false}))
    }
    // Keep manual selection. Never manufacture a pitcher/outing if no official roster is available.
    if(selectedId.value && !players.value.some(p=>p.id===selectedId.value))await query({player:undefined,game:undefined})
  }catch(e){if(current===request)error.value=e instanceof Error?e.message:'Player directory unavailable. Sign in again if your session expired.'}
  finally{if(current===request)loading.value=false}
}
async function loadVideos(){const current=++request;loading.value=true;error.value='';videos.value=[];videoUrl.value='';try{const result=await api.homeRecommendations(year.value);if(current===request)videos.value=result.videos}catch(e){if(current===request)error.value=e instanceof Error?e.message:'Recommendations unavailable.'}finally{if(current===request)loading.value=false}}
watch(()=>[props.object.id,props.team,year.value],()=>{
  videoUrl.value='';answer.value='';search.value=''
  if(['roster','pitcher','batter','in-game'].includes(props.object.kind))void loadPlayers()
  else if(props.object.kind==='videos')void loadVideos()
},{immediate:true})
onBeforeUnmount(()=>{++request})
</script>

<style scoped>
.object-panel{display:grid;gap:16px;min-width:0}.toolbar,.actions{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.players{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px;max-height:320px;overflow:auto}label{display:grid;gap:7px}select,input,button,.actions a{min-height:44px;border:1px solid #606e75;border-radius:6px;padding:9px 12px;color:var(--color-foreground,#f6f0dd);background:var(--color-surface,#182228);font:inherit;max-width:100%}button,.actions a{cursor:pointer}a{color:#e8ac49}.pitch-video header{display:flex;justify-content:space-between;gap:12px;align-items:center}.pitch-video iframe{width:100%;height:min(65vh,650px);border:0;margin-top:12px;background:#000}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #ffb441;outline-offset:2px}
</style>
