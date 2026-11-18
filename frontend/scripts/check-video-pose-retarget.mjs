// Numerical/source checks only. No renderer, browser, image or visual acceptance.
import fs from 'node:fs'
import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import ts from 'typescript'
import * as THREE from 'three'
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js'
globalThis.ProgressEvent ??= class extends Event {constructor(type,init){super(type);Object.assign(this,init)}}
const read=p=>fs.readFileSync(new URL(`../${p}`,import.meta.url),'utf8')
const original=read('components/charts/replay3d/createReplayActors.ts')
assert.match(original,/PITCHER_DELIVERY_AVAILABLE=false/)
assert.match(original,/VIDEO_POSE_RETARGET_AVAILABLE=false/)
assert.match(original,/if\(VIDEO_POSE_RETARGET_AVAILABLE&&input.previewOnly&&pilot&&pilot.clip.previewOnly&&pilot.clip.playerId===pilot.playerId&&\[702056,657044\].includes\(pilot.playerId\)\)/)
assert.match(read('components/pitcher-personal/PitcherVideoPosePilot.client.vue'),/reconstructionAvailable=false/)
assert.match(read('pages/pitcher-personal.vue'),/:video-pose-pilot="true"/)
assert.match(read('components/pitcher-personal/PitcherInGameTab.vue'),/v-if="videoPosePilot && \(pitcherId===702056 \|\| pitcherId===657044\)"/)
const source=original.replace("import actorUrl from '~/assets/ballpark/characters3d/actor-base-v1.glb?url'","const actorUrl='unused'")
 .replace("'three'",`'${import.meta.resolve('three')}'`)
 .replace("'three/addons/loaders/GLTFLoader.js'",`'${import.meta.resolve('three/addons/loaders/GLTFLoader.js')}'`)
 .replace("'three/addons/utils/SkeletonUtils.js'",`'${import.meta.resolve('three/addons/utils/SkeletonUtils.js')}'`)
const module=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {makeActor,applyVideoPose}=await import('data:text/javascript;base64,'+Buffer.from(module).toString('base64'))
const bytes=fs.readFileSync(new URL('../assets/ballpark/characters3d/actor-base-v1.glb',import.meta.url))
const length=bytes.readUInt32LE(12),gltf=JSON.parse(bytes.subarray(20,20+length)),bin=bytes.subarray(28+length)
gltf.buffers=[{byteLength:bin.length,uri:'data:application/octet-stream;base64,'+bin.toString('base64')}];delete gltf.images;delete gltf.textures
for(const m of gltf.materials)delete m.pbrMetallicRoughness.baseColorTexture
const asset=await new GLTFLoader().parseAsync(JSON.stringify(gltf),'')
for(const [name,id] of [['yesavage',702056],['thompson',657044]]){
 const clip=JSON.parse(read(`assets/ballpark/motion/${name}-video-pose-v1.json`))
 const raw=fs.readFileSync(new URL(`../../output/ballpark/f2-motion-reference-v1/${name}-pose.json`,import.meta.url))
 assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),clip.sourcePoseSha256)
 assert.equal(clip.playerId,id);assert.equal(clip.previewOnly,true);assert.equal(clip.frames.length,56)
 assert.equal(clip.version,'video_pose_rig_pilot_v1')
 const actor=makeActor(asset.scene,asset.animations,'pitcher')
 const at=p=>{actor.root.position.set(0,.254,-60.5*.3048);actor.update({hand:'R',heightM:1.83},'ready',0);applyVideoPose(actor,clip,p);actor.root.updateMatrixWorld(true)}
 const pos=n=>actor.bones.get(n).getWorldPosition(new THREE.Vector3())
 const snapshot=()=>[...actor.root.position.toArray(),...[...actor.bones.values()].flatMap(b=>[...b.position.toArray(),...b.quaternion.toArray()])]
 let maxKnee=0,minKneeSign=1,minFoot=Infinity,maxFoot=-Infinity,maxRoot=0
 for(let i=0;i<clip.frames.length;i++){
  const f=clip.frames[i];assert.equal(f.rotations.length,clip.boneNames.length*4)
  assert.ok([...f.root,...f.rotations].every(Number.isFinite))
  if(i){assert.ok(f.sourceTime>clip.frames[i-1].sourceTime);maxRoot=Math.max(maxRoot,new THREE.Vector3(...f.root).distanceTo(new THREE.Vector3(...clip.frames[i-1].root)))}
 }
 assert.ok(maxRoot<.12001)
 for(let i=0;i<=110;i++){
  at(i/110)
  for(const r of actor.rest){assert.ok(r.bone.position.distanceTo(r.position)<1e-9,'no local bone translation/stretch');assert.ok(Math.abs(r.bone.quaternion.length()-1)<.000002);assert.ok(r.bone.matrixWorld.elements.every(Number.isFinite))}
  const right=pos('thigh_l').sub(pos('thigh_r')).normalize()
  for(const s of ['l','r']){
   const upper=pos(`calf_${s}`).sub(pos(`thigh_${s}`)).normalize(),lower=pos(`foot_${s}`).sub(pos(`calf_${s}`)).normalize()
   const angle=upper.angleTo(lower)*180/Math.PI;maxKnee=Math.max(maxKnee,angle)
   const sign=upper.clone().cross(lower).dot(right);minKneeSign=Math.min(minKneeSign,sign)
   assert.ok(angle<145.2,`knee flexion ${angle}`);assert.ok(sign>-.015,`reversed knee hinge ${sign}`)
   const foot=pos(`foot_${s}`).y;minFoot=Math.min(minFoot,foot);maxFoot=Math.max(maxFoot,foot)
  }
 }
 at(.43);const first=snapshot();at(.9);at(.1);at(.43);assert.deepEqual(snapshot(),first,'seek reset must not accumulate offsets')
 console.log(JSON.stringify({name,frames:56,samples:111,maxKneeDeg:maxKnee,minKneeSign,ankleWorldY:[minFoot,maxFoot],maximumRootStep:maxRoot,scope:'source/numerical only; ground and naturalness pending user'}))
}
