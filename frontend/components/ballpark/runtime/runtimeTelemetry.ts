// Bounded, user-initiated samples. These counters describe our instances, not GPU/global leaks.
export const runtimeLifecycle={created:0,destroyRequested:0,destroyed:0}
export function lifecycleSnapshot(){return {...runtimeLifecycle,live:runtimeLifecycle.created-runtimeLifecycle.destroyed}}
export function summarizeFrames(frames:number[],moving:number){
  const sorted=frames.filter(n=>Number.isFinite(n)&&n>0).sort((a,b)=>a-b)
  const percentile=(p:number)=>sorted.length?sorted[Math.min(sorted.length-1,Math.ceil(sorted.length*p)-1)]!:null
  const p95=percentile(.95),median=percentile(.5)
  return {sample_count:sorted.length,moving_samples:moving,median_ms:median,p95_ms:p95,approximate_fps:sorted.length?1000*sorted.length/sorted.reduce((a,b)=>a+b,0):null,long_frames_over_33ms:sorted.filter(n=>n>33.3).length,
    interpretation:moving<60?'limited_insufficient_walking_samples':p95!==null&&p95>33.3?'offer_classic_fallback':'local_sample_only_not_release_certification'}
}
export function createFrameRecorder(){
  let started:number|null=null,last:number|null=null,moving=0,frames:number[]=[]
  return {
    start(now:number){started=now;last=null;moving=0;frames=[]},
    sample(now:number,active:boolean,isMoving:boolean){
      if(started===null)return
      if(!active){last=null;return}
      if(last!==null && frames.length<3600){frames.push(now-last);if(isMoving)moving++}
      last=now
    },
    finish(now:number){if(started===null)return null;const elapsed=Math.max(0,now-started);started=null;return {elapsed_ms:elapsed,...summarizeFrames(frames,moving),raw_frame_ms:[...frames]}},
    cancel(){started=null;last=null;frames=[]}
  }
}
