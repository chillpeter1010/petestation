<template>
  <section class="bullpen-select" :aria-busy="loading" aria-label="Official bullpen pitcher selection">
    <header><strong>{{ lane==='west'?'West':'East' }} bullpen · {{ team || 'Choose team' }}</strong><span>Manual pitcher / outing selection · static figures</span></header>
    <div class="controls">
      <label>Season<select :value="year" @change="changeContext({year:Number(($event.target as HTMLSelectElement).value)})"><option v-for="y in [2026,2025,2024,2023,2022,2021]" :key="y" :value="y">{{ y }}</option></select></label>
      <label>Viewing team<select :value="team" @change="changeContext({team:($event.target as HTMLSelectElement).value})"><option value="" disabled>Select team</option><option v-for="t in MLB_TEAMS" :key="t.code" :value="t.code">{{ t.code }} · {{ t.name }}</option></select></label>
      <label>Official roster · pitcher<select :value="pitcherId || ''" :disabled="loading || !players.length" @change="choose(Number(($event.target as HTMLSelectElement).value))"><option value="">Select pitcher</option><option v-if="pitcherId && !players.some(p=>p.player_id===pitcherId)" :value="pitcherId">Current historical selection · outside this active snapshot</option><option v-for="p in players" :key="p.player_id" :value="p.player_id">{{ p.name }} · {{ p.position_name || 'Pitcher' }}</option></select></label>
    </div>
    <p v-if="loading" role="status">Loading official active roster…</p>
    <p v-else-if="error" role="alert">{{ error }} <button type="button" @click="load">Retry</button></p>
    <p v-else-if="roster">MLB StatsAPI active roster: <b>{{ roster.freshness }}</b> · retrieved {{ roster.retrieved_at || 'unavailable' }}<span v-if="roster.source_as_of"> · source {{ roster.source_as_of }}</span>. This snapshot is separate from the historical game roster.</p>
    <p v-if="!loading && !players.length">No official pitchers available. No season-participant list is substituted; an explicit historical pitcher remains usable.</p>
  </section>
</template>
<script setup lang="ts">
import { MLB_TEAMS } from '~/config/mlbTeams'
type Pitcher={player_id:number;name:string;position_name:string|null;position_type:string|null}
type Roster={freshness:'fresh'|'stale'|'unavailable';retrieved_at:string|null;source_as_of:string|null;players:Pitcher[]}
const props=defineProps<{year:number;team:string;pitcherId:number|null;lane:'west'|'east'}>()
const emit=defineEmits<{ready:[value:boolean];identity:[value:{id:number;name:string}]}>()
const config=useRuntimeConfig(),route=useRoute(),router=useRouter()
const roster=ref<Roster|null>(null),loading=ref(false),error=ref('')
const players=computed(()=>roster.value?.freshness==='unavailable'?[]:(roster.value?.players||[]).filter(p=>p.position_type==='Pitcher'))
let version=0
function choose(id:number){if(!players.value.some(p=>p.player_id===id))return;void router.replace({query:{...route.query,pitcher_id:id,game_pk:undefined,gamePk:undefined}})}
function changeContext(values:{team?:string;year?:number}){emit('ready',false);void router.replace({query:{...route.query,...values,pitcher_id:undefined,pitcherId:undefined,game_pk:undefined,gamePk:undefined}})}
async function load(){
  const request=++version;roster.value=null;loading.value=true;error.value='';emit('ready',false)
  try{
    if(!props.team){error.value='Choose a team to load its official roster.';return}
    const result=await $fetch<Roster>(`${config.public.apiBase}/teams/${props.team}/active-roster`,{query:{year:props.year},credentials:'include',timeout:15000})
    if(request!==version)return
    roster.value=result
    // Explicit historical choices win; otherwise select the first official entry.
    const requested=Number(route.query.pitcher_id||route.query.pitcherId)
    if(!Number.isSafeInteger(requested)||requested<=0){if(players.value[0])choose(players.value[0].player_id)}
  }catch(e){if(request===version)error.value=e instanceof Error?e.message:'Official roster unavailable.'}
  finally{if(request===version){loading.value=false;emit('ready',true)}}
}
watch(()=>[props.year,props.team],load,{immediate:true})
watch(()=>[props.pitcherId,players.value],()=>{const p=players.value.find(p=>p.player_id===props.pitcherId);if(p)emit('identity',{id:p.player_id,name:p.name})},{immediate:true})
onBeforeUnmount(()=>{++version})
</script>
<style scoped>
.bullpen-select{padding:16px;border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface);display:grid;gap:12px}header,.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end}header{justify-content:space-between}header span,p{color:var(--color-muted-text);font-size:13px;margin:0;line-height:1.6}label{display:grid;gap:6px;flex:1 1 180px;font-size:12px}select,button{font:inherit;color:var(--color-foreground);background:var(--color-background);border:1px solid var(--color-border);border-radius:6px;min-height:44px;padding:8px;max-width:100%}select:focus-visible,button:focus-visible{outline:2px solid var(--color-primary);outline-offset:3px}
</style>
