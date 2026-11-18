// Structural and kinematic checks only: no renderer, image decode, DOM or browser.
import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'
import * as THREE from 'three'
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js'
globalThis.ProgressEvent ??= class extends Event {constructor(type,init){super(type);Object.assign(this,init)}}
const read=p=>fs.readFileSync(new URL(`../${p}`,import.meta.url),'utf8')
const source=read('components/charts/replay3d/createReplayActors.ts')
  .replace("import actorUrl from '~/assets/ballpark/characters3d/actor-base-v1.glb?url'","const actorUrl='unused-in-structural-test'")
  .replace("'three'",`'${import.meta.resolve('three')}'`)
  .replace("'three/addons/loaders/GLTFLoader.js'",`'${import.meta.resolve('three/addons/loaders/GLTFLoader.js')}'`)
  .replace("'three/addons/utils/SkeletonUtils.js'",`'${import.meta.resolve('three/addons/utils/SkeletonUtils.js')}'`)
const module=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {makeActor}=await import('data:text/javascript;base64,'+Buffer.from(module).toString('base64'))
const contractSource=ts.transpileModule(read('components/charts/replay3d/replayContract.ts'),{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {replayMotionFrame,DELIVERY_LEAD_SECONDS}=await import('data:text/javascript;base64,'+Buffer.from(contractSource).toString('base64'))
const bytes=fs.readFileSync(new URL('../assets/ballpark/characters3d/actor-base-v1.glb',import.meta.url))
assert.equal(bytes.readUInt32LE(0),0x46546c67);assert.equal(bytes.readUInt32LE(8),bytes.length)
const length=bytes.readUInt32LE(12),gltf=JSON.parse(bytes.subarray(20,20+length).toString())
assert.equal(gltf.skins[0].joints.length,65)
assert.ok(gltf.meshes.some(m=>m.name==='IndependentBaseballGarments'),'clothes must have independent geometry')
assert.ok(gltf.nodes.some(n=>n.name==='IndependentBaseballGarments'&&n.skin===0),'clothes must follow the skeleton')
const mother=gltf.meshes.find(m=>m.name==='BaseballMaleSkinned'),clothing=gltf.meshes.find(m=>m.name==='IndependentBaseballGarments')
const cuffMaterial=gltf.materials.findIndex(m=>m.name==='uniform_cuff')
assert.ok(clothing.primitives.some(p=>p.material===cuffMaterial),'cuff must be part of the shared skinned sleeve surface')
for(const primitive of clothing.primitives)for(const attr of ['POSITION','JOINTS_0','WEIGHTS_0'])assert.equal(primitive.attributes[attr],mother.primitives[0].attributes[attr],`seam ${attr} must match exactly; nearest weights can split clothing`)
assert.equal(gltf.animations.length,10)
assert.ok(!mother.primitives.some(p=>p.material===6),'bare foot colour-only triangles must be removed')
for(const side of ['l','r']){
  for(const name of [`cleat-upper-${side}`,`cleat-outsole-${side}`,...Array.from({length:4},(_,i)=>`cleat-lace-${side}-${i}`),...Array.from({length:8},(_,i)=>`cleat-stud-${side}-${i}`)]){
    assert.ok(gltf.nodes.some(n=>n.name===name&&n.skin===0),`${name} must be actual skinned geometry in exported asset`)
  }
}
for(const role of ['batter','pitcher'])for(const hand of ['R','L'])for(const pose of ['ready','idle'])assert.ok(gltf.animations.some(a=>a.name===`${role}_${pose}_${hand}`))
const binary=bytes.subarray(28+length)
gltf.buffers=[{byteLength:binary.length,uri:'data:application/octet-stream;base64,'+binary.toString('base64')}]
// Mesh / skin / clips remain identical; omit texture reads solely in this source check.
delete gltf.images;delete gltf.textures
for(const mat of gltf.materials)delete mat.pbrMetallicRoughness.baseColorTexture
const asset=await new GLTFLoader().parseAsync(JSON.stringify(gltf),'')
const fingerprint=JSON.stringify(gltf.nodes),near=(a,b,t=.005)=>assert.ok(Math.abs(a-b)<t,`${a} versus ${b}`)
for(const role of ['batter','pitcher']){
  const actor=makeActor(asset.scene,asset.animations,role)
  for(const side of ['l','r'])assert.ok(!actor.model.getObjectByName(`jersey-cuff-${side}`),'remove the rigid cuff ring that protruded in bent-arm poses')
  assert.ok(actor.model.getObjectByName('jersey-collar'))
  assert.ok(actor.baseHeight>1.7&&actor.baseHeight<2)
  for(const hand of ['L','R']){
    actor.root.rotation.y=role==='batter'?(hand==='R'?Math.PI/2:-Math.PI/2):0
    for(const heightM of [1.7526,2.0066]){
      actor.update({hand,heightM,team:'ATH',home:hand==='R'},'ready',0)
      actor.root.updateMatrixWorld(true)
      let jerseyFound=false
      actor.model.traverse(o=>{
        if(!o.material)return
        for(const m of Array.isArray(o.material)?o.material:[o.material])if(m.name==='uniform_jersey'){
          jerseyFound=true;assert.ok(!m.map,'jersey must never inherit the bare-skin texture')
          near(m.color.r,new THREE.Color(hand==='R'?'#f3f3ed':'#004b35').r,.00001)
        }
      })
      assert.ok(jerseyFound,'home/away kit must retain its jersey material')
      for(const bone of actor.bones.values())assert.ok(bone.getWorldPosition(new THREE.Vector3()).toArray().every(Number.isFinite))
      for(const side of ['l','r']){
        const foot=actor.bones.get(`foot_${side}`).getWorldPosition(new THREE.Vector3())
        assert.ok(foot.y>.015&&foot.y<.23,`foot anchor not near ground: ${foot.y}`)
        const shoe=actor.model.getObjectByName(`cleat-upper-${side}`);shoe.computeBoundingBox()
        const shoeBox=shoe.boundingBox.clone().applyMatrix4(shoe.matrixWorld)
        assert.ok(shoeBox.getCenter(new THREE.Vector3()).distanceTo(foot)<.25,'shoe must follow its foot bone through handed pose and height scale')
        assert.ok(shoeBox.max.y-shoeBox.min.y>.07,'cleat upper must have physical volume')
        if(role==='batter'){
          const wrist=actor.bones.get(`hand_${side}`),neutral=asset.scene.getObjectByName(`hand_${side}`)
          assert.ok(wrist.quaternion.angleTo(neutral.quaternion)<.601,'wrist must not invert; forearm twist and grip socket own orientation')
          const bat=actor.model.getObjectByName('wooden-bat-grip-anchor'),origin=bat.getWorldPosition(new THREE.Vector3())
          const axis=new THREE.Vector3(0,1,0).applyQuaternion(bat.getWorldQuaternion(new THREE.Quaternion()))
          assert.ok(axis.y>.35,`bat must remain raised, up=${axis.y}`)
          const socket=actor.gripSockets[side].getWorldPosition(new THREE.Vector3()).sub(origin)
          const along=socket.dot(axis),gap=socket.clone().addScaledVector(axis,-along).length()
          assert.ok(gap<.025,`${hand}/${side} palm socket not on bat: ${gap}`)
          for(const finger of ['index','middle','ring','pinky','thumb']){
            const tip=actor.bones.get(`${finger}_04_leaf_${side}`).getWorldPosition(new THREE.Vector3()).sub(origin)
            const distance=tip.clone().addScaledVector(axis,-tip.dot(axis)).length()
            assert.ok(distance<.085,`${hand}/${side}/${finger} fingertip too far from bat: ${distance}`)
          }
        }
      }
      const box=new THREE.Box3().setFromObject(actor.root)
      assert.ok(box.max.y<heightM+1,`${role} exploded height ${box.max.y}`)
      assert.ok(box.min.y>-.15,`${role} feet under ground ${box.min.y}`)
      const rest=actor.bones.get('pelvis').position.clone()
      actor.update({hand,heightM},'idle',.6)
      assert.notEqual(actor.bones.get('pelvis').position.z,rest.z)
      actor.update({hand,heightM},'ready',0)
      const first=actor.bones.get('hand_l').getWorldPosition(new THREE.Vector3())
      actor.update({hand,heightM},'idle',1.8);actor.update({hand,heightM},'ready',0)
      const again=actor.bones.get('hand_l').getWorldPosition(new THREE.Vector3());near(first.distanceTo(again),0)
      assert.ok(actor.root.scale.x>0&&actor.root.scale.z>0,'authored handedness must not mirror the mesh')
    }
  }
}
assert.equal(JSON.stringify(gltf.nodes),fingerprint,'source skeleton unchanged')
// Independent source constraints, not screenshots or animation appearance QA.
const duration=2.4,releaseFrame=replayMotionFrame(DELIVERY_LEAD_SECONDS/duration,.4,'called_strike',60)
assert.equal(releaseFrame.phase,'release');assert.equal(releaseFrame.timeSeconds,0);assert.equal(releaseFrame.ballProgress,0)
assert.equal(replayMotionFrame(1.6/duration,.4,'swinging_strike',0).phase,'plate')
assert.equal(replayMotionFrame(1.6/duration,.4,'swinging_strike',0).ballProgress,1)
assert.equal(replayMotionFrame(.5,.4,'foul_bunt',null).batterAction,'unknown')
assert.equal(replayMotionFrame(.5,.4,'ball',null).armAngleDeg,null)
assert.equal(replayMotionFrame(.5,.4,'hit_into_play',0).armAngleDeg,0)
let maximumReleaseError=0,maximumAngleError=0
for(const hand of ['L','R'])for(const heightM of [1.7526,2.0066])for(const [angle,zFt,extension] of [[60,6.2,6],[-12,2.8,7]]){
  const actor=makeActor(asset.scene,asset.animations,'pitcher');actor.root.position.set(0,.254,-60.5*.3048)
  const point=new THREE.Vector3((hand==='R'?-.7:.7),zFt*.3048,-(60.5-extension)*.3048),frame={...releaseFrame,armAngleDeg:angle}
  actor.update({hand,heightM},'ready',0,{frame,releaseWorld:point})
  const side=hand==='R'?'r':'l',socket=actor.releaseSockets[side].getWorldPosition(new THREE.Vector3()),shoulder=actor.bones.get(`upperarm_${side}`).getWorldPosition(new THREE.Vector3())
  const error=socket.distanceTo(point),direction=socket.clone().sub(shoulder),actualAngle=Math.atan2(direction.y,Math.hypot(direction.x,direction.z))*180/Math.PI
  maximumReleaseError=Math.max(maximumReleaseError,error);maximumAngleError=Math.max(maximumAngleError,Math.abs(actualAngle-angle))
  assert.ok(error<.005,`source release hand fit ${hand}/${heightM}/${angle}: ${error} m`)
  assert.ok(Math.abs(actualAngle-angle)<.5,`source shoulder-to-ball angle ${angle}: ${actualAngle}`)
  const snapshot=()=>[...actor.bones.values()].flatMap(b=>[...b.position.toArray(),...b.quaternion.toArray()])
  const first=snapshot()
  for(const t of [0,.2,.7,.99,.1,.5])actor.update({hand,heightM},'ready',0,{frame:replayMotionFrame(t,.4,'ball',angle),releaseWorld:point})
  actor.update({hand,heightM},'ready',0,{frame,releaseWorld:point})
  assert.deepEqual(snapshot(),first,'seek must restore the same full skeleton without accumulated rotations')
}
console.log(`F2.4 numerical release constraints: max hand error ${maximumReleaseError.toFixed(6)} m; max arm-angle error ${maximumAngleError.toFixed(6)} degrees. Generic motion only; no visual acceptance.`)
let maxPlantDrift=0
for(const hand of ['L','R'])for(const angle of [-12,60]){
  const actor=makeActor(asset.scene,asset.animations,'pitcher'),point=new THREE.Vector3(hand==='R'?-.6:.6,angle<0?.9:1.9,-54.5*.3048)
  actor.root.position.set(0,.254,-60.5*.3048)
  const at=d=>{actor.update({hand,heightM:1.83},'ready',0,{frame:replayMotionFrame(d*1.2/2.4,.4,'ball',angle),releaseWorld:point});actor.root.updateMatrixWorld(true)}
  const line=(a,b)=>actor.bones.get(a).getWorldPosition(new THREE.Vector3()).sub(actor.bones.get(b).getWorldPosition(new THREE.Vector3()))
  at(.45)
  const closed=line('upperarm_l','upperarm_r')
  assert.ok(Math.abs(closed.z)>Math.abs(closed.x)*2,'set/lift must stay side-on, not face home all the way')
  at(.78)
  const hips=line('thigh_l','thigh_r'),shoulders=line('upperarm_l','upperarm_r')
  const separation=Math.abs(Math.atan2(hips.z,hips.x)-Math.atan2(shoulders.z,shoulders.x))
  assert.ok(Math.min(separation,2*Math.PI-separation)>.25,'hips must open before shoulders')
  const lead=hand==='R'?'l':'r'
  at(.90);const plant=actor.bones.get(`foot_${lead}`).getWorldPosition(new THREE.Vector3())
  at(1);const drift=plant.distanceTo(actor.bones.get(`foot_${lead}`).getWorldPosition(new THREE.Vector3()))
  maxPlantDrift=Math.max(maxPlantDrift,drift)
  assert.ok(drift<.035,`lead foot should stay planted through release: ${hand}/${angle}: ${drift}m`)
}
console.log(`Video-reference phase source checks: closed set, hip-before-shoulder opening, max lead-ankle drift after plant ${maxPlantDrift.toFixed(6)}m. No animation appearance certification.`)
for(const hand of ['L','R'])for(const description of ['called_strike','swinging_strike']){
  const actor=makeActor(asset.scene,asset.animations,'batter'),point=new THREE.Vector3(-.6,1.85,-54.5*.3048)
  actor.root.rotation.y=hand==='R'?Math.PI/2:-Math.PI/2
  for(let i=0;i<=60;i++){
    const frame=replayMotionFrame(i/60,.4,description,55)
    actor.update({hand,heightM:1.83},'ready',0,{frame,releaseWorld:point});actor.root.updateMatrixWorld(true)
    for(const b of actor.bones.values())assert.ok([...b.position.toArray(),...b.quaternion.toArray()].every(Number.isFinite),'finite motion skeleton')
    const bat=actor.model.getObjectByName('wooden-bat-grip-anchor'),origin=bat.getWorldPosition(new THREE.Vector3()),axis=new THREE.Vector3(0,1,0).applyQuaternion(bat.getWorldQuaternion(new THREE.Quaternion()))
    for(const side of ['l','r']){
      const offset=actor.gripSockets[side].getWorldPosition(new THREE.Vector3()).sub(origin)
      const gripError=offset.addScaledVector(axis,-offset.dot(axis)).length()
      assert.ok(gripError<.035,`${hand}/${description}/${i}: palm detached from bat during motion, ${gripError}m`)
    }
  }
}
console.log('F2.3 source PASS: self-contained GLB, 65-joint skin, ready/idle, L/R authored targets, finite body pose, foot bounds, metre height scaling, repeatable pose reset. No renderer, image or visual acceptance.')
