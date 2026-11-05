<template>
  <section class="game-bridge">
    <div class="toolbar">
      <label>Date<input v-model="date" type="date"></label><button type="button" @click="loadGames">Load games</button>
      <label>Game<select :value="gameId || ''" @change="chooseGame(Number(($event.target as HTMLSelectElement).value))"><option value="">Select game</option><option v-for="game in games" :key="game.game_pk" :value="game.game_pk">{{ game.game_date }} · {{ game.away_team }} {{ game.away_score ?? '—' }} @ {{ game.home_team }} {{ game.home_score ?? '—' }}</option></select></label>
    </div>
    <p v-if="loading" role="status">Loading game data…</p><p v-if="error" role="alert">{{ error }} <button type="button" @click="loadGames">Retry</button></p>
    <p v-if="!loading && !error && !games.length">No games in this snapshot for the selected date/team.</p>
    <template v-if="detail && !loading && !error">
      <nav aria-label="Game analysis"><button v-for="item in modes" :key="item" type="button" :aria-pressed="mode===item" @click="setMode(item)">{{ item === 'replay' ? 'In game' : item }}</button></nav>
      <label v-if="mode!=='box'">Pitcher<select :value="pitcherId || ''" @change="setPitcher(Number(($event.target as HTMLSelectElement).value))"><option value="">Select pitcher</option><option v-for="player in pitchers" :key="player.pitcher_id" :value="player.pitcher_id">{{ player.name }} · {{ player.team }}</option></select></label>
      <template v-if="mode==='box'">
        <DataTable v-for="team in detail.batting || []" :key="`bat-${team.team}`" :title="`${team.team} batting`" :table="boxTable(team.hitters,['name','position','pa','ab','hits','home_runs','walks','strikeouts','average'])" />
        <DataTable v-for="team in detail.teams" :key="team.team" :title="`${team.team} pitching`" :table="boxTable(team.pitchers,['name','ip','hits','runs','earned_runs','walks','strikeouts','pitches','era'])" />
      </template>
      <LazyGamePitcherAnalysisPanel v-else-if="selectedPitcher && gameId" :key="`${year}:${gameId}:${pitcherId}:${mode}`" :year="year" :game-pk="gameId" :pitcher-id="selectedPitcher.pitcher_id" :pitcher-name="selectedPitcher.name" :mode="mode" @select-pitch="emit('pitch',$event)" />
      <p v-else>No pitcher analysis is available for this selection.</p>
    </template>
  </section>
</template>
<script setup lang="ts">
import type { TablePayload } from '~/types/api'
import { positiveId } from './runtime/interactionCatalog'
type Mode='box'|'location'|'sequence'|'movement'|'replay'
type Game={game_pk:number;game_date:string;away_team:string;home_team:string;away_score?:number;home_score?:number}
type Pitcher=Record<string,unknown>&{pitcher_id:number;name:string;team?:string}
type Detail={teams:{team:string;pitchers:Pitcher[]}[];batting?:{team:string;hitters:Record<string,unknown>[]}[]}
const props=defineProps<{year:number;team:string;initialMode?:string}>()
const emit=defineEmits<{pitch:[row:Record<string,unknown>]}>()
const api=useApi(), route=useRoute(),router=useRouter()
const modes:Mode[]=['box','location','sequence','movement','replay']
const date=ref(typeof route.query.date==='string'?route.query.date:'')
const games=ref<Game[]>([]), detail=ref<Detail|null>(null),loading=ref(false),error=ref('')
const gameId=computed(()=>positiveId(route.query.game)),pitcherId=computed(()=>positiveId(route.query.player))
const mode=computed<Mode>(()=>modes.includes(route.query.mode as Mode)?route.query.mode as Mode:props.initialMode==='replay'?'replay':'box')
const pitchers=computed(()=>detail.value?.teams.flatMap(t=>t.pitchers.map(p=>({...p,team:t.team})))||[])
const selectedPitcher=computed(()=>pitchers.value.find(p=>p.pitcher_id===pitcherId.value))
let version=0, listVersion=0
function query(values:Record<string,string|number|undefined>){return router.replace({query:{...route.query,...values},state:{ballparkOverlay:window.history.state.ballparkOverlay}})}
function setMode(value:Mode){void query({mode:value})}
function setPitcher(value:number){void query({player:value||undefined})}
function chooseGame(value:number){void query({game:value||undefined,player:undefined,date:date.value||undefined})}
function boxTable(rows:Record<string,unknown>[],columns:string[]):TablePayload{return {columns:columns.map(key=>({key,label:key.replaceAll('_',' ')})),rows}}
async function loadGames(){
  const current=++listVersion; ++version; loading.value=true;error.value='';games.value=[];detail.value=null
  try{
    let result=await api.gamesList({year:props.year,date:date.value||undefined,team:props.team||undefined,limit:120})
    if(current!==listVersion)return
    if(!date.value && result.latest_game_date){date.value=String(result.latest_game_date);result=await api.gamesList({year:props.year,date:date.value,team:props.team||undefined,limit:120})}
    if(current!==listVersion)return
    games.value=(result.games||[]) as Game[]
    const next=games.value.some(g=>g.game_pk===gameId.value)?gameId.value:games.value[0]?.game_pk
    if(next!==gameId.value)await query({game:next,player:undefined,date:date.value||undefined})
    else if(next)await loadDetail()
  }catch(e){if(current===listVersion)error.value=e instanceof Error?e.message:'Game list unavailable.'}
  finally{if(current===listVersion)loading.value=false}
}
async function loadDetail(){
  const id=gameId.value,current=++version;detail.value=null;error.value=''
  if(!id || !games.value.some(g=>g.game_pk===id))return
  loading.value=true
  try{
    const result=await api.gamePitching({year:props.year,gamePk:id})
    if(current!==version)return
    detail.value=result as unknown as Detail
    if(!pitchers.value.some(p=>p.pitcher_id===pitcherId.value))await query({player:pitchers.value[0]?.pitcher_id})
  }catch(e){if(current===version)error.value=e instanceof Error?e.message:'Game detail unavailable.'}
  finally{if(current===version)loading.value=false}
}
watch(gameId,()=>{void loadDetail()})
watch(()=>[props.year,props.team],()=>{void loadGames()},{immediate:true})
onBeforeUnmount(()=>{++version;++listVersion})
</script>
<style scoped>
.game-bridge{display:grid;gap:16px}.toolbar,nav{display:flex;flex-wrap:wrap;gap:12px;align-items:end}label{display:grid;gap:6px;min-width:0}select,input,button{min-height:42px;padding:8px;border:1px solid #5b6a72;border-radius:6px;color:var(--color-foreground);background:var(--color-surface);font:inherit;max-width:100%}button{cursor:pointer}button[aria-pressed=true]{border-color:#ffb441;color:#ffb441}
</style>
