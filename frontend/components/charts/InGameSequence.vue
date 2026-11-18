<template>
  <section class="in-game-sequence" :aria-busy="loading" aria-label="Sequence filtered to selected pitch context">
    <header><h3>Sequence · Conditioned branch</h3><span>{{ year }} season · {{ count }} · vs {{ side || '?' }}HB · Previous: {{ previous.label }}</span></header>
    <p v-if="!valid">Count / batter side unavailable.</p>
    <p v-else-if="previous.key==null">Previous pitch is missing from this plate appearance. No earlier pitch is substituted.</p>
    <p v-else-if="loading" role="status">Loading Sequence…</p>
    <p v-else-if="error" role="alert">Sequence unavailable. <button type="button" @click="load">Retry</button></p>
    <div v-else-if="mix.length" class="sequence-results">
      <p>Anchor {{ count }} after {{ previous.label }} · {{ branchSummary.downstream_pas ?? 0 }} PA · {{ branchSummary.downstream_pitches ?? 0 }} downstream pitches</p>
      <SequenceOutcomeTree :rows="mix" />
    </div>
    <p v-else>No season pitches match this exact count, batter side and previous pitch.</p>
    <details><summary>Branch guide</summary><small>Conditions on the selected count, batter side and immediately previous pitch, then shows the anchor and subsequent count branches within those plate appearances. Descriptive full-season context, not a prediction.</small></details>
  </section>
</template>
<script setup lang="ts">
import type { AnalysisResponse } from '~/types/api'
import {previousReplayPitch,type InGameRow} from '~/utils/pitcherInGame'
const props=defineProps<{year:number;pitcherId:number;rows:InGameRow[];selected:InGameRow}>()
const api=useApi(),data=shallowRef<AnalysisResponse|null>(null),loading=ref(false),error=ref(false)
const count=computed(()=>`${props.selected.balls ?? '?'}-${props.selected.strikes ?? '?'}`)
const side=computed(()=>props.selected.stand==='L'||props.selected.stand==='R'?props.selected.stand:'')
const valid=computed(()=>side.value&&props.selected.balls!=null&&props.selected.strikes!=null&&/^[0-3]-[0-2]$/.test(count.value))
const previous=computed(()=>previousReplayPitch(props.rows,props.selected))
const mix=computed(()=>Array.isArray(data.value?.charts.conditioned_count_pitch_mix)?data.value!.charts.conditioned_count_pitch_mix as Record<string,unknown>[]:[])
const branchSummary=computed(()=>(data.value?.charts.conditioned_summary||{}) as Record<string,unknown>)
const cache=new Map<string,AnalysisResponse>();let version=0,timer:ReturnType<typeof setTimeout>|undefined
async function load(){
  const token=++version;data.value=null;error.value=false;loading.value=false
  if(!valid.value||previous.value.key==null)return
  const key=[props.year,props.pitcherId,side.value,count.value,previous.value.key].join(':')
  loading.value=true
  try{
    const result=cache.get(key)||await api.personalSequence({year:props.year,pitcherId:props.pitcherId,stand:side.value,count:count.value,detailCount:count.value,conditionCount:count.value,conditionPitch:'All',previousPitch:previous.value.key})
    if(token!==version)return
    data.value=result;if(cache.size>=24)cache.delete(cache.keys().next().value!);cache.set(key,result)
  }catch{if(token===version)error.value=true}finally{if(token===version)loading.value=false}
}
watch(()=>[props.year,props.pitcherId,side.value,count.value,previous.value.key],()=>{++version;data.value=null;error.value=false;loading.value=Boolean(valid.value&&previous.value.key!=null);clearTimeout(timer);timer=setTimeout(load,100)},{immediate:true})
onBeforeUnmount(()=>{++version;clearTimeout(timer)})
</script>
<style scoped>
.in-game-sequence{display:grid;gap:8px;min-width:0;padding:10px;border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface);font-size:12px}header{display:grid;gap:5px}h3,p{margin:0}h3{font-size:14px}header span,p,small{color:var(--color-muted-text);line-height:1.5}.sequence-results{display:grid;gap:8px;min-width:0}button{font:inherit;cursor:pointer}summary{cursor:pointer}
.in-game-sequence :deep(.tree-wrap){padding:6px 4px 0}.in-game-sequence :deep(svg){width:100%;min-width:0}.in-game-sequence :deep(.chart-header){padding:8px;flex-wrap:wrap;gap:4px}.in-game-sequence :deep(.chart-header h2){font-size:12px}.in-game-sequence :deep(.chart-header span),.in-game-sequence :deep(.legend){font-size:11px}
</style>
