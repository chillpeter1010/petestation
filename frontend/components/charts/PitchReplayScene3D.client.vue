<template>
  <section class="spatial-replay" aria-label="Three-dimensional historical pitch analysis">
    <div ref="host" class="spatial-canvas" />
    <div v-if="hoveredPath" class="pitch-tooltip" role="group" aria-label="Pitch details" @pointerenter="keepHover" @pointerleave="setHover(null)">
      <strong>Pitch details</strong>
      <nav v-if="hoveredRow">
        <NuxtLink v-if="Number(hoveredRow.pitcher)>0" :to="{path:'/pitcher-personal',query:{year,pitcher_id:Number(hoveredRow.pitcher)}}">{{ hoveredRow.pitcher_name || 'Pitcher personal' }}</NuxtLink>
        <NuxtLink v-if="Number(hoveredRow.batter)>0" :to="{path:'/batter-personal',query:{year,batter_id:Number(hoveredRow.batter)}}">{{ hoveredRow.batter_name || 'Batter personal' }}</NuxtLink>
      </nav>
      <pre>{{ hoveredPath.label }}</pre>
      <button v-if="hoveredRow && inGamePitchVideoUrl(hoveredRow)" type="button" @click="emit('open-video',hoveredRow)">Open video</button>
      <small v-else>No video mapping for this pitch.</small>
    </div>
    <p v-if="loading" class="loading" role="status">Loading 3D field…</p>
    <p class="scene-note" role="status">{{ actorStatus }}</p>
    <p class="scene-note">Gold: recorded release point / height. Grey heatmap cells: insufficient sample/reference. Drag / arrows: orbit · wheel / + −: move camera · Home: reset.</p>
    <dl v-if="input.points[0] && !input.batterSwingReference" class="release-values">
      <div><dt>Release X</dt><dd>{{ input.points[0].x_ft.toFixed(2) }} ft</dd></div>
      <div><dt>Release Y</dt><dd>{{ input.points[0].y_ft.toFixed(2) }} ft</dd></div>
      <div><dt>Release height / Z</dt><dd>{{ input.points[0].z_ft.toFixed(2) }} ft</dd></div>
      <div><dt>Arm angle</dt><dd>{{ input.armAngleDeg!=null && Number.isFinite(input.armAngleDeg) ? input.armAngleDeg.toFixed(1)+'°' : 'unavailable' }}</dd></div>
      <div><dt>Extension</dt><dd>{{ input.releaseExtensionFt!=null && Number.isFinite(input.releaseExtensionFt) ? input.releaseExtensionFt.toFixed(2)+' ft' : 'unavailable' }}</dd></div>
    </dl>
    <p v-if="input.batterSwingReference" class="scene-note">Perdomo B reference swing · source {{ input.batterSwingReference.sourceTime.toFixed(3) }} s · estimated body/root, generic ground clearance and bat grip. No measured bat path or contact alignment.</p>
    <p v-else-if="!input.previewOnly" class="scene-note">Extension is not stride length. The gold point shows the recorded release position.</p>
    <p v-if="input.motion" class="scene-note">{{ input.motion.phase }} · {{ input.motion.timeSeconds.toFixed(2) }} s · Arm angle: {{ input.motion.armAngleDeg==null?'unavailable (generic 45° prior)':input.motion.armAngleDeg.toFixed(1)+'° source' }} · Batter: {{ input.motion.batterAction }} (generic timing; contact unmeasured).</p>
  </section>
</template>
<script setup lang="ts">
import type { Replay3DInput, ReplayView } from './replay3d/replayContract'
import type { createReplayScene } from './replay3d/createReplayScene'
import { inGamePitchVideoUrl } from '~/utils/pitcherInGame'
const props=defineProps<{input:Replay3DInput;view:ReplayView;resetToken:number;year?:number}>()
const emit=defineEmits<{pick:[key:string];failure:[message:string];'open-video':[row:Record<string,unknown> ]}>()
const host=ref<HTMLElement|null>(null),loading=ref(true)
const actorStatus=ref('Loading character rig…')
const hoveredKey=ref<string|null>(null)
const hoveredPath=computed(()=>props.input.paths.find(path=>path.key===hoveredKey.value))
const hoveredRow=computed(()=>hoveredPath.value?.source)
let hoverTimer:ReturnType<typeof setTimeout>|undefined
function keepHover(){clearTimeout(hoverTimer)}
function setHover(key:string|null){keepHover();if(key)hoveredKey.value=key;else hoverTimer=setTimeout(()=>{hoveredKey.value=null},250)}
let scene:ReturnType<typeof createReplayScene>|undefined,disposed=false
watch(()=>props.input,value=>scene?.update(value))
watch(()=>props.input.selectedKey,()=>{keepHover();hoveredKey.value=null})
watch(()=>[props.view,props.resetToken],()=>scene?.reset(props.view))
onMounted(async()=>{
  try {
    const {createReplayScene}=await import('./replay3d/createReplayScene')
    if(disposed||!host.value)return
    scene=createReplayScene(host.value,key=>emit('pick',key),message=>emit('failure',message),message=>{actorStatus.value=message},setHover)
    scene.update(props.input);scene.reset(props.view);loading.value=false
  }catch{if(!disposed)emit('failure','3D could not start. The schematic, pitch details and videos remain available.')}
})
onBeforeUnmount(()=>{disposed=true;keepHover();scene?.dispose();scene=undefined})
</script>
<style scoped>
.pitch-tooltip{position:absolute;z-index:6;top:16px;right:12px;max-width:min(310px,70%);max-height:390px;overflow:auto;padding:12px;border:1px solid #8fa7b7;border-radius:9px;background:#000000f5;color:#f1f5f9;pointer-events:auto;font-size:12px}.pitch-tooltip pre{margin:7px 0 0;white-space:pre-wrap;font:inherit;line-height:1.5}.pitch-tooltip nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:7px}.pitch-tooltip a{color:#fff;text-decoration:underline}.pitch-tooltip button{margin-top:8px;padding:7px 12px;border:1px solid #f8b848;border-radius:6px;background:#f8b848;color:#131c28;cursor:pointer}
.release-values{display:flex;gap:12px 24px;flex-wrap:wrap;margin:0;padding:10px 14px;color:#d9e9ee}.release-values div{display:grid;gap:4px}.release-values dt{font-size:12px;color:#a9becb}.release-values dd{margin:0;font-weight:800;font-variant-numeric:tabular-nums}
.spatial-replay{position:relative;background:#000}.spatial-canvas{height:clamp(360px,54vw,640px);width:100%;overflow:hidden}.spatial-canvas :deep(canvas){display:block;width:100%;height:100%;touch-action:none;outline-offset:-3px}.spatial-canvas :deep(canvas:focus-visible){outline:2px solid #fbb754}.scene-note{margin:0;padding:7px 14px;color:#d9e9ee;font-size:12px;line-height:1.5}.loading{position:absolute;top:35%;left:0;right:0;text-align:center;color:#fff}
</style>
