// Static rig math only, no renderer/browser/image decoding or motion reconstruction.
import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'
import * as THREE from 'three'
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js'
globalThis.ProgressEvent ??= class extends Event {}
const read=p=>fs.readFileSync(new URL(`../${p}`,import.meta.url),'utf8')
const source=read('components/charts/replay3d/createReplayActors.ts')
  .replace("import actorUrl from '~/assets/ballpark/characters3d/actor-base-v1.glb?url'","const actorUrl='unused'")
  .replace("'three'",`'${import.meta.resolve('three')}'`)
  .replace("'three/addons/loaders/GLTFLoader.js'",`'${import.meta.resolve('three/addons/loaders/GLTFLoader.js')}'`)
  .replace("'three/addons/utils/SkeletonUtils.js'",`'${import.meta.resolve('three/addons/utils/SkeletonUtils.js')}'`)
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {makeActor}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'))
const bytes=fs.readFileSync(new URL('../assets/ballpark/characters3d/actor-base-v1.glb',import.meta.url))
const size=bytes.readUInt32LE(12),gltf=JSON.parse(bytes.subarray(20,20+size).toString()),binary=bytes.subarray(28+size)
gltf.buffers=[{byteLength:binary.length,uri:'data:application/octet-stream;base64,'+binary.toString('base64')}]
delete gltf.images;delete gltf.textures;for(const m of gltf.materials)delete m.pbrMetallicRoughness.baseColorTexture
const asset=await new GLTFLoader().parseAsync(JSON.stringify(gltf),'')
const actor=makeActor(asset.scene,asset.animations,'pitcher')
for(const hand of ['R','L'])for(const angle of [-61,-12.2,0,50,65.8,90]){
  actor.update({hand,heightM:1.9,team:'AZ',home:true},'ready',0)
  const feet=['foot_l','foot_r'].map(n=>actor.bones.get(n).getWorldPosition(new THREE.Vector3()))
  actor.staticArmAngle(angle,hand)
  const side=hand==='L'?'l':'r',shoulder=actor.bones.get(`upperarm_${side}`).getWorldPosition(new THREE.Vector3()),wrist=actor.bones.get(`hand_${side}`).getWorldPosition(new THREE.Vector3()),axis=wrist.sub(shoulder).normalize()
  const actual=Math.atan2(axis.y,Math.abs(axis.x))*180/Math.PI
  assert.ok(Math.abs(actual-angle)<1e-4,`${hand}: ${actual} vs ${angle}`) // float32 rig precision, degrees
  for(const [i,n] of ['foot_l','foot_r'].entries())assert.ok(actor.bones.get(n).getWorldPosition(new THREE.Vector3()).distanceTo(feet[i])<1e-8,'no foot/root movement')
  const first=JSON.stringify([...actor.bones.values()].map(b=>b.quaternion.toArray()))
  actor.update({hand,heightM:1.9,team:'AZ',home:true},'ready',0);actor.staticArmAngle(angle,hand)
  assert.equal(JSON.stringify([...actor.bones.values()].map(b=>b.quaternion.toArray())),first,'deterministic frozen pose')
}
assert.ok(actor.model.getObjectByName('glove-leather-pocket'));assert.ok(actor.model.getObjectByName('glove-open-pocket'));assert.ok(actor.model.getObjectByName('glove-thumb'))
assert.equal(actor.model.getObjectByName('fielding-glove').type,'Group')
console.log('Static rig source PASS: L/R negative/high angles, extended shoulder-to-hand direction, unchanged feet/root, repeatable pose, separate glove pocket/thumb. No visual acceptance.')
