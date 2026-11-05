<template>
  <div class="matchup-cards" aria-label="Exact count season matchup context" :aria-busy="loading">
    <article v-for="role in roles" :key="role.key" class="matchup-card">
      <header><span>{{ role.key==='pitcher'?'PITCHER ARSENAL':'BATTER PROFILE' }} · {{ balls }}–{{ strikes }}</span><NuxtLink :to="{path:role.key==='pitcher'?'/pitcher-personal':'/batter-personal',query:{year,...(role.key==='pitcher'?{pitcher_id:pitcherId}:{batter_id:batterId})}}">{{ role.name || (loading?'Loading name…':'Name unavailable') }} ↗</NuxtLink></header>
      <p class="split-label">{{ year }} regular season · {{ role.key==='pitcher'?`vs ${batterSide==='L'?'LHB':batterSide==='R'?'RHB':'unknown batter side'}`:`vs ${pitcherHand==='L'?'LHP':pitcherHand==='R'?'RHP':'unknown pitcher hand'}` }}</p>
      <p v-if="loading" role="status">Loading count split…</p>
      <p v-else-if="error" role="alert">Split unavailable. <button type="button" @click="load">Retry</button></p>
      <p v-else-if="role.data?.status!=='ready'">{{ data?.source_status==='unavailable'?'Season source unavailable.':role.data?.status==='unknown_hand'?'Handedness unavailable.':'No season pitches for this exact count and side.' }}</p>
      <template v-else>
        <div class="quick-stats"><div><span>Pitches</span><b>{{ role.data.summary.pitches }}</b></div><div><span>Swing</span><b>{{ value(role.data.summary.swing_pct) }}</b></div><div><span>Contact</span><b>{{ value(role.data.summary.contact_pct) }}</b></div><div><span>Whiff</span><b>{{ value(role.data.summary.whiff_pct) }}</b></div></div>
        <div class="pitch-table"><table><thead><tr><th>Pitch</th><th>N</th><th>{{ role.key==='pitcher'?'Mix':'Swing' }}</th><th>{{ role.key==='pitcher'?'mph':'Contact' }}</th><th>{{ role.key==='pitcher'?'Whiff':'AVG' }}</th></tr></thead><tbody><tr v-for="row in role.data.pitches" :key="row.pitch"><th><i :style="{background:getPitchColor(row.pitch)}" />{{ row.pitch }}</th><td>{{ row.pitches }}</td><td>{{ value(role.key==='pitcher'?row.usage_pct:row.swing_pct) }}</td><td>{{ value(role.key==='pitcher'?row.velocity:row.contact_pct,role.key==='pitcher'?'number':'percent') }}</td><td>{{ value(role.key==='pitcher'?row.whiff_pct:row.avg,role.key==='pitcher'?'percent':'decimal') }}</td></tr></tbody></table></div>
        <details><summary>More rates / sample sizes</summary><div class="pitch-table"><table><thead><tr><th>Pitch</th><th>Strike</th><th>Zone</th><th>AVG</th><th>wOBA</th><th>HardHit</th><th>AB / BBE</th></tr></thead><tbody><tr v-for="row in [role.data.summary,...role.data.pitches]" :key="row.pitch"><th>{{ row.pitch }}</th><td>{{ value(row.strike_pct) }}</td><td>{{ value(row.zone_pct) }}</td><td>{{ value(row.avg,'decimal') }}</td><td>{{ value(row.woba,'decimal') }}</td><td>{{ value(row.hard_hit_pct) }}</td><td>{{ row.denominators.ab }} / {{ row.denominators.tracked_bbe }}</td></tr></tbody></table></div><p>Exact pre-pitch count; not head-to-head. Contact/Whiff use swings. AVG/wOBA use PA-ending pitches; HardHit uses tracked fair BBE ≥95mph. Fewer than 30 pitches is a limited sample; — means no denominator.</p></details>
      </template>
    </article>
  </div>
</template>
<script setup lang="ts">
import type { InGameCountContext } from '~/types/api'
import { getPitchColor } from '~/utils/pitchColors'
const props=defineProps<{year:number;pitcherId:number;batterId:number;pitcherName?:string;batterName?:string;batterSide:string;pitcherHand:string;balls:number;strikes:number}>()
const emit=defineEmits<{identity:[value:{pitcherName:string;batterName:string}]}>()
const api=useApi(),data=shallowRef<InGameCountContext|null>(null),loading=ref(false),error=ref(false)
const cache=new Map<string,InGameCountContext>();let version=0
const roles=computed(()=>[{key:'pitcher' as const,name:data.value?.pitcher_name||props.pitcherName,data:data.value?.pitcher},{key:'batter' as const,name:data.value?.batter_name||props.batterName,data:data.value?.batter}])
function value(n:number|null|undefined,format='percent'){return n==null?'—':format==='decimal'?n.toFixed(3):format==='number'?n.toFixed(1):`${n.toFixed(1)}%`}
async function load(){
  const token=++version;data.value=null;error.value=false;loading.value=true
  const key=[props.year,props.pitcherId,props.batterId,props.batterSide,props.pitcherHand,props.balls,props.strikes].join(':')
  try{
    const result=cache.get(key)||await api.inGameCountContext({year:props.year,pitcherId:props.pitcherId,batterId:props.batterId,batterSide:props.batterSide==='L'||props.batterSide==='R'?props.batterSide:'unknown',pitcherHand:props.pitcherHand==='L'||props.pitcherHand==='R'?props.pitcherHand:'unknown',balls:props.balls,strikes:props.strikes})
    if(token!==version)return
    data.value=result;if(cache.size>=48)cache.delete(cache.keys().next().value!);cache.set(key,result)
    emit('identity',{pitcherName:result.pitcher_name||props.pitcherName||'',batterName:result.batter_name||props.batterName||''})
  }catch{if(token===version)error.value=true}finally{if(token===version)loading.value=false}
}
watch(()=>[props.year,props.pitcherId,props.batterId,props.batterSide,props.pitcherHand,props.balls,props.strikes],load,{immediate:true})
onBeforeUnmount(()=>{++version})
</script>
<style scoped>
.matchup-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;padding:16px;background:#0a1722}.matchup-card{min-width:0;overflow:auto;padding:18px;border:1px solid #3c655a;border-radius:12px;background:rgb(10 23 31 / 94%);box-shadow:0 12px 35px #0005;color:#dbe9ef;backdrop-filter:blur(10px);font-size:12px}.matchup-card header{display:grid;gap:7px}.matchup-card header>span{color:#7de6c4;font-size:10px;font-weight:850;letter-spacing:.1em}.matchup-card a{font-size:17px;font-weight:850;color:#f7fbff;text-decoration:none}.split-label{color:#9bb2c2;margin:8px 0 12px}.quick-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-bottom:12px}.quick-stats div{display:grid;gap:5px}.quick-stats span{color:#91aebb;font-size:10px}.quick-stats b{font-size:15px;color:#e2ffef}.pitch-table{overflow-x:auto}table{width:100%;border-collapse:collapse;white-space:nowrap;text-align:right}th,td{padding:7px 4px;border-bottom:1px solid #29424c;font-variant-numeric:tabular-nums}th:first-child{text-align:left}i{display:inline-block;width:7px;height:7px;margin-right:5px;border-radius:50%}summary,button{cursor:pointer}details{margin-top:12px}details p{color:#9bb2c2;line-height:1.6}button{background:#163d36;color:#d8fff0;border:1px solid #397765;border-radius:4px;padding:5px}
@media(max-width:1500px){.matchup-cards{position:static;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));padding:14px;background:#0a1722;align-items:start}.matchup-card{width:auto;max-width:none;max-height:none}}
@media(max-width:650px){.matchup-cards{grid-template-columns:1fr}}
</style>
