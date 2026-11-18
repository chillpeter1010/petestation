<template>
  <section class="motion-review" aria-label="Pitcher source landmarks and MotionBERT review">
    <h3>{{ data?.clip.playerName || 'Pitcher' }} · 來源標點 / B · MotionBERT-Lite</h3>
    <nav aria-label="AZ starter reference pilots"><NuxtLink v-for="p in players" :key="p.playerId" :to="{path:'/pitcher-personal',query:{year:2026,team:'AZ',role:'SP',pitcher_id:p.playerId,tab:'in-game'}}" :aria-current="p.playerId===pitcherId?'page':undefined">{{ p.playerName }}</NuxtLink></nav>
    <p v-if="loading" role="status">正在載入此投手的參考標點…</p>
    <p v-else-if="error" role="alert">{{ error }} <button type="button" @click="load">重試</button></p>
    <template v-if="data">
      <p><a :href="data.clip.sourcePage" target="_blank" rel="noopener noreferrer">官方來源 ↗</a> · {{ data.clip.date }} · {{ data.clip.pitchType }} / {{ data.clip.pitchHand }}HP · Game {{ data.clip.gamePk }} / PA {{ data.clip.atBat }} / Pitch {{ data.clip.pitchNumber }}</p>
      <div class="controls">
        <button type="button" @click="play">播放</button><button type="button" @click="pause">暫停</button><button type="button" @click="restart">重播</button>
        <label>速度 <select v-model.number="rate"><option :value=".25">0.25×</option><option :value=".5">0.5×</option><option :value="1">1×</option></select></label>
        <button type="button" @click="resetCamera">重設三維視角</button>
        <label><input v-model="overlay" type="checkbox"> 來源標點</label><label><input v-model="corrected" type="checkbox"> 側別連續性修正</label><label><input v-model="trails" type="checkbox"> 雙踝軌跡</label>
        <label><input v-model="skipLeading" type="checkbox"> 從首個可用骨架開始</label>
      </div>
      <label class="seek">來源時間軸<input :value="time" type="range" min="0" :max="data.sourceDuration" step="0.001" @input="seek(Number(($event.target as HTMLInputElement).value))"></label>
      <p aria-live="polite">{{ time.toFixed(3) }} 秒 · 第 {{ frameIndex+1 }} / {{ data.times.length }} 幀{{ currentPose?'':' · 此段沒有可靠骨架' }}</p>
      <div class="review-columns">
        <section><h4>來源影片＋二維標點</h4><div class="viewport"><video ref="video" :src="`${base}/${pitcherId}/video`" playsinline muted preload="metadata" @loadedmetadata="metadata" @timeupdate="sync" @seeked="sync" @ended="ended" @error="videoFailed" /><canvas ref="sourceCanvas" aria-label="來源投手關節標點" /></div><p>青色 R：解剖右側；橘色 L：解剖左側。缺失／低信心點留空。</p></section>
        <section><h4>B · MotionBERT-Lite · {{ corrected?'側別修正':'原始' }}</h4><div class="viewport"><canvas ref="poseCanvas" tabindex="0" aria-label="三維骨架；拖曳或方向鍵旋轉，滾輪縮放，Home 重設" @pointerdown="dragStart" @pointermove="dragMove" @pointerup="drag=null" @pointercancel="drag=null" @lostpointercapture="drag=null" @wheel.prevent="wheel" @keydown="keys" /></div><p>拖曳旋轉 · 滾輪縮放。三維為相機相對估測，格線不表示實測接地。</p></section>
      </div>
      <details><summary>覆蓋率、挑片與來源方法</summary>
        <p v-if="qualityReport">人物追蹤 {{ percent(qualityReport.current.bodyCoverage) }} · 投球手可見 {{ percent(qualityReport.current.throwingArmCoverage) }} · 雙腳可見 {{ percent(qualityReport.current.feetCoverage) }} · 最長追蹤缺口 {{ qualityReport.current.longestMissingGapSeconds }} 秒。投手人物動作已停用，本區僅保留研究標點。</p>
        <p>指標排除最前／最後未追蹤區間，內部缺口仍列入分母；不是完整投球或正確率。新擷取改掃原片全長，不再固定只看 0.5–8 秒；長遮擋不強補，候選需兼看投球手、雙腳、跳點與動作階段。</p>
        <table v-if="qualityReport"><thead><tr><th>已快取候選</th><th>人物</th><th>投球手</th><th>雙腳</th><th>排序分數</th></tr></thead><tbody><tr v-for="c in qualityReport.candidates" :key="c.clipId+c.tracker"><td>{{ c.clipId }} · {{ c.tracker }}</td><td>{{ percent(c.bodyCoverage) }}</td><td>{{ percent(c.throwingArmCoverage) }}</td><td>{{ percent(c.feetCoverage) }}</td><td>{{ c.score }}</td></tr></tbody></table>
        <p>本片是此投手的獨立研究參考，不是下方所選場次每一球的重建。預訓練 MotionBERT-Lite 使用逐片二維輸入，尚未訓練個人模型。側別修正只重新關聯下肢左右標籤，不移動腳或強制接地；本片 {{ data.sideAssociation.changedSourceSeconds.length }} 幀標籤改變。這些估測不作投手人物動作使用。</p>
      </details>
    </template>
  </section>
</template>
<script setup lang="ts">
import { nearestPose,poseBounds,poseParents,poseColor,drawPose3D,type PitchMotionReview } from '~/utils/pitchMotionReview'
const props=defineProps<{pitcherId:number;heightM?:number|null}>()
const base=`${useRuntimeConfig().public.apiBase}/personal/motion-review`
const data=shallowRef<PitchMotionReview|null>(null),players=ref<{playerId:number;playerName:string}[]>([]),loading=ref(false),error=ref('')
const video=ref<HTMLVideoElement>(),sourceCanvas=ref<HTMLCanvasElement>(),poseCanvas=ref<HTMLCanvasElement>()
const time=ref(0),rate=ref(.5),overlay=ref(true),corrected=ref(true),trails=ref(true)
type Quality={score:number;bodyCoverage:number;throwingArmCoverage:number;feetCoverage:number;longestMissingGapSeconds:number}
const qualityReport=shallowRef<{current:Quality;candidates:(Quality&{clipId:string;tracker:string})[];userAccepted:boolean}|null>(null),skipLeading=ref(true)
const percent=(v:number)=>`${(v*100).toFixed(1)}%`
const camera={yaw:0,pitch:.12,zoom:1};let drag:{x:number;y:number}|null=null,raf=0,version=0,playVersion=0,disposed=false,resize:ResizeObserver|undefined
const frameIndex=computed(()=>data.value?nearestPose(data.value.times,time.value):0)
const sequence=computed(()=>data.value?(corrected.value?data.value.methods.motionbert:data.value.originalMotionbert):[])
const currentPose=computed(()=>sequence.value[frameIndex.value]||null)
const bounds=computed(()=>poseBounds(sequence.value))
const firstPoseTime=computed(()=>{const i=sequence.value.findIndex(f=>f!==null);return i>=0?data.value?.times[i]||0:0})
function size(canvas:HTMLCanvasElement){const ratio=Math.min(devicePixelRatio||1,2);const w=Math.round(canvas.clientWidth*ratio),h=Math.round(canvas.clientHeight*ratio);if(canvas.width!==w)canvas.width=w;if(canvas.height!==h)canvas.height=h}
function draw(){
  const d=data.value,c=sourceCanvas.value,b=poseCanvas.value;if(!d||!c||!b)return
  size(c);size(b);const ctx=c.getContext('2d');if(!ctx)return;ctx.clearRect(0,0,c.width,c.height)
  const p=(corrected.value?d.observed:d.originalObserved)[frameIndex.value]
  if(overlay.value&&p&&!d.filled.includes(frameIndex.value)){
    const s=Math.min(c.width/d.width,c.height/d.height),dx=(c.width-d.width*s)/2,dy=(c.height-d.height*s)/2;ctx.lineWidth=2
    for(let j=0;j<17;j++){const a=p[j]!,parent=poseParents[j]!;if(a[2]!<.65)continue;ctx.fillStyle=poseColor(j);ctx.beginPath();ctx.arc(dx+a[0]!*s,dy+a[1]!*s,3,0,Math.PI*2);ctx.fill();if(parent>=0&&p[parent]![2]!>=.65){ctx.strokeStyle=poseColor(j);ctx.beginPath();ctx.moveTo(dx+a[0]!*s,dy+a[1]!*s);ctx.lineTo(dx+p[parent]![0]!*s,dy+p[parent]![1]!*s);ctx.stroke()}}
  }
  drawPose3D(b,currentPose.value,sequence.value,d.segments,bounds.value,camera,trails.value)
}
function sync(){if(video.value){time.value=video.value.currentTime;draw()}}
function pause(){playVersion++;video.value?.pause();if(raf)cancelAnimationFrame(raf);raf=0}
function tick(){if(disposed||!video.value||video.value.paused||document.hidden){pause();return}sync();raf=requestAnimationFrame(tick)}
async function play(){pause();const token=playVersion,v=video.value;if(!v)return;if(v.ended)v.currentTime=skipLeading.value?firstPoseTime.value:0;if(skipLeading.value&&v.currentTime<firstPoseTime.value)v.currentTime=firstPoseTime.value;v.playbackRate=rate.value;try{await v.play();if(disposed||token!==playVersion)return;raf=requestAnimationFrame(tick)}catch{if(token===playVersion)error.value='影片無法播放，請重試。'}}
function restart(){seek(skipLeading.value?firstPoseTime.value:0);void play()}
function seek(value:number){pause();if(video.value)video.value.currentTime=value;time.value=value;draw()}
function metadata(){if(video.value){video.value.playbackRate=rate.value;if(skipLeading.value)video.value.currentTime=firstPoseTime.value}sync()}
function ended(){pause();sync()}
function videoFailed(){error.value='參考影片暫不可用；下方場次分析仍可使用。'}
function resetCamera(){Object.assign(camera,{yaw:0,pitch:.12,zoom:1});draw()}
function dragStart(e:PointerEvent){if(e.button!==0)return;const c=e.currentTarget as HTMLCanvasElement;c.focus();c.setPointerCapture(e.pointerId);drag={x:e.clientX,y:e.clientY}}
function dragMove(e:PointerEvent){if(!drag)return;camera.yaw+=(e.clientX-drag.x)*.009;camera.pitch=Math.max(-1.35,Math.min(1.35,camera.pitch+(e.clientY-drag.y)*.009));drag={x:e.clientX,y:e.clientY};draw()}
function wheel(e:WheelEvent){camera.zoom=Math.max(.35,Math.min(3,camera.zoom*Math.exp(e.deltaY*.001)));draw()}
function keys(e:KeyboardEvent){if(!['Home','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();if(e.key==='Home')resetCamera();if(e.key==='ArrowLeft')camera.yaw-=.1;if(e.key==='ArrowRight')camera.yaw+=.1;if(e.key==='ArrowUp')camera.pitch=Math.min(1.35,camera.pitch+.1);if(e.key==='ArrowDown')camera.pitch=Math.max(-1.35,camera.pitch-.1);draw()}
async function load(){const token=++version;pause();resize?.disconnect();data.value=null;qualityReport.value=null;time.value=0;error.value='';loading.value=true;try{const [result,quality]=await Promise.all([$fetch<PitchMotionReview>(`${base}/${props.pitcherId}/data`),$fetch<typeof qualityReport.value>(`${base}/${props.pitcherId}/quality`).catch(()=>null)]);if(disposed||token!==version)return;if(result.clip.playerId!==props.pitcherId||!result.times.length)throw new Error('identity mismatch');data.value=result;qualityReport.value=quality;await nextTick();resetCamera();if(sourceCanvas.value)resize?.observe(sourceCanvas.value);if(poseCanvas.value)resize?.observe(poseCanvas.value)}catch{if(!disposed&&token===version)error.value='此投手的參考標點尚未可用；下方場次分析仍可使用。'}finally{if(!disposed&&token===version)loading.value=false}}
function visibility(){if(document.hidden)pause()}
watch([corrected,overlay,trails],()=>draw());watch(rate,v=>{if(video.value)video.value.playbackRate=v})
onMounted(()=>{resize=new ResizeObserver(draw);document.addEventListener('visibilitychange',visibility);void $fetch<{players:{playerId:number;playerName:string}[]}>(`${base}/index`).then(v=>{if(!disposed)players.value=v.players}).catch(()=>{});void load()})
watch(()=>props.pitcherId,()=>void load())
onBeforeUnmount(()=>{disposed=true;version++;pause();resize?.disconnect();document.removeEventListener('visibilitychange',visibility)})
</script>
<style scoped>
.motion-review{border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface);padding:16px;min-width:0;color:var(--color-foreground)}h3{margin:0}h4{margin:8px 0}p{font-size:13px;line-height:1.6}nav,.controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:14px 0}a,a:visited{color:var(--color-foreground)}nav a{border:1px solid var(--color-border);border-radius:6px;padding:5px 9px}nav a[aria-current=page]{border-color:var(--color-primary);color:var(--color-primary)}button,select{font:inherit;min-height:38px;padding:6px 12px;border:1px solid var(--color-border);border-radius:6px;background:var(--color-background);color:var(--color-foreground)}button,summary{cursor:pointer}.seek{display:grid;gap:5px}input[type=range]{width:100%;accent-color:var(--color-primary)}.review-columns{display:grid;grid-template-columns:1fr 1fr;gap:16px}.review-columns>section{min-width:0}details{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:7px;border-bottom:1px solid var(--color-border)}.viewport{position:relative;aspect-ratio:4/3;overflow:hidden;border-radius:8px;background:#0d1823}.viewport video{width:100%;height:100%;object-fit:contain}.viewport canvas{position:absolute;inset:0;width:100%;height:100%;touch-action:none}.viewport canvas[tabindex]{cursor:grab}.viewport canvas:not([tabindex]){pointer-events:none}button:focus-visible,select:focus-visible,canvas:focus-visible,a:focus-visible,input:focus-visible{outline:2px solid var(--color-primary);outline-offset:3px}@media(max-width:850px){.review-columns{grid-template-columns:1fr}}
</style>
