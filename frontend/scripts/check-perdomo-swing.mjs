// Source-data/rig math only; no renderer/browser or visual acceptance.
import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'
import * as THREE from 'three'
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js'
globalThis.ProgressEvent??=class extends Event{constructor(type,init){super(type);Object.assign(this,init)}}
const root=new URL('../../',import.meta.url),read=p=>fs.readFileSync(new URL(p,root),'utf8')
const moduleUrl=source=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64')
let source=read('frontend/components/charts/replay3d/createReplayActors.ts')
for(const flag of ['PITCHER_ACTOR_AVAILABLE','PITCHER_DELIVERY_AVAILABLE','VIDEO_POSE_RETARGET_AVAILABLE','REFERENCE_B_RETARGET_AVAILABLE'])assert.match(source,new RegExp(flag+'=false'))
source=source.replace("import actorUrl from '~/assets/ballpark/characters3d/actor-base-v1.glb?url'","const actorUrl='unused'")
for(const name of ['three','three/addons/loaders/GLTFLoader.js','three/addons/utils/SkeletonUtils.js'])source=source.replace(`'${name}'`,`'${import.meta.resolve(name)}'`)
const {makeActor,retargetReferencePose}=await import(moduleUrl(source))
const utils=moduleUrl(read('frontend/utils/pitchMotionReview.ts'))
const {prepareBatterSwing,sampleBatterSwing}=await import(moduleUrl(read('frontend/utils/perdomoSwing.ts').replace("'./pitchMotionReview'",`'${utils}'`)))
const bytes=fs.readFileSync(new URL('frontend/assets/ballpark/characters3d/actor-base-v1.glb',root)),length=bytes.readUInt32LE(12),gltf=JSON.parse(bytes.subarray(20,20+length)),bin=bytes.subarray(28+length)
gltf.buffers=[{byteLength:bin.length,uri:'data:application/octet-stream;base64,'+bin.toString('base64')}];delete gltf.images;delete gltf.textures
for(const material of gltf.materials)delete material.pbrMetallicRoughness.baseColorTexture
const asset=await new GLTFLoader().parseAsync(JSON.stringify(gltf),'')
for(const side of ['L','R']){
 const data=JSON.parse(read(`output/ballpark/perdomo-swing-v1/${side}-review.json`)),clip=prepareBatterSwing(data),actor=makeActor(asset.scene,asset.animations,'batter')
 const at=p=>{actor.root.position.set((side==='R'?-1:1)*3.2*.3048,0,-17/24*.3048);actor.root.rotation.y=side==='R'?Math.PI/2:-Math.PI/2;actor.update({hand:side,team:'AZ',home:false,heightM:1.88},'ready',0);return retargetReferencePose(actor,sampleBatterSwing(clip,p))}
 const snapshot=()=>[...actor.root.position.toArray(),...[...actor.bones.values()].flatMap(b=>[...b.position.toArray(),...b.quaternion.toArray()])]
 let n=0,minX=Infinity,maxX=-Infinity,maxGrip=0,maxJointShift=0,maxRadialGap=0,worst=null,minFootY=Infinity,maxFootY=-Infinity
 for(let i=0;i<=100;i++){
  if(!at(i/100))continue;n++
  assert.ok([...actor.bones.values()].every(b=>b.matrixWorld.elements.every(Number.isFinite)))
  for(const r of actor.rest)maxJointShift=Math.max(maxJointShift,r.bone.position.distanceTo(r.position))
  minX=Math.min(minX,actor.root.position.x);maxX=Math.max(maxX,actor.root.position.x)
  const a=actor.gripSockets.l.getWorldPosition(new THREE.Vector3()),b=actor.gripSockets.r.getWorldPosition(new THREE.Vector3())
  maxGrip=Math.max(maxGrip,a.distanceTo(b))
  const bat=actor.model.getObjectByName('wooden-bat-grip-anchor'),origin=bat.getWorldPosition(new THREE.Vector3()),axis=new THREE.Vector3(0,1,0).applyQuaternion(bat.getWorldQuaternion(new THREE.Quaternion()))
  for(const p of [a,b]){const off=p.clone().sub(origin),gap=off.clone().addScaledVector(axis,-off.dot(axis)).length();if(gap>maxRadialGap){maxRadialGap=gap;worst=i/100}}
  for(const s of ['l','r']){const foot=actor.bones.get(`foot_${s}`).getWorldPosition(new THREE.Vector3());minFootY=Math.min(minFootY,foot.y);maxFootY=Math.max(maxFootY,foot.y);assert.ok(actor.bones.get(`hand_${s}`).quaternion.angleTo(actor.rest.find(r=>r.bone.name===`hand_${s}`).quaternion)<.601,'no inverted wrist')}
 }
 assert.ok(n>50);assert.ok(maxJointShift<1e-8,'fixed rig lengths');assert.ok(maxX-minX>.01,'root must not be pinned')
 at(.5);const first=snapshot();at(.7);at(.2);at(.5);assert.deepEqual(snapshot(),first,'deterministic seek')
 assert.equal(retargetReferencePose(actor,{...sampleBatterSwing(clip,0),points:null}),false,'gap must stay unavailable')
 assert.ok(maxRadialGap<.005&&maxGrip<.20,'hands must share the bat handle without detachment');assert.ok(minFootY>.05,'ground clearance')
 console.log(JSON.stringify({side,samples:n,rootLateralTravelM:maxX-minX,maxGripSocketDistanceM:maxGrip,maxRadialGap,minFootY,maxFootY,maxJointShift,visualAcceptance:'pending'}))
}
