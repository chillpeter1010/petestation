<template>
  <section class="swing-review" aria-label="Geraldo Perdomo swing landmark pilot">
    <h3>Geraldo Perdomo · 揮棒標點試作</h3>
    <div class="controls"><label>實際打擊側 <select v-model="stand"><option value="L">左打 LHB</option><option value="R">右打 RHB</option></select></label><button type="button" @click="play">播放</button><button type="button" @click="pause">暫停</button><button type="button" @click="restart">重播</button><label>速度 <select v-model.number="rate"><option :value=".25">0.25×</option><option :value=".5">0.5×</option><option :value="1">1×</option></select></label><button type="button" @click="reset">重設 B 視角</button><label><input v-model="overlay" type="checkbox"> 來源標點</label></div>
    <p v-if="loading" role="status">載入揮棒參考…</p><p v-if="error" role="alert">{{ error }} <button type="button" @click="load">重試</button></p>
    <template v-if="data">
      <p><a :href="data.clip.sourcePage" target="_blank" rel="noopener noreferrer">官方來源 ↗</a> · {{ data.clip.date }} · {{ data.clip.stand }}HB · Game {{ data.clip.gamePk }} / PA {{ data.clip.atBat }} / Pitch {{ data.clip.pitchNumber }}</p>
      <label class="seek">來源時間軸<input :value="time" type="range" min="0" :max="data.sourceDuration" step="0.001" @input="seek(Number(($event.target as HTMLInputElement).value))"></label>
      <p>{{ time.toFixed(3) }} 秒 · 第 {{ index+1 }} / {{ data.times.length }} 幀{{ pose?'':' · 此段沒有可靠人體骨架' }}</p>
      <div class="columns">
        <section><h4>來源影片＋人體標點</h4><div class="viewport"><video ref="video" :src="`${base}/${stand}/video`" playsinline muted preload="metadata" @loadedmetadata="metadata" @timeupdate="sync" @seeked="sync" @ended="pause" @error="error='來源影片暫不可用。'" /><canvas ref="sourceCanvas" /></div></section>
        <section><h4>B · MotionBERT-Lite 人體估測</h4><div class="viewport"><canvas ref="poseCanvas" tabindex="0" aria-label="B 人體骨架；拖曳旋轉，滾輪縮放，方向鍵或 Home" @pointerdown="down" @pointermove="move" @pointerup="drag=null" @pointercancel="drag=null" @lostpointercapture="drag=null" @wheel.prevent="wheel" @keydown="keys" /></div></section>
      </div>
      <p>青色 R：解剖右側；橘色 L：解剖左側。來源低信心點留空；B 灰色虛線為來源低信心關節的模型估測，缺失影格不顯示骨架。</p>
      <p>分析區間 {{ data.quality.analysisWindow.join('–') }} 秒：人物 {{ percent(data.quality.bodyCoverage) }}，雙肘／雙腕 {{ percent(data.quality.bothWristsCoverage) }}。遮擋仍多，這是供你驗標點的候選，不是完整揮棒重建。</p>
      <details><summary>來源與資料限制</summary><p>可見率以整個明列分析區間為分母，包含缺口；不表示揮棒正確率。影片保留完整時間軸，開場切鏡與分析區間外不標點。這是獨立參考影片，不是下方所選球的動作，尚未套入人物。</p><p>本球 Statcast bat speed：{{ data.clip.sourceBatSpeedMph ?? 'unavailable' }} mph；swing length：{{ data.clip.sourceSwingLengthFt ?? 'unavailable' }} ft。兩者是逐次揮棒摘要，不能還原棒頭／棒柄逐幀座標。這批只有人體點，不畫虛構的球棒軌跡或觸球時間。相機相對深度、腳步與人物身分由你驗收。</p></details>
    </template>
  </section>
</template>
<script setup lang="ts">
import { nearestPose,poseBounds,poseParents,poseColor,drawPose3D,type PitchMotionReview } from '~/utils/pitchMotionReview'
type SwingData=Pick<PitchMotionReview,'times'|'width'|'height'|'sourceDuration'|'observed'|'methods'|'filled'|'segments'>&{clip:PitchMotionReview['clip']&{stand:'L'|'R';sourceBatSpeedMph:number|null;sourceSwingLengthFt:number|null};quality:{bodyCoverage:number;bothWristsCoverage:number;analysisWindow:number[]}}
const base=`${useRuntimeConfig().public.apiBase}/personal/motion-review/batter/672695`
const stand=ref<'L'|'R'>('L'),rate=ref(.5),time=ref(0),overlay=ref(true),loading=ref(false),error=ref(''),data=shallowRef<SwingData|null>(null)
const video=ref<HTMLVideoElement>(),sourceCanvas=ref<HTMLCanvasElement>(),poseCanvas=ref<HTMLCanvasElement>()
const camera={yaw:0,pitch:.12,zoom:1};let drag:{x:number;y:number}|null=null,raf=0,token=0,playToken=0,disposed=false,observer:ResizeObserver|undefined
const index=computed(()=>data.value?nearestPose(data.value.times,time.value):0),sequence=computed(()=>data.value?.methods.motionbert||[]),pose=computed(()=>data.value?.filled.includes(index.value)?null:sequence.value[index.value]||null),bounds=computed(()=>poseBounds(sequence.value))
const percent=(v:number)=>`${(v*100).toFixed(1)}%`
const firstTime=computed(()=>{const i=sequence.value.findIndex(Boolean);return i>=0?data.value?.times[i]||0:0})
function size(c:HTMLCanvasElement){const d=Math.min(devicePixelRatio||1,2),w=Math.round(c.clientWidth*d),h=Math.round(c.clientHeight*d);if(c.width!==w)c.width=w;if(c.height!==h)c.height=h}
function draw(){const d=data.value,c=sourceCanvas.value,b=poseCanvas.value;if(!d||!c||!b)return;size(c);size(b);const ctx=c.getContext('2d');if(!ctx)return;ctx.clearRect(0,0,c.width,c.height);const p=d.observed[index.value]
 if(overlay.value&&p&&!d.filled.includes(index.value)){const s=Math.min(c.width/d.width,c.height/d.height),dx=(c.width-d.width*s)/2,dy=(c.height-d.height*s)/2;ctx.lineWidth=2;for(let j=0;j<17;j++){const a=p[j]!,parent=poseParents[j]!;if(a[2]!<.65)continue;ctx.fillStyle=poseColor(j);ctx.beginPath();ctx.arc(dx+a[0]!*s,dy+a[1]!*s,3,0,Math.PI*2);ctx.fill();if(parent>=0&&p[parent]![2]!>=.65){ctx.strokeStyle=poseColor(j);ctx.beginPath();ctx.moveTo(dx+a[0]!*s,dy+a[1]!*s);ctx.lineTo(dx+p[parent]![0]!*s,dy+p[parent]![1]!*s);ctx.stroke()}}}
 drawPose3D(b,pose.value,sequence.value,d.segments,bounds.value,camera,false,p?.map(j=>j[2]??0))
}
function pause(){playToken++;video.value?.pause();if(raf)cancelAnimationFrame(raf);raf=0}
function sync(){if(video.value){time.value=video.value.currentTime;draw()}}
function tick(){if(disposed||document.hidden||!video.value||video.value.paused){pause();return}sync();raf=requestAnimationFrame(tick)}
async function play(){pause();const current=playToken,v=video.value;if(!v)return;if(v.ended||v.currentTime<firstTime.value)v.currentTime=firstTime.value;v.playbackRate=rate.value;try{await v.play();if(!disposed&&current===playToken)raf=requestAnimationFrame(tick)}catch{if(current===playToken)error.value='影片暫時無法播放。'}}
function seek(value:number){pause();if(video.value)video.value.currentTime=value;time.value=value;draw()}
function restart(){seek(firstTime.value);void play()}
function metadata(){if(video.value){video.value.currentTime=firstTime.value;video.value.playbackRate=rate.value}sync()}
function reset(){Object.assign(camera,{yaw:0,pitch:.12,zoom:1});draw()}
function down(e:PointerEvent){if(e.button!==0)return;const c=e.currentTarget as HTMLCanvasElement;c.focus();c.setPointerCapture(e.pointerId);drag={x:e.clientX,y:e.clientY}}
function move(e:PointerEvent){if(!drag)return;camera.yaw+=(e.clientX-drag.x)*.009;camera.pitch=Math.max(-1.35,Math.min(1.35,camera.pitch+(e.clientY-drag.y)*.009));drag={x:e.clientX,y:e.clientY};draw()}
function wheel(e:WheelEvent){camera.zoom=Math.max(.35,Math.min(3,camera.zoom*Math.exp(e.deltaY*.001)));draw()}
function keys(e:KeyboardEvent){if(!['Home','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();if(e.key==='Home')reset();if(e.key==='ArrowLeft')camera.yaw-=.1;if(e.key==='ArrowRight')camera.yaw+=.1;if(e.key==='ArrowUp')camera.pitch=Math.min(1.35,camera.pitch+.1);if(e.key==='ArrowDown')camera.pitch=Math.max(-1.35,camera.pitch-.1);draw()}
async function load(){const current=++token;pause();observer?.disconnect();data.value=null;error.value='';loading.value=true;time.value=0;try{const value=await $fetch<SwingData>(`${base}/${stand.value}/data`);if(disposed||current!==token)return;if(value.clip.playerId!==672695||value.clip.stand!==stand.value)throw new Error('Source identity mismatch');data.value=value;await nextTick();reset();if(sourceCanvas.value)observer?.observe(sourceCanvas.value);if(poseCanvas.value)observer?.observe(poseCanvas.value)}catch{if(!disposed&&current===token)error.value='這個打擊側的參考資料尚不可用。'}finally{if(!disposed&&current===token)loading.value=false}}
function hidden(){if(document.hidden)pause()}
watch(stand,()=>void load());watch(overlay,draw);watch(rate,v=>{if(video.value)video.value.playbackRate=v})
onMounted(()=>{observer=new ResizeObserver(draw);document.addEventListener('visibilitychange',hidden);void load()})
onBeforeUnmount(()=>{disposed=true;token++;pause();observer?.disconnect();document.removeEventListener('visibilitychange',hidden)})
</script>
<style scoped>
.swing-review{border:1px solid var(--color-border);border-radius:10px;padding:14px;min-width:0;background:var(--color-surface);color:var(--color-foreground)}h3{margin:0}h4{margin:9px 0}p{font-size:13px;line-height:1.6}a,a:visited{color:var(--color-foreground)}.controls{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:12px 0}button,select{padding:7px 12px;min-height:38px;font:inherit;color:inherit;background:var(--color-background);border:1px solid var(--color-border);border-radius:6px}button,summary{cursor:pointer}.seek{display:grid;gap:5px}.seek input{width:100%;accent-color:var(--color-primary)}.columns{display:grid;grid-template-columns:1fr 1fr;gap:14px}.columns>section{min-width:0}.viewport{position:relative;aspect-ratio:4/3;background:#0d1823;overflow:hidden;border-radius:8px}.viewport video{width:100%;height:100%;object-fit:contain}.viewport canvas{position:absolute;inset:0;width:100%;height:100%;touch-action:none}.viewport canvas:not([tabindex]){pointer-events:none}button:focus-visible,select:focus-visible,canvas:focus-visible,input:focus-visible{outline:2px solid var(--color-primary);outline-offset:3px}@media(max-width:850px){.columns{grid-template-columns:1fr}}
</style>
