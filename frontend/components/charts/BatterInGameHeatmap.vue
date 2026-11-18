<template>
  <section class="batter-heatmap" aria-label="Batter Personal pitch-location heatmap">
    <header><strong>Batter heatmap · <NuxtLink :to="{path:'/batter-personal',query:{year,batter_id:batterId,tab:'discipline'}}">{{ batterName || 'Batter' }}</NuxtLink></strong><div class="header-actions"><slot name="header-actions" /><label><input v-model="enabled" type="checkbox"> Show heatmap</label></div></header>
    <div class="heatmap-controls">
      <label>Pitcher hand<select v-model="hand"><option value="All">All hands</option><option value="R">vs RHP</option><option value="L">vs LHP</option></select></label>
      <label>Heatmap<select v-model="metric"><option value="choice">Swing%</option><option value="density">Pitch density</option><option value="bat-speed">Bat speed</option></select></label>
      <label>Heatmap Blend<input v-model.number="blend" type="range" min="0" max="1" step="0.1"><b>{{ Math.round(blend*100) }}%</b></label>
      <button v-if="error" type="button" @click="load(true)">Retry</button>
    </div>
    <slot name="toolbar" />
    <p v-if="enabled && loading" role="status">Loading batter pitches…</p>
    <p v-else-if="enabled && error" role="alert">Batter heatmap could not load.</p>
    <p v-else-if="enabled && points.length < 8" role="status">此篩選至少需要 8 筆有落點的投球才能顯示熱圖。</p>
    <details v-else-if="enabled"><summary>Heatmap guide / samples</summary><p>{{ year }} 整季 · {{ hand === 'All' ? '所有投手手別' : `vs ${hand}HP` }} · {{ stand === 'L' || stand === 'R' ? `${stand}HB` : '所有打擊側' }} · {{ contextMode ? count : '所有球數' }} · {{ points.length.toLocaleString() }} pitches。</p><p>與 Batter Personal 共用逐球高斯平滑及配色。Swing% 為附近投球的加權揮棒比例，藍色較低、紅色較高；不是聯盟 PR。低密度處自然淡出，不使用九宮格補色。</p></details>
  </section>
</template>

<script setup lang="ts">
import type { AnalysisResponse } from '~/types/api'
import type { BatterHeatmapOverlay } from '~/utils/batterZoneRates'
import { buildPitchHeatmap, pitchHeatmapReplayBands, type PitchHeatMode } from '~/utils/pitchLocationHeatmap'
import { createBatterHeatmapCache, heatmapRequestKey, type HeatmapRequest } from '~/utils/batterHeatmapCache'

const props=defineProps<{year:number;batterId:number;batterName?:string;pitcherId:number;pitcherHand:string;prefetchBatterId?:number;contextMode?:boolean;contextKey?:string;stand?:string;count?:string;zoneBottom:number;zoneTop:number}>()
const emit=defineEmits<{overlay:[value:BatterHeatmapOverlay|null]}>()
const api=useApi(),enabled=ref(true),hand=ref<'All'|'L'|'R'>('All'),metric=ref<PitchHeatMode>('choice'),blend=ref(1)
const data=shallowRef<AnalysisResponse|null>(null),dataKey=ref(''),loading=ref(false),error=ref(false)
const cache=createBatterHeatmapCache<AnalysisResponse>(undefined,()=>120_000)
const request=computed<HeatmapRequest>(()=>({year:props.year,batterId:props.batterId,pitcherHand:'All'}))
let version=0
watch(()=>props.pitcherHand,()=>{hand.value=props.pitcherHand==='L'||props.pitcherHand==='R'?props.pitcherHand:'All'},{immediate:true})
const fetcher=(p:HeatmapRequest)=>api.batterPersonalDiscipline({year:p.year,batterId:p.batterId})
async function load(force=false){
  const token=++version;error.value=false;loading.value=false
  if(!enabled.value||!props.batterId){data.value=null;return}
  const p=request.value,key=heatmapRequestKey(p),cached=force?undefined:cache.peek(p)
  if(cached){data.value=cached;dataKey.value=key;return}
  data.value=null;loading.value=true
  try{const result=await cache.load(p,fetcher,force);if(token===version){data.value=result;dataKey.value=key}}
  catch{if(token===version)error.value=true}
  finally{if(token===version)loading.value=false}
}
watch(()=>[props.year,props.batterId,enabled.value],()=>void load(),{immediate:true})
const points=computed(()=>{
  if(dataKey.value!==heatmapRequestKey(request.value))return []
  return (data.value?.tables.location_points?.rows||[]).filter(row=>
    row.plate_x!=null&&row.plate_z!=null&&Number.isFinite(Number(row.plate_x))&&Number.isFinite(Number(row.plate_z))
    &&(hand.value==='All'||row.p_throws===hand.value)
    &&(!['L','R'].includes(props.stand||'')||row.stand===props.stand)
    &&(!props.contextMode||(Boolean(props.count)&&row.count===props.count)))
})
// Identical compact Personal domain, bandwidth, palette and blend semantics.
const cells=computed(()=>buildPitchHeatmap(points.value.map(row=>({x:-Number(row.plate_x),z:Number(row.plate_z),swung:Boolean(row.is_swing),batSpeed:row.bat_speed==null?null:Number(row.bat_speed)})),{blend:blend.value,mode:metric.value,xDomain:[-2.2,2.2],zDomain:[0,4.8]}))
const bands=computed(()=>pitchHeatmapReplayBands(cells.value,props.zoneBottom,props.zoneTop))
watch(()=>[bands.value,enabled.value,props.year,props.batterId,props.pitcherId,props.pitcherHand,props.contextMode,props.contextKey],()=>emit('overlay',enabled.value?{bands:bands.value,metric:metric.value,context:`${props.year}:${props.batterId}:${props.pitcherId}:${props.pitcherHand}${props.contextMode?':'+props.contextKey:''}`} :null),{immediate:true})
let prefetchTimer:ReturnType<typeof setTimeout>|undefined
watch(()=>[props.prefetchBatterId,props.year,enabled.value],()=>{
  clearTimeout(prefetchTimer)
  if(enabled.value&&props.prefetchBatterId&&props.prefetchBatterId!==props.batterId){
    const p:HeatmapRequest={year:props.year,batterId:props.prefetchBatterId,pitcherHand:'All'}
    prefetchTimer=setTimeout(()=>{void cache.load(p,fetcher).catch(()=>{})},150)
  }
},{immediate:true})
onBeforeUnmount(()=>{version++;clearTimeout(prefetchTimer);emit('overlay',null)})
</script>

<style scoped>
.batter-heatmap{display:grid;gap:9px;margin-top:12px;padding:12px;border:1px solid var(--color-border);border-radius:8px;background:var(--color-surface)}
header,.header-actions,.heatmap-controls{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.heatmap-controls{justify-content:flex-start}.heatmap-controls label{display:flex;align-items:center;gap:7px}select,button{padding:7px;color:var(--color-foreground);background:var(--color-plot-bg);border:1px solid var(--color-border);border-radius:5px}p{margin:4px 0;font-size:12px;color:var(--color-muted-text)}input[type=range]{width:130px;accent-color:var(--color-primary)}summary{cursor:pointer;font-size:12px}
</style>
