// Offline retargeting only. Never constructs a renderer, DOM or browser.
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import * as THREE from 'three'
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js'
globalThis.ProgressEvent ??= class extends Event {constructor(type,init){super(type);Object.assign(this,init)}}
const root=path.resolve(import.meta.dirname,'../..'),source=path.join(root,'output/ballpark/f2-motion-reference-v1'),dest=path.join(root,'frontend/assets/ballpark/motion')
fs.mkdirSync(dest,{recursive:true})
const bytes=fs.readFileSync(path.join(root,'frontend/assets/ballpark/characters3d/actor-base-v1.glb')),length=bytes.readUInt32LE(12),gltf=JSON.parse(bytes.subarray(20,20+length)),bin=bytes.subarray(28+length)
gltf.buffers=[{byteLength:bin.length,uri:'data:application/octet-stream;base64,'+bin.toString('base64')}];delete gltf.images;delete gltf.textures
for(const m of gltf.materials)delete m.pbrMetallicRoughness.baseColorTexture
const asset=await new GLTFLoader().parseAsync(JSON.stringify(gltf),'');asset.scene.updateMatrixWorld(true)
const bones=new Map();asset.scene.traverse(o=>{if(o.isBone)bones.set(o.name,o)})
const rest=new Map([...bones].map(([name,b])=>[name,{p:b.position.clone(),q:b.quaternion.clone(),worldQ:b.getWorldQuaternion(new THREE.Quaternion()),worldP:b.getWorldPosition(new THREE.Vector3())}]))
const V=a=>new THREE.Vector3(...a),up=new THREE.Vector3(0,1,0),round=a=>a.map(v=>Number(v.toFixed(6)))
const point=n=>bones.get(n).getWorldPosition(new THREE.Vector3())
function basis(right,vertical){
  const y=vertical.clone().normalize(),x=right.clone().addScaledVector(y,-right.dot(y)).normalize(),z=x.clone().cross(y).normalize()
  return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x,y,z))
}
function limbBasis(direction,axis){const y=direction.clone().negate().normalize();return basis(axis,y)}
function setWorld(name,q){const b=bones.get(name);b.quaternion.copy(b.parent.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(q));asset.scene.updateMatrixWorld(true)}
const torsoRest=basis(point('upperarm_l').sub(point('upperarm_r')),point('spine_03').sub(point('pelvis')))
const hipRest=basis(point('thigh_l').sub(point('thigh_r')),point('spine_03').sub(point('pelvis')))
const driven=['pelvis','spine_01','spine_02','spine_03','Head',...['l','r'].flatMap(s=>['upperarm','lowerarm','hand','thigh','calf','foot'].map(n=>`${n}_${s}`))]
const hash=b=>crypto.createHash('sha256').update(b).digest('hex')
const sourceMeta=JSON.parse(fs.readFileSync(path.join(source,'metadata.json'),'utf8'))
const summaries=[]
for(const [name,playerId,plantTime,releaseTime] of [['yesavage',702056,2.74,2.88],['thompson',657044,2.62,2.77]]){
  const inputBytes=fs.readFileSync(path.join(source,`${name}-pose.json`)),raw=JSON.parse(inputBytes),valid=raw.frames.map((f,i)=>f.landmarks.length?i:-1).filter(i=>i>=0)
  const frames=raw.frames.map((f,i)=>{
    const index=f.landmarks.length?i:valid.reduce((a,b)=>Math.abs(b-i)<Math.abs(a-i)?b:a)
    return {source:f,points:raw.frames[index].landmarks.map(p=>new THREE.Vector3(-p.estimated_hip_relative_m[0],-p.estimated_hip_relative_m[1],p.estimated_hip_relative_m[2]))}
  })
  // Weighted temporal filtering of predictions; raw observations stay untouched.
  const smooth=frames.map((f,i)=>f.points.map((_,j)=>{
    const sum=new THREE.Vector3();let total=0
    for(let k=Math.max(0,i-2);k<=Math.min(frames.length-1,i+2);k++){
      const detection=frames[k].source.landmarks[j],confidence=detection?Math.min(detection.visibility,detection.presence):.05
      const w=Math.exp(-((k-i)**2)/3)*(.05+confidence*confidence);sum.addScaledVector(frames[k].points[j],w);total+=w
    }
    return sum.divideScalar(total)
  }))
  // Camera yaw is an estimated set-position prior (RHP lead side toward plate),
  // not solved broadcast camera extrinsics or measured field coordinates.
  const line=smooth.slice(0,6).reduce((v,p)=>v.add(p[23].clone().sub(p[24])),new THREE.Vector3())
  const yaw=-Math.atan2(line.x,line.z),cameraQ=new THREE.Quaternion().setFromAxisAngle(up,yaw)
  const rows=[];let previousQ=null,previousRoot=null
  for(let i=0;i<frames.length;i++){
    for(const [n,b] of bones){b.position.copy(rest.get(n).p);b.quaternion.copy(rest.get(n).q)}
    asset.scene.updateMatrixWorld(true)
    const p=smooth[i].map(v=>v.clone().applyQuaternion(cameraQ)),hip=p[23].clone().add(p[24]).multiplyScalar(.5),shoulder=p[11].clone().add(p[12]).multiplyScalar(.5)
    const right=p[23].clone().sub(p[24]).normalize(),hipQ=basis(right,up),chestQ=basis(p[11].clone().sub(p[12]),shoulder.clone().sub(hip))
    setWorld('pelvis',hipQ.clone().multiply(hipRest.clone().invert()).multiply(rest.get('pelvis').worldQ))
    for(const [n,t] of [['spine_01',.3],['spine_02',.65],['spine_03',1]])setWorld(n,hipQ.clone().slerp(chestQ,t).multiply(torsoRest.clone().invert()).multiply(rest.get(n).worldQ))
    const fieldRight=new THREE.Vector3(1,0,0).applyQuaternion(hipQ)
    for(const [s,h,k,a,heel,toe] of [['l',23,25,27,29,31],['r',24,26,28,30,32]]){
      const thigh=p[k].clone().sub(p[h]).normalize(),lower=p[a].clone().sub(p[k]).normalize()
      const hinge=fieldRight.clone().addScaledVector(thigh,-fieldRight.dot(thigh)).normalize()
      const flex=THREE.MathUtils.clamp(Math.acos(THREE.MathUtils.clamp(thigh.dot(lower),-1,1)),0,145*Math.PI/180)
      const calf=thigh.clone().applyAxisAngle(hinge,flex)
      for(const [n,child,d] of [[`thigh_${s}`,`calf_${s}`,thigh],[`calf_${s}`,`foot_${s}`,calf]]){
        const original=rest.get(child).worldP.clone().sub(rest.get(n).worldP)
        const restFrame=limbBasis(original,new THREE.Vector3(1,0,0))
        setWorld(n,limbBasis(d,hinge).multiply(restFrame.invert()).multiply(rest.get(n).worldQ))
      }
      const toeDirection=p[toe].clone().sub(p[heel]).normalize()
      const planted=(s==='r'&&frames[i].source.source_time_seconds<releaseTime)||(s==='l'&&frames[i].source.source_time_seconds>=plantTime)
      const footYaw=Math.atan2(toeDirection.x,toeDirection.z),pitch=planted?0:THREE.MathUtils.clamp(Math.asin(toeDirection.y),-Math.PI/3,Math.PI/3)
      const footQ=new THREE.Quaternion().setFromEuler(new THREE.Euler(-pitch,footYaw,0,'YXZ'))
      setWorld(`foot_${s}`,footQ.multiply(rest.get(`foot_${s}`).worldQ))
    }
    for(const [s,sh,el,wr] of [['l',11,13,15],['r',12,14,16]]){
      for(const [n,child,d] of [[`upperarm_${s}`,`lowerarm_${s}`,p[el].clone().sub(p[sh])],[`lowerarm_${s}`,`hand_${s}`,p[wr].clone().sub(p[el])]]){
        const from=point(child).sub(point(n)).normalize(),q=new THREE.Quaternion().setFromUnitVectors(from,d.normalize())
        setWorld(n,q.multiply(bones.get(n).getWorldQuaternion(new THREE.Quaternion())))
      }
    }
    setWorld('Head',rest.get('Head').worldQ.clone())
    const quaternions=driven.map((n,j)=>{
      const q=bones.get(n).quaternion.clone()
      if(previousQ&&q.dot(previousQ[j])<0)q.set(-q.x,-q.y,-q.z,-q.w)
      return q
    })
    previousQ=quaternions
    rows.push({sourceTime:frames[i].source.source_time_seconds,rotations:quaternions.flatMap(q=>round(q.toArray())),feet:{l:point('foot_l').toArray(),r:point('foot_r').toArray()},uncertain:frames[i].source.landmarks.filter(p=>Math.min(p.visibility,p.presence)<.65).map(p=>p.id),filled:!frames[i].source.landmarks.length})
  }
  const drive=rest.get('foot_r').worldP,lead=rest.get('foot_l').worldP,plantIndex=rows.reduce((a,r,i)=>Math.abs(r.sourceTime-plantTime)<Math.abs(rows[a].sourceTime-plantTime)?i:a,0)
  const rootAtPlant=drive.clone().sub(V(rows[plantIndex].feet.r)),leadAnchor=rootAtPlant.add(V(rows[plantIndex].feet.l));leadAnchor.y=lead.y
  let maxRootStep=0
  for(const row of rows){
    const a=drive.clone().sub(V(row.feet.r)),b=leadAnchor.clone().sub(V(row.feet.l)),t=THREE.MathUtils.smoothstep(row.sourceTime,plantTime-.10,plantTime+.10)
    const translation=a.lerp(b,t)
    if(previousRoot){const step=translation.clone().sub(previousRoot),length=step.length();if(length>.12)translation.copy(previousRoot).addScaledVector(step,.12/length);maxRootStep=Math.max(maxRootStep,translation.distanceTo(previousRoot))}
    previousRoot=translation.clone();row.root=round(translation.toArray());delete row.feet
  }
  const meta=sourceMeta.find(m=>m.name===name)
  const clip={version:'video_pose_rig_pilot_v1',id:`${name}-video-pose-v1`,playerId,playerName:name==='yesavage'?'Trey Yesavage':'Ryan Thompson',date:name==='yesavage'?'2025-10-05':'2025-05-09',playId:meta.play_id,sourceUrl:meta.page,sourcePoseSha256:hash(inputBytes),sourceStart:rows[0].sourceTime,sourceEnd:rows.at(-1).sourceTime,releaseSourceTime:releaseTime,plantSourceTime:plantTime,boneNames:driven,frames:rows,calibration:'estimated yaw from closed set; hip-relative monocular predictions; NOT measured field camera or exact release alignment',constraints:'fixed rig bone lengths; knee hinge 0-145deg with pelvis-aligned axis; planted foot flattened; temporal weighted filtering; root step bound .12 model units/sample',fallback:'low-confidence predictions retained/flagged; one missing source frame uses nearest observed estimate; no new training',visualStatus:'pending_user',previewOnly:true}
  const json=JSON.stringify(clip);fs.writeFileSync(path.join(dest,`${name}-video-pose-v1.json`),json+'\n')
  summaries.push({name,playerId,bytes:Buffer.byteLength(json)+1,frames:rows.length,sha256:hash(json+'\n'),maximumRootStep:maxRootStep})
}
fs.writeFileSync(path.join(root,'data/sample/petehub_video_pose_retarget_pilot_v1.json'),JSON.stringify({status:'pending_user',builder:'frontend/scripts/build-pitch-video-poses.mjs',clips:summaries,notMeasured3DMocap:true,scope:'Personal-only isolated reference preview; never applied to another game pitch'},null,2)+'\n')
console.log(JSON.stringify(summaries))
