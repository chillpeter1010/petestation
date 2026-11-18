export type PoseFrame = number[][] | null
export const teamMotionPitcherIds=[593958,518876,694297,669194,683352,684442,703615,669203]
export type PitchMotionReview = {
  clip: { playerId:number;playerName:string;year:number;date:string;pitchType:string;pitchHand:string;sourcePage:string;playId:string;gamePk:number;atBat:number;pitchNumber:number }
  times:number[];width:number;height:number;sourceDuration:number;observed:PoseFrame[];originalObserved:PoseFrame[];originalMotionbert:PoseFrame[]
  methods:{motionbert:PoseFrame[]};filled:number[];segments:{first:number;last:number}[];sideAssociation:{changedSourceSeconds:number[]}
}
export const poseParents=[-1,0,1,2,0,4,5,0,7,8,9,8,11,12,8,14,15]
export const poseColor=(j:number)=>[1,2,3,14,15,16].includes(j)?'#58dcff':[4,5,6,11,12,13].includes(j)?'#ffb368':'#edf3f8'
// Symmetric, render-only denoising. No timestamps changed or missing gaps filled;
// raw B and its displayed skeleton remain untouched for comparison.
export function referenceRenderSequence(sequence:PoseFrame[],times?:number[]):PoseFrame[]{
  const weights=[1,2,3,4,3,2,1]
  const smooth=sequence.map((frame,i)=>{
    if(!frame)return null
    let lo=i,hi=i;while(lo>Math.max(0,i-3)&&sequence[lo-1])lo--;while(hi<Math.min(sequence.length-1,i+3)&&sequence[hi+1])hi++
    const total=weights.slice(lo-i+3,hi-i+4).reduce((a,b)=>a+b,0)
    return frame.map((point,j)=>point.map((_,k)=>{let sum=0;for(let t=lo;t<=hi;t++)sum+=sequence[t]![j]![k]!*weights[t-i+3]!;return sum/total}))
  })
  const mix=(a:number[],b:number[],t:number)=>{
    const angle=Math.acos(Math.max(-1,Math.min(1,dot(a,b)))),sin=Math.sin(angle)
    if(angle<1e-6)return b
    if(Math.abs(sin)<1e-6)return norm(a.map((v,k)=>v*(1-t)+b[k]!*t))
    return norm(a.map((v,k)=>(v*Math.sin((1-t)*angle)+b[k]!*Math.sin(t*angle))/sin))
  }
  let previous:(number[]|null)[]=Array(8).fill(null)
  return smooth.map((frame,i)=>{
    if(!frame){previous=Array(8).fill(null);return null}
    const out=frame.map(p=>[...p]),chains=[[4,5,6],[11,12,13],[1,2,3],[14,15,16]]
    const dt=i&&times?Math.max(1/240,Math.min(.1,times[i]!-times[i-1]!)):1/60
    chains.forEach(([a,b,c],j)=>{
      const vectors=[sub(frame[b!]!,frame[a!]!),sub(frame[c!]!,frame[b!]!)]
      const dirs=vectors.map((value,link)=>{
        let dir=norm(value);const old=previous[j*2+link]
        if(old){const angle=Math.acos(Math.max(-1,Math.min(1,dot(old,dir)))),limit=(j%2===0?10:30)*dt;if(angle>limit)dir=mix(old,dir,limit/angle)}
        return dir
      })
      const bend=Math.acos(Math.max(-1,Math.min(1,dot(dirs[0]!,dirs[1]!)))),max=(j%2===0?140:175)*Math.PI/180
      if(bend>max)dirs[1]=mix(dirs[0]!,dirs[1]!,max/bend)
      previous[j*2]=dirs[0]!;previous[j*2+1]=dirs[1]!
      out[b!]=out[a!]!.map((v,k)=>v+dirs[0]![k]!*Math.hypot(...vectors[0]!))
      out[c!]=out[b!]!.map((v,k)=>v+dirs[1]![k]!*Math.hypot(...vectors[1]!))
    })
    return out
  })
}
export function nearestPose(times:number[],t:number){let a=0,b=times.length-1;while(a<b){const m=(a+b)>>1;if(times[m]!<t)a=m+1;else b=m}return a>0&&Math.abs(times[a-1]!-t)<Math.abs(times[a]!-t)?a-1:a}
const world=(p:number[])=>[p[0]!,-p[1]!,-p[2]!]
const sub=(a:number[],b:number[])=>a.map((v,i)=>v-b[i]!)
const dot=(a:number[],b:number[])=>a.reduce((s,v,i)=>s+v*b[i]!,0)
const cross=(a:number[],b:number[])=>[a[1]!*b[2]!-a[2]!*b[1]!,a[2]!*b[0]!-a[0]!*b[2]!,a[0]!*b[1]!-a[1]!*b[0]!]
const norm=(a:number[])=>{const d=Math.hypot(...a)||1;return a.map(v=>v/d)}
// Derived render roll axes only. Preserve anatomical segment directions and
// reset at gaps; no source-point editing or frame-order dependent runtime state.
export function referenceBendAxes(sequence:PoseFrame[],times?:number[]){
  let previous:(number[]|null)[]=Array(8).fill(null)
  const chains=[[4,5,6],[11,12,13],[1,2,3],[14,15,16]]
  return sequence.map((points,index)=>{
    if(!points){previous=Array(8).fill(null);return null}
    const p=points.map(world),body=norm(sub(p[4]!,p[1]!))
    return chains.flatMap(([a,b,c],j)=>{
      const upper=norm(sub(p[b!]!,p[a!]!)),lower=norm(sub(p[c!]!,p[b!]!)),normal=cross(upper,lower)
      return [upper,lower].map((up,link)=>{
      const slot=j*2+link,old=previous[slot]||body
      let axis=normal
      if(Math.hypot(...axis)<.15)axis=old.map((v,k)=>v-up[k]!*dot(old,up))
      if(Math.hypot(...axis)<1e-5)axis=cross(up,[0,0,1])
      axis=norm(axis);if(dot(axis,old)<0)axis=axis.map(v=>-v)
      const transported=norm(old.map((v,k)=>v-up[k]!*dot(old,up)))
      if(Math.hypot(...transported)>.9){
        const angle=Math.atan2(dot(up,cross(transported,axis)),dot(transported,axis))
        const dt=index&&times?Math.max(1/240,Math.min(.1,times[index]!-times[index-1]!)):1/60
        const limit=(j%2===0?5:10)*dt,turn=Math.max(-limit,Math.min(limit,angle))
        const tangent=cross(up,transported)
        axis=norm(transported.map((v,k)=>v*Math.cos(turn)+tangent[k]!*Math.sin(turn)))
      }
      previous[slot]=axis;return axis
      })
    })
  })
}
export function poseBounds(sequence:PoseFrame[]){
  const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity]
  for(const frame of sequence)if(frame)for(const p of frame.map(world))for(let k=0;k<3;k++){lo[k]=Math.min(lo[k]!,p[k]!);hi[k]=Math.max(hi[k]!,p[k]!)}
  return Number.isFinite(lo[0])?{centre:lo.map((v,k)=>(v+hi[k]!)/2),radius:Math.max(1,...hi.map((v,k)=>v-lo[k]!))*1.9,floor:lo[1]!}:{centre:[0,0,0],radius:3,floor:0}
}
export function drawPose3D(c:HTMLCanvasElement,frame:PoseFrame,seq:PoseFrame[],segments:PitchMotionReview['segments'],bounds:ReturnType<typeof poseBounds>,camera:{yaw:number;pitch:number;zoom:number},trails:boolean,sourceConfidence?:number[]){
  const ctx=c.getContext('2d');if(!ctx)return;const w=c.width,h=c.height;ctx.fillStyle='#0d1823';ctx.fillRect(0,0,w,h)
  if(!frame){ctx.fillStyle='#ffd58c';ctx.font='16px system-ui';ctx.fillText('此段追蹤缺失，影片繼續播放',18,34);return}
  const {centre,radius,floor}=bounds,{yaw,pitch,zoom}=camera,d=radius*zoom
  const cp=centre.map((v,k)=>v+[d*Math.sin(yaw)*Math.cos(pitch),d*Math.sin(pitch),d*Math.cos(yaw)*Math.cos(pitch)][k]!),f=norm(sub(centre,cp)),r=norm(cross(f,[0,1,0])),u=cross(r,f)
  const project=(p:number[])=>{const v=sub(p,cp),z=dot(v,f);return z>.01?[w/2+dot(v,r)*h*.95/z,h/2-dot(v,u)*h*.95/z,z]:null}
  const line=(a:number[],b:number[],color:string,width=2,dashed=false)=>{const p=project(a),q=project(b);if(!p||!q)return;ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dashed?[3,3]:[]);ctx.beginPath();ctx.moveTo(p[0]!,p[1]!);ctx.lineTo(q[0]!,q[1]!);ctx.stroke();ctx.setLineDash([])}
  for(let k=-4;k<=4;k++){const n=k*.25;line([centre[0]!+n,floor,centre[2]!-1],[centre[0]!+n,floor,centre[2]!+1],'#2b3e4b',1);line([centre[0]!-1,floor,centre[2]!+n],[centre[0]!+1,floor,centre[2]!+n],'#2b3e4b',1)}
  if(trails)for(const j of [3,6])for(const s of segments)for(let t=s.first+1;t<=s.last;t++){const a=seq[t-1],b=seq[t];if(a&&b)line(world(a[j]!),world(b[j]!),j===3?'#23748a':'#875d31',1,true)}
  const p=frame.map(world),sorted=p.map((v,j)=>({j,q:project(v)})).filter(v=>v.q).sort((a,b)=>b.q![2]!-a.q![2]!)
  for(const {j} of sorted)if(poseParents[j]!>=0){const uncertain=sourceConfidence&&(sourceConfidence[j]!<.65||sourceConfidence[poseParents[j]!]!<.65);line(p[j]!,p[poseParents[j]!]!,uncertain?'#82909c':poseColor(j),uncertain?2:4,!!uncertain)}
  for(const {j,q} of sorted){ctx.fillStyle=sourceConfidence&&sourceConfidence[j]!<.65?'#82909c':poseColor(j);ctx.beginPath();ctx.arc(q![0]!,q![1]!,4,0,Math.PI*2);ctx.fill();if(j===3||j===6){ctx.font='bold 13px system-ui';ctx.fillText(j===3?'R':'L',q![0]!+7,q![1]!-5)}}
}
