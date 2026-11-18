<template>
  <section class="video-pose-pilot" aria-label="Reference-video reconstruction pilot">
    <header><h3>{{ clip?.playerName || 'Pitcher' }} · Video reconstruction pilot</h3><button v-if="reconstructionAvailable" type="button" @click="resetToken++">Reset view</button></header>
    <p v-if="loading" role="status">Loading processed reference motion…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="clip">
      <p>Reference: {{ clip.date }} · <a :href="clip.sourceUrl" target="_blank" rel="noopener noreferrer">Original pitch video ↗</a>. This one clip is separate from the outing selected below.</p>
      <p>Monocular estimated 3D pose on a generic 1.83 m rig, with fixed bone lengths and knee hinge limits. Depth, camera orientation and ground contact are approximate; no measured release alignment or ball flight is claimed here.</p>
      <p v-if="!reconstructionAvailable" role="status">Reconstruction preview paused: leg twisting and stride errors were reported. The original reference video remains available; the selected game's pitch analysis below is unchanged.</p>
      <div v-if="reconstructionAvailable" class="controls">
        <button type="button" :disabled="playing" @click="play">Play</button><button type="button" :disabled="!playing" @click="pause">Pause</button><button type="button" @click="replay">Replay</button>
        <label>Speed <select v-model.number="rate"><option :value=".25">0.25×</option><option :value=".5">0.5×</option><option :value="1">1×</option></select></label>
        <label class="seek">Reference timeline<input v-model.number="progress" type="range" min="0" max="1" step="0.001" @input="pause"></label>
      </div>
      <p v-if="reconstructionAvailable" aria-live="polite">Source {{ sourceTime.toFixed(3) }} s · {{ currentFrame?.uncertain.length || 0 }} low-confidence source landmarks{{ currentFrame?.filled?' · missing source frame estimated from its neighbour':'' }}.</p>
      <PitchReplayScene3D v-if="reconstructionAvailable && !error" :input="input" view="pitcher-detail" :reset-token="resetToken" @failure="failed" />
    </template>
  </section>
</template>
<script setup lang="ts">
import type {ReplayVideoPoseClip,Replay3DInput} from '../charts/replay3d/replayContract'
const PitchReplayScene3D=defineAsyncComponent(()=>import('../charts/PitchReplayScene3D.client.vue'))
const props=defineProps<{pitcherId:number}>()
// User rejected this monocular retarget candidate: do not expose its motion again.
const reconstructionAvailable=false
const clip=shallowRef<ReplayVideoPoseClip|null>(null),loading=ref(true),error=ref(''),progress=ref(0),rate=ref(.5),playing=ref(false),resetToken=ref(0)
let handle:number|null=null,started=0,startProgress=0,disposed=false
const sourceTime=computed(()=>clip.value?clip.value.sourceStart+progress.value*(clip.value.sourceEnd-clip.value.sourceStart):0)
const currentFrame=computed(()=>clip.value?.frames.find(f=>f.sourceTime>=sourceTime.value)||clip.value?.frames.at(-1))
const input=computed<Replay3DInput>(()=>({selectedKey:clip.value?.id||'pose-pilot',points:[],paths:[],progress:0,color:'#ffc354',zoneTop:3.5,zoneBottom:1.5,stand:'',heatmap:[],actorPose:'ready',previewOnly:true,pitcherActor:{hand:'R',heightM:1.83,team:props.pitcherId===702056?'TOR':'AZ',home:false},videoPose:clip.value?{clip:clip.value,playerId:props.pitcherId,progress:progress.value}:undefined}))
function pause(){playing.value=false;if(handle!==null)cancelAnimationFrame(handle);handle=null}
function play(){if(!reconstructionAvailable||!clip.value||error.value)return;pause();if(progress.value>=1)progress.value=0;startProgress=progress.value;started=performance.now();playing.value=true;handle=requestAnimationFrame(tick)}
function tick(now:number){if(!playing.value||!clip.value)return;progress.value=Math.min(1,startProgress+(now-started)/1000*rate.value/(clip.value.sourceEnd-clip.value.sourceStart));if(progress.value<1)handle=requestAnimationFrame(tick);else pause()}
function replay(){progress.value=0;play()}
function failed(message:string){pause();error.value=message}
function hidden(){if(document.hidden)pause()}
watch(rate,()=>{if(playing.value)play()})
onMounted(async()=>{
  document.addEventListener('visibilitychange',hidden)
  try{
    const value=props.pitcherId===702056?await import('~/assets/ballpark/motion/yesavage-video-pose-v1.json'):props.pitcherId===657044?await import('~/assets/ballpark/motion/thompson-video-pose-v1.json'):null
    if(disposed)return
    if(!value||value.default.playerId!==props.pitcherId)throw new Error('No reference motion for this pitcher.')
    clip.value=value.default as unknown as ReplayVideoPoseClip
  }catch(e){if(!disposed)error.value=e instanceof Error?e.message:'Reference motion unavailable.'}finally{if(!disposed)loading.value=false}
})
onBeforeUnmount(()=>{disposed=true;pause();document.removeEventListener('visibilitychange',hidden)})
</script>
<style scoped>
.video-pose-pilot{border:1px solid #668a8f;border-radius:10px;padding:16px;background:var(--color-surface);color:var(--color-foreground)}header,.controls{display:flex;align-items:center;flex-wrap:wrap;gap:12px}header{justify-content:space-between}h3{margin:0}p{font-size:14px;line-height:1.6}a{color:var(--color-foreground)}button,select{font:inherit;min-height:38px;padding:6px 12px;border:1px solid var(--color-border);border-radius:6px;background:var(--color-background);color:var(--color-foreground)}button{cursor:pointer}button:disabled{opacity:.45}.seek{display:grid;gap:6px;flex:1 0 100%}input{width:100%;accent-color:var(--color-primary)}button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--color-primary);outline-offset:3px}
</style>
