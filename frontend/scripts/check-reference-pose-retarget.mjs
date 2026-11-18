// Real cached B poses -> rig math only. No renderer/browser/image/UI acceptance.
import fs from 'node:fs'
import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import ts from 'typescript'
import * as THREE from 'three'
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js'
globalThis.ProgressEvent ??= class extends Event {constructor(type,init){super(type);Object.assign(this,init)}}
const root=new URL('../../',import.meta.url),read=p=>fs.readFileSync(new URL(p,root),'utf8')
let source=read('frontend/components/charts/replay3d/createReplayActors.ts')
assert.match(source,/PITCHER_DELIVERY_AVAILABLE=false/);assert.match(source,/VIDEO_POSE_RETARGET_AVAILABLE=false/)
source=source.replace("import actorUrl from '~/assets/ballpark/characters3d/actor-base-v1.glb?url'","const actorUrl='unused'")
for(const id of ['three','three/addons/loaders/GLTFLoader.js','three/addons/utils/SkeletonUtils.js'])source=source.replace(`'${id}'`,`'${import.meta.resolve(id)}'`)
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {makeActor,retargetReferencePose}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'))
const util=ts.transpileModule(read('frontend/utils/pitchMotionReview.ts'),{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {referenceBendAxes,referenceRenderSequence}=await import('data:text/javascript;base64,'+Buffer.from(util).toString('base64'))
const bytes=fs.readFileSync(new URL('frontend/assets/ballpark/characters3d/actor-base-v1.glb',root)),length=bytes.readUInt32LE(12),gltf=JSON.parse(bytes.subarray(20,20+length)),bin=bytes.subarray(28+length)
gltf.buffers=[{byteLength:bin.length,uri:'data:application/octet-stream;base64,'+bin.toString('base64')}];delete gltf.images;delete gltf.textures
for(const m of gltf.materials)delete m.pbrMetallicRoughness.baseColorTexture
const asset=await new GLTFLoader().parseAsync(JSON.stringify(gltf),'')
const results=[]
for(const [id,hash] of [[669203,'5a2eb4fbc853a24dc09510fed5f7663f44195e69e165a741243880382e4f1eeb'],[518876,'13696b5889363c289f9453f46b9d64e4ad48b958efb6f0445146b8b2eaabd30b']]){
 const path=`output/ballpark/team-motion-az-v1/${id}-review.json`,text=read(path)
 assert.equal(crypto.createHash('sha256').update(text).digest('hex'),hash,'accepted source data must remain frozen')
 const data=JSON.parse(text),raw=data.methods.motionbert,seq=referenceRenderSequence(raw,data.times),baseline=seq.find(Boolean),actor=makeActor(asset.scene,asset.animations,'pitcher')
 assert.deepEqual(seq.map(p=>p===null),raw.map(p=>p===null),'render filter cannot fill missing gaps')
 const bendAxes=referenceBendAxes(seq,data.times)
 const d=(a,b)=>new THREE.Vector3(...a).distanceTo(new THREE.Vector3(...b))
 const lengths=seq.filter(Boolean).map(p=>(d(p[1],p[2])+d(p[2],p[3])+d(p[4],p[5])+d(p[5],p[6]))/2).sort((a,b)=>a-b),legLengthUnits=lengths[Math.floor(lengths.length/2)]
 const at=i=>{
  actor.root.position.set(0,.254,-60.5*.3048);actor.root.rotation.set(0,0,0);actor.update({hand:'R',team:'AZ',heightM:1.88},'ready',0)
  const input={version:'motionbert_reference_points_v1',playerId:id,points:seq[i],baseline,legLengthUnits,sourceTime:data.times[i],sourceId:data.clip.playId,hand:'R',bendAxes:bendAxes[i]}
  return retargetReferencePose(actor,input)
 }
 const pos=n=>actor.bones.get(n).getWorldPosition(new THREE.Vector3())
 const snapshot=()=>[...actor.root.position.toArray(),...[...actor.bones.values()].flatMap(b=>[...b.position.toArray(),...b.quaternion.toArray()])]
 let samples=0,maxKnee=0,maxDirectionError=0,maxLocalShift=0,minRoot=Infinity,maxRoot=-Infinity,maxFrameTurn=0,maxFrameAt=null,previous=null
 for(let i=0;i<seq.length;i++){
  if(!seq[i]){assert.equal(at(i),false);previous=null;continue}
  assert.equal(at(i),true);samples++
  for(const r of actor.rest){maxLocalShift=Math.max(maxLocalShift,r.bone.position.distanceTo(r.position));assert.ok(Math.abs(r.bone.quaternion.length()-1)<.00001);assert.ok(r.bone.matrixWorld.elements.every(Number.isFinite))}
  const joints=[['thigh_r','calf_r','foot_r',1,2,3],['thigh_l','calf_l','foot_l',4,5,6],['upperarm_r','lowerarm_r','hand_r',14,15,16],['upperarm_l','lowerarm_l','hand_l',11,12,13]]
  for(const [a,b,c,ia,ib,ic] of joints){
   const up=pos(b).sub(pos(a)).normalize(),low=pos(c).sub(pos(b)).normalize(),world=p=>new THREE.Vector3(p[0],-p[1],-p[2])
   const targetUp=world(seq[i][ib]).sub(world(seq[i][ia])).normalize(),targetLow=world(seq[i][ic]).sub(world(seq[i][ib])).normalize()
   maxDirectionError=Math.max(maxDirectionError,up.angleTo(targetUp),low.angleTo(targetLow))
   if(a.startsWith('thigh'))maxKnee=Math.max(maxKnee,up.angleTo(low)*180/Math.PI)
  }
  const quats=['thigh_l','calf_l','thigh_r','calf_r'].map(n=>actor.bones.get(n).getWorldQuaternion(new THREE.Quaternion()))
  if(previous)for(let j=0;j<quats.length;j++){const angle=quats[j].angleTo(previous[j])*180/Math.PI;if(angle>maxFrameTurn){maxFrameTurn=angle;maxFrameAt={frame:i+1,j,angle}}}
  previous=quats;minRoot=Math.min(minRoot,actor.root.position.x);maxRoot=Math.max(maxRoot,actor.root.position.x)
  if(samples%100===0)console.log(id,'math samples',samples)
 }
 assert.ok(maxLocalShift<1e-8,'no bone translation/stretch');assert.ok(maxDirectionError<.0001,'B segment directions must be preserved')
 console.log('largest adjacent turn',maxFrameAt)
 assert.ok(maxFrameTurn<40,'reject sudden leg roll flips before user review')
 assert.ok(maxKnee<145,'source knee flexion limit');assert.ok(maxRoot-minRoot>.15,'observed image-plane root travel must not be pinned')
 const mid=seq.findIndex((p,i)=>p&&i>seq.length/3);at(mid);const first=snapshot();at(mid+10);at(mid-5);at(mid);assert.deepEqual(snapshot(),first,'seek must reset, not accumulate root offsets')
 results.push({playerId:id,samples,maxKneeDeg:maxKnee,maxSegmentDirectionErrorRad:maxDirectionError,maximumLocalBoneTranslation:maxLocalShift,largestAdjacentLegRotationDeg:maxFrameTurn,imagePlaneRootTravelM:maxRoot-minRoot,sourceSha256:hash})
 console.log(JSON.stringify(results.at(-1)))
}
fs.writeFileSync(new URL('data/sample/petehub_b_reference_retarget_v1.json',root),JSON.stringify({version:'b_reference_retarget_v1',date:'2026-11-07',status:'pending_user',mode:'reference_video_pose_estimate',sourceChecks:'pass',visualAcceptance:false,calibratedWorldRoot:false,measuredReleaseAligned:false,results},null,2)+'\n')
