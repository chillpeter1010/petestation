import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { clone } from 'three/addons/utils/SkeletonUtils.js'
import actorUrl from '~/assets/ballpark/characters3d/actor-base-v1.glb?url'
import type { Replay3DInput, ReplayActorIdentity, ReplayMotionFrame, ReplayVideoPoseClip, ReplayReferencePose } from './replayContract'

// Generic palette variants, not exact historical MLB uniform editions or logos.
const PALETTES:Record<string,string>={ATH:'#004b35',OAK:'#004b35',AZ:'#a71930',ATL:'#15345a',BAL:'#df570a',BOS:'#bd3039',CHC:'#174996',CWS:'#20232a',CIN:'#c6011f',CLE:'#123659',COL:'#42316b',DET:'#18365b',HOU:'#e66b23',KC:'#1767ab',LAA:'#bf153e',LAD:'#07579b',MIA:'#008ca2',MIL:'#18365b',MIN:'#16365a',NYM:'#16498b',NYY:'#1b3557',PHI:'#c92542',PIT:'#292b30',SD:'#604333',SEA:'#006d70',SF:'#df570a',STL:'#bd2035',TB:'#173f6c',TEX:'#17579d',TOR:'#1d5fa1',WSH:'#b82035'}
const UP=new THREE.Vector3(0,1,0)
// User rejected the procedural delivery (twisted legs). Keep the accepted ready
// rig until video keypoints and retargeting have a separate acceptance gate.
const PITCHER_DELIVERY_AVAILABLE=false
const PITCHER_ACTOR_AVAILABLE=false // User removed the pitcher figure; source release remains.
const BATTER_SWING_RETARGET_AVAILABLE=false // User paused all actor motion.
const REFERENCE_B_RETARGET_AVAILABLE=false // Rejected: stride/root depth is not reconstructed.
const VIDEO_POSE_RETARGET_AVAILABLE=false // Rejected: right-leg/body twist and invalid stride.
type Actor = ReturnType<typeof makeActor>
type ActorMotion = {frame:ReplayMotionFrame;releaseWorld:THREE.Vector3}
const ease=(a:number,b:number,x:number)=>{const t=THREE.MathUtils.clamp((x-a)/(b-a),0,1);return t*t*(3-2*t)}

function disposeObjects(root:THREE.Object3D){
  const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>(),textures=new Set<THREE.Texture>(),skeletons=new Set<THREE.Skeleton>()
  root.traverse(o=>{
    const m=o as THREE.SkinnedMesh
    if(m.geometry)geometries.add(m.geometry)
    if(m.skeleton)skeletons.add(m.skeleton)
    for(const material of m.material?(Array.isArray(m.material)?m.material:[m.material]):[]){
      materials.add(material)
      for(const value of Object.values(material))if(value instanceof THREE.Texture)textures.add(value)
    }
  })
  geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>{const image=t.source.data as {close?:()=>void}|null;if(image&&typeof image.close==='function')image.close();t.dispose()});skeletons.forEach(s=>s.dispose())
}

export function makeActor(source:THREE.Group,clips:THREE.AnimationClip[],role:'pitcher'|'batter'){
  const root=new THREE.Group(),model=clone(source) as THREE.Group
  root.name=`generic-${role}-actor`;root.add(model)
  const bones=new Map<string,THREE.Bone>(),rest:{bone:THREE.Bone;position:THREE.Vector3;quaternion:THREE.Quaternion}[]=[]
  const mats=new Map<string,THREE.MeshStandardMaterial>()
  model.traverse(o=>{
    if(o instanceof THREE.Bone){bones.set(o.name,o);rest.push({bone:o,position:o.position.clone(),quaternion:o.quaternion.clone()})}
    if(o instanceof THREE.Mesh){
      const sourceMaterials=Array.isArray(o.material)?o.material:[o.material]
      const copies=sourceMaterials.map(m=>{
        if(!mats.has(m.name)){const material=m.clone() as THREE.MeshStandardMaterial;mats.set(m.name,material)}
        return mats.get(m.name)!
      })
      o.material=Array.isArray(o.material)?copies:copies[0];o.frustumCulled=false
    }
  })
  model.updateMatrixWorld(true)
  const box=new THREE.Box3().setFromObject(model),baseHeight=box.max.y-box.min.y,groundOffset=-box.min.y
  const localPoint=(o:THREE.Object3D)=>model.worldToLocal(o.getWorldPosition(new THREE.Vector3()))
  const feet={l:localPoint(bones.get('foot_l')!),r:localPoint(bones.get('foot_r')!)}
  const footRot={l:bones.get('foot_l')!.getWorldQuaternion(new THREE.Quaternion()),r:bones.get('foot_r')!.getWorldQuaternion(new THREE.Quaternion())}
  const headRestWorld=model.getObjectByName('Head')!.getWorldQuaternion(new THREE.Quaternion())
  const mixer=new THREE.AnimationMixer(model)
  const actions=Object.fromEntries(clips.map(c=>[c.name,mixer.clipAction(c)]))
  const object=(geometry:THREE.BufferGeometry,color:string,name:string)=>{
    const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:.8}));mesh.name=name;return mesh
  }
  const head=bones.get('Head')!,hat=new THREE.Group();head.add(hat);hat.name=role==='batter'?'batting-helmet':'pitcher-cap'
  // Equipment anchors are stored in the original head bone's local frame.
  const setModelPoint=(item:THREE.Object3D,parent:THREE.Object3D,p:THREE.Vector3)=>{parent.add(item);item.position.copy(parent.worldToLocal(model.localToWorld(p.clone())));item.quaternion.copy(parent.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(model.getWorldQuaternion(new THREE.Quaternion())))}
  const crown=object(new THREE.SphereGeometry(.109,24,12,0,Math.PI*2,0,Math.PI/2),'#17354b','hat-crown')
  setModelPoint(crown,head,new THREE.Vector3(0,1.755,.005));crown.scale.set(1,.68,1.10)
  const visor=object(new THREE.SphereGeometry(.11,20,8),'#17354b','hat-visor')
  setModelPoint(visor,head,new THREE.Vector3(0,1.752,.105));visor.scale.set(.9,.045,.88)
  const bat=new THREE.Group();bat.name='wooden-bat-grip-anchor';model.add(bat)
  const gripSockets={l:new THREE.Object3D(),r:new THREE.Object3D()}
  for(const side of ['l','r'] as const){const socket=gripSockets[side];socket.name=`bat-palm-socket-${side}`;socket.position.set(side==='l'?.022:-.022,.105,0);bones.get(`hand_${side}`)!.add(socket)}
  const shaft=object(new THREE.CylinderGeometry(.032,.014,.82,18),'#b99262','bat-shaft');shaft.position.y=.36;bat.add(shaft)
  const knob=object(new THREE.CylinderGeometry(.023,.023,.018,14),'#9c764a','bat-knob');knob.position.y=-.055;bat.add(knob)
  const glove=new THREE.Group();glove.name='fielding-glove';model.add(glove)
  // A shallow leather pocket with a separate thumb/web, rather than a solid ball.
  const palm=new THREE.Shape();palm.moveTo(-.065,-.055);palm.quadraticCurveTo(-.09,.015,-.06,.085);palm.quadraticCurveTo(0,.135,.06,.085);palm.quadraticCurveTo(.09,.015,.055,-.055);palm.closePath()
  const pocket=object(new THREE.ExtrudeGeometry(palm,{depth:.022,bevelEnabled:true,bevelSegments:2,steps:1,bevelSize:.008,bevelThickness:.006}),'#89552d','glove-leather-pocket');glove.add(pocket)
  const inset=object(new THREE.SphereGeometry(.055,16,10),'#3c261b','glove-open-pocket');inset.scale.set(.85,1.05,.16);inset.position.set(0,.03,.03);glove.add(inset)
  const thumb=object(new THREE.CapsuleGeometry(.023,.075,4,8),'#a16b39','glove-thumb');thumb.position.set(.072,.005,.018);thumb.rotation.z=-.48;glove.add(thumb)
  for(let i=0;i<4;i++){const finger=object(new THREE.CapsuleGeometry(.014,.054,3,8),'#a16b39',`glove-finger-${i}`);finger.position.set(-.045+i*.029,.083,.014);finger.rotation.z=(1.5-i)*.1;glove.add(finger)}
  const releaseSockets={l:new THREE.Object3D(),r:new THREE.Object3D()}
  for(const side of ['l','r'] as const){releaseSockets[side].name=`pitch-release-socket-${side}`;releaseSockets[side].position.set(0,.10,0);bones.get(`hand_${side}`)!.add(releaseSockets[side])}
  const heldBall=object(new THREE.SphereGeometry(.037,12,8),'#f7f5ee','pitcher-held-ball');model.add(heldBall);heldBall.visible=false
  const seam=object(new THREE.TorusGeometry(.054,.003,4,20),'#deb982','glove-seam');glove.add(seam);seam.scale.y=1.15;seam.position.set(0,.025,.031)
  const belt=object(new THREE.CylinderGeometry(.215,.215,.032,24),'#253340','belt');setModelPoint(belt,bones.get('pelvis')!,new THREE.Vector3(0,1.005,0));belt.scale.z=.74
  const badge=object(new THREE.BoxGeometry(.045,.045,.006),'#d5b265','jersey-badge');setModelPoint(badge,bones.get('spine_03')!,new THREE.Vector3(.12,1.35,.184))
  const uniformTrim:THREE.Mesh[]=[]
  const collar=object(new THREE.CylinderGeometry(.117,.123,.052,24,1,true),'#17354b','jersey-collar')
  setModelPoint(collar,bones.get('spine_03')!,new THREE.Vector3(0,1.553,-.012));collar.scale.z=.95;uniformTrim.push(collar)
  const placketPoints=[new THREE.Vector3(0,1.07,.165),new THREE.Vector3(0,1.20,.186),new THREE.Vector3(0,1.36,.200),new THREE.Vector3(0,1.49,.168)]
  for(const x of [-.012,.012]){
    const pipe=object(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(placketPoints.map(p=>p.clone().add(new THREE.Vector3(x,0,0)))),20,.0035,6,false),'#17354b','jersey-placket-piping')
    setModelPoint(pipe,bones.get('spine_03')!,new THREE.Vector3());uniformTrim.push(pipe)
  }
  for(const [y,z] of [[1.12,.177],[1.20,.190],[1.28,.198],[1.36,.204]])setModelPoint(object(new THREE.SphereGeometry(.007,8,6),'#b9c0c0','jersey-button'),bones.get('spine_03')!,new THREE.Vector3(0,y,z))

  function worldRotate(bone:THREE.Bone,q:THREE.Quaternion){
    bone.quaternion.copy(bone.parent!.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(q));model.updateMatrixWorld(true)
  }
  function aim(bone:THREE.Bone,child:THREE.Bone,target:THREE.Vector3){
    const origin=bone.getWorldPosition(new THREE.Vector3()),from=child.getWorldPosition(new THREE.Vector3()).sub(origin).normalize(),to=target.clone().sub(origin).normalize()
    worldRotate(bone,new THREE.Quaternion().setFromUnitVectors(from,to).multiply(bone.getWorldQuaternion(new THREE.Quaternion())))
  }
  function ik(a:string,b:string,c:string,targetLocal:THREE.Vector3,hintLocal:THREE.Vector3){
    const upper=bones.get(a)!,lower=bones.get(b)!,end=bones.get(c)!
    model.updateMatrixWorld(true)
    const origin=upper.getWorldPosition(new THREE.Vector3()),joint=lower.getWorldPosition(new THREE.Vector3()),tip=end.getWorldPosition(new THREE.Vector3())
    const target=model.localToWorld(targetLocal.clone()),dir=target.clone().sub(origin),la=origin.distanceTo(joint),lb=joint.distanceTo(tip),distance=THREE.MathUtils.clamp(dir.length(),Math.abs(la-lb)+.001,la+lb-.001)
    dir.normalize();target.copy(origin).addScaledVector(dir,distance)
    const bend=model.localToWorld(hintLocal.clone()).sub(origin);bend.addScaledVector(dir,-bend.dot(dir)).normalize()
    const x=(la*la-lb*lb+distance*distance)/(2*distance),y=Math.sqrt(Math.max(0,la*la-x*x))
    aim(upper,lower,origin.clone().addScaledVector(dir,x).addScaledVector(bend,y));aim(lower,end,target)
  }
  function orientGrip(side:'l'|'r',direction:THREE.Vector3){
    const hand=bones.get(`hand_${side}`)!,forearm=bones.get(`lowerarm_${side}`)!
    hand.quaternion.copy(rest.find(r=>r.bone===hand)!.quaternion);model.updateMatrixWorld(true)
    const axis=hand.getWorldPosition(new THREE.Vector3()).sub(forearm.getWorldPosition(new THREE.Vector3())).normalize()
    const target=direction.clone().applyQuaternion(model.getWorldQuaternion(new THREE.Quaternion()))
    const current=new THREE.Vector3(0,0,1).applyQuaternion(hand.getWorldQuaternion(new THREE.Quaternion()))
    const from=current.clone().addScaledVector(axis,-current.dot(axis)).normalize(),to=target.clone().addScaledVector(axis,-target.dot(axis)).normalize()
    const angle=THREE.MathUtils.clamp(Math.atan2(axis.dot(from.clone().cross(to)),from.dot(to)),-Math.PI/2,Math.PI/2)
    worldRotate(forearm,new THREE.Quaternion().setFromAxisAngle(axis,angle).multiply(forearm.getWorldQuaternion(new THREE.Quaternion())))
    const width=new THREE.Vector3(0,0,1).applyQuaternion(hand.getWorldQuaternion(new THREE.Quaternion()))
    const turn=new THREE.Quaternion().setFromUnitVectors(width,target),bend=turn.angleTo(new THREE.Quaternion())
    if(bend>.60)turn.identity().slerp(new THREE.Quaternion().setFromUnitVectors(width,target),.60/bend)
    worldRotate(hand,turn.multiply(hand.getWorldQuaternion(new THREE.Quaternion())))
  }
  function holdBat(side:'l'|'r',center:THREE.Vector3,direction:THREE.Vector3){
    const hand=bones.get(`hand_${side}`)!
    const forward=new THREE.Vector3(0,1,0).applyQuaternion(hand.getWorldQuaternion(new THREE.Quaternion())).applyQuaternion(model.getWorldQuaternion(new THREE.Quaternion()).invert()).normalize()
    const normal=forward.clone().cross(direction).normalize()
    // Each joint aims around the handle cylinder in model space. The finger
    // bone frames differ; a shared Euler-X curl leaves these fingers splayed.
    for(const finger of ['index','middle','ring','pinky']){
      const base=bones.get(`${finger}_01_${side}`)!,p=localPoint(base)
      const axis=center.clone().addScaledVector(direction,p.clone().sub(center).dot(direction))
      const radial=p.clone().sub(axis),radius=Math.max(.021,radial.length());radial.normalize()
      const tangent=direction.clone().cross(radial),sign=Math.sign(tangent.dot(forward))||1
      for(let i=1;i<=3;i++){
        const bone=bones.get(`${finger}_0${i}_${side}`)!,child=bones.get(i===3?`${finger}_04_leaf_${side}`:`${finger}_0${i+1}_${side}`)!
        const target=axis.clone().add(radial.clone().applyAxisAngle(direction,sign*i*1.24).multiplyScalar(radius))
        aim(bone,child,model.localToWorld(target))
      }
    }
    for(let i=1;i<=3;i++){
      const bone=bones.get(`thumb_0${i}_${side}`)!,child=bones.get(i===3?`thumb_04_leaf_${side}`:`thumb_0${i+1}_${side}`)!
      const target=center.clone().addScaledVector(normal,-.019).addScaledVector(direction,.025).addScaledVector(forward,(3-i)*.025)
      aim(bone,child,model.localToWorld(target))
    }
  }
  let lastKit=''
  function update(identity:ReplayActorIdentity|undefined,pose:'ready'|'idle',time:number,motion?:ActorMotion){
    const height=identity?.heightM&&Number.isFinite(identity.heightM)?identity.heightM:1.83
    root.scale.setScalar(height/baseHeight);model.position.y=groundOffset
    root.updateMatrixWorld(true)
    for(const r of rest){r.bone.position.copy(r.position);r.bone.quaternion.copy(r.quaternion)}
    for(const action of Object.values(actions))action.stop()
    actions[pose]?.play();mixer.setTime(pose==='idle'?time%2.4:0)
    bones.get('pelvis')!.position.z-=role==='batter'?.055:.018
    model.updateMatrixWorld(true)
    const left=identity?.hand==='L',mirror=left?-1:1
    const baseRot=model.getWorldQuaternion(new THREE.Quaternion())
    const frame=motion?.frame,recover=frame&&role==='batter'?ease(frame.flightSeconds+.30,frame.flightSeconds+.8,frame.timeSeconds):0
    const delivery=frame?ease(.32,1,frame.delivery)*(1-recover):0,follow=frame?ease(0,1,frame.follow)*(1-recover):0
    const armSide=left?'l':'r',leadSide=left?'r':'l'
    const releaseLocal=motion?model.worldToLocal(motion.releaseWorld.clone()):undefined
    const armAngle=(frame?.armAngleDeg??45)*Math.PI/180
    const armDirection=new THREE.Vector3(-mirror*Math.cos(armAngle)*.94,Math.sin(armAngle),Math.cos(armAngle)*Math.sqrt(1-.94*.94)).normalize()
    const d=frame?.delivery??0,lowSlot=THREE.MathUtils.clamp((25-(frame?.armAngleDeg??45))/65,0,1)
    // Authored from observed video PHASE ORDER, not measured 3D joint angles:
    // closed set -> lift -> stride/hips open -> shoulders open -> follow-through.
    const hipYaw=frame?-mirror*(Math.PI/2*(1-ease(.48,.88,d))-.28*follow):0
    const shoulderYaw=frame?-mirror*(Math.PI/2*(1-ease(.72,1,d))-.75*follow):0
    if(frame&&role==='pitcher'&&releaseLocal){
      const pelvis=bones.get('pelvis')!,yaw=new THREE.Quaternion().setFromAxisAngle(UP,hipYaw)
      worldRotate(pelvis,baseRot.clone().multiply(yaw).multiply(baseRot.clone().invert()).multiply(pelvis.getWorldQuaternion(new THREE.Quaternion())))
      // This is a constrained generic pose, not recovered shoulder/elbow data.
      // A torso prior supplies the otherwise underdetermined shoulder location.
      const torso=bones.get('spine_01')!
      const tilt=new THREE.Quaternion().setFromEuler(new THREE.Euler(.45*delivery+.38*follow,shoulderYaw-hipYaw,mirror*lowSlot*.65*delivery))
      const worldTilt=baseRot.clone().multiply(tilt).multiply(baseRot.clone().invert())
      worldRotate(torso,worldTilt.multiply(torso.getWorldQuaternion(new THREE.Quaternion())))
      const shoulder=localPoint(bones.get(`upperarm_${armSide}`)!),elbow=localPoint(bones.get(`lowerarm_${armSide}`)!),wrist=localPoint(bones.get(`hand_${armSide}`)!)
      const reach=(shoulder.distanceTo(elbow)+elbow.distanceTo(wrist))*.94+.10
      const delta=releaseLocal.clone().addScaledVector(armDirection,-reach).sub(shoulder).multiplyScalar(delivery)
      delta.y-=lowSlot*.065*Math.sin(Math.PI*d)
      const target=model.localToWorld(localPoint(pelvis).add(delta))
      pelvis.position.copy(pelvis.parent!.worldToLocal(target));model.updateMatrixWorld(true)
      worldRotate(head,baseRot.clone().multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),.15*follow)).multiply(headRestWorld))
    }
    const swing=frame&&frame.batterAction==='swing'?ease(frame.flightSeconds-.16,frame.flightSeconds+.24,frame.timeSeconds)*(1-recover):0
    const batterTurn=frame?mirror*(swing*1.35-ease(-.5,-.15,frame.timeSeconds)*.12*(1-recover)):0
    if(frame&&role==='batter'){
      const spine=bones.get('spine_01')!,turn=new THREE.Quaternion().setFromAxisAngle(UP,batterTurn)
      worldRotate(spine,baseRot.clone().multiply(turn).multiply(baseRot.clone().invert()).multiply(spine.getWorldQuaternion(new THREE.Quaternion())))
    }
    for(const side of ['l','r'] as const){
      const target=feet[side].clone();target.x=(side==='l'?1:-1)*(role==='batter'?.225:.145)
      if(frame&&role==='pitcher'){
        target.applyAxisAngle(UP,-mirror*Math.PI/2)
        // Plant is world-locked before release; extension is never stride length.
        const landingZ=Math.max(.55,(releaseLocal?.z??1.7)-.20)
        if(side===leadSide){
          const plant=ease(.38,.86,d)
          target.z=THREE.MathUtils.lerp(target.z,landingZ,plant);target.x=THREE.MathUtils.lerp(target.x,mirror*.12,plant)
        }else{
          target.z=THREE.MathUtils.lerp(target.z,landingZ-.55,ease(.88,1,d))+.45*follow
          target.x=THREE.MathUtils.lerp(target.x,-mirror*.26,follow)
        }
        const wx=target.x*root.scale.x,wz=-60.5*.3048+target.z*root.scale.x,radius=Math.hypot(wx,wz+59*.3048)
        const profile=[[0,.254],[.8,.254],[1.15,.22],[1.7,.14],[2.2,.06],[9*.3048,0]]
        const i=profile.findIndex(p=>p[0]>=radius)
        const surface=i<0?0:i===0?.254:THREE.MathUtils.lerp(profile[i-1][1],profile[i][1],(radius-profile[i-1][0])/(profile[i][0]-profile[i-1][0]))
        target.y+=(surface-.254)/root.scale.x
        if(side===leadSide)target.y+=Math.sin(Math.PI*ease(0,.68,d))*(.46-.34*lowSlot)*(1-ease(.58,.86,d))
        else target.y+=Math.sin(Math.PI*follow)*.42+follow*.10
      }else if(frame&&role==='batter'&&side===leadSide){
        target.x+=(side==='l'?1:-1)*ease(-.3,.1,frame.timeSeconds)*.06*(1-recover)
        target.y+=Math.sin(Math.PI*ease(-.5,-.05,frame.timeSeconds))*.045
      }
      const hint=frame&&role==='pitcher'?new THREE.Vector3(0,.48,.55).applyAxisAngle(UP,hipYaw).add(new THREE.Vector3(target.x,0,target.z*.5)):new THREE.Vector3(target.x,.48,.4)
      ik(`thigh_${side}`,`calf_${side}`,`foot_${side}`,target,hint)
      const footYaw=frame&&role==='pitcher'?-mirror*Math.PI/2*(1-ease(side===leadSide?.42:.80,side===leadSide?.86:1,d)):0
      worldRotate(bones.get(`foot_${side}`)!,baseRot.clone().multiply(new THREE.Quaternion().setFromAxisAngle(UP,footYaw)).multiply(footRot[side]))
    }
    if(role==='batter'){
      const grip=new THREE.Vector3(-.10*mirror,1.43,.23),direction=new THREE.Vector3(-.38*mirror,.90,-.22).normalize()
      const pivot=localPoint(bones.get('spine_01')!)
      const chestPoint=(p:THREE.Vector3)=>p.sub(pivot).applyAxisAngle(UP,batterTurn).add(pivot)
      if(frame){
        const load=ease(-.5,-.15,frame.timeSeconds)*(1-swing)
        grip.add(new THREE.Vector3(-.05*mirror*load,-.25*Math.sin(Math.PI*swing),-.035*load+.15*Math.sin(Math.PI*swing)))
        const across=new THREE.Vector3(.9*mirror,.12,.40).normalize(),finish=new THREE.Vector3(-.38*mirror,.90,-.22).normalize()
        if(swing<.55)direction.lerp(across,ease(0,.55,swing)).normalize()
        else direction.copy(across).lerp(finish,ease(.55,1,swing)).normalize()
        chestPoint(grip);direction.applyAxisAngle(UP,batterTurn)
      }
      const bottom=left?'r':'l',top=left?'l':'r'
      const forward=new THREE.Vector3(0,0,1).applyAxisAngle(UP,batterTurn);forward.addScaledVector(direction,-forward.dot(direction)).normalize()
      const upperGrip=grip.clone().addScaledVector(direction,.075)
      const wrist=upperGrip.clone().addScaledVector(forward,-.105).addScaledVector(forward.clone().cross(direction).normalize(),top==='l'?-.022:.022)
      ik(`upperarm_${top}`,`lowerarm_${top}`,`hand_${top}`,wrist,chestPoint(new THREE.Vector3(-.48*mirror,1.41,.26)));orientGrip(top,direction)
      // Primary-hand socket owns the bat. Secondary hand follows the bat's
      // lower socket through IK, never a 180-degree palm-frame inversion.
      const primary=localPoint(gripSockets[top])
      const batDirection=new THREE.Vector3(0,0,1).applyQuaternion(bones.get(`hand_${top}`)!.getWorldQuaternion(new THREE.Quaternion())).applyQuaternion(baseRot.clone().invert()).normalize()
      const lower=primary.clone().addScaledVector(batDirection,-.075)
      for(let i=0;i<(frame?8:3);i++){
        const offset=localPoint(gripSockets[bottom]).sub(localPoint(bones.get(`hand_${bottom}`)!))
        ik(`upperarm_${bottom}`,`lowerarm_${bottom}`,`hand_${bottom}`,lower.clone().sub(offset),chestPoint(new THREE.Vector3(.32*mirror,1.25,.46)));orientGrip(bottom,batDirection)
      }
      holdBat(bottom,lower,batDirection);holdBat(top,primary,batDirection)
      bat.visible=true;glove.visible=false;bat.position.copy(lower);bat.quaternion.setFromUnitVectors(UP,batDirection)
      worldRotate(head,baseRot.clone().multiply(new THREE.Quaternion().setFromAxisAngle(UP,mirror*Math.PI/2)))
    }else{
      bat.visible=false;glove.visible=true
      const chest=localPoint(bones.get('spine_03')!),chestOffset=(p:THREE.Vector3)=>p.applyAxisAngle(UP,shoulderYaw).add(chest)
      for(const side of ['l','r'] as const){
        const target=frame?chestOffset(new THREE.Vector3((side==='l'?.035:-.025)*mirror,-.14,.23)):new THREE.Vector3((side==='l'?.035:-.025)*mirror,1.24,.28)
        if(frame&&side!==armSide){
          const reach=ease(.32,.65,d)*(1-ease(.78,1,d))
          target.lerp(chest.clone().add(new THREE.Vector3(mirror*.08,-.05,.62)),reach)
        }
        ik(`upperarm_${side}`,`lowerarm_${side}`,`hand_${side}`,target,frame?target.clone().add(new THREE.Vector3(side==='l'?.38:-.38,-.2,-.1)):new THREE.Vector3(side==='l'?.38:-.38,1.05,.18))
      }
      const hand=bones.get(left?'hand_r':'hand_l')!;glove.position.copy(model.worldToLocal(hand.localToWorld(new THREE.Vector3(0,.075,0))));glove.quaternion.copy(model.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(hand.getWorldQuaternion(new THREE.Quaternion())))
      if(frame&&releaseLocal){
        const shoulder=localPoint(bones.get(`upperarm_${armSide}`)!)
        const ready=chestOffset(new THREE.Vector3((armSide==='l'?.035:-.025)*mirror,-.14,.23))
        const separated=shoulder.clone().add(new THREE.Vector3(-mirror*.28,-.36,-.20))
        const cocked=shoulder.clone().add(new THREE.Vector3(-mirror*.30,.23,-.25))
        const wristAtRelease=releaseLocal.clone().addScaledVector(armDirection,-.10)
        const wrist=d<.58?ready.clone().lerp(separated,ease(.30,.58,d)):d<.84?separated.clone().lerp(cocked,ease(.58,.84,d)):cocked.clone().lerp(wristAtRelease,ease(.84,1,d))
        wrist.lerp(wristAtRelease.clone().add(new THREE.Vector3(mirror*.3,-.55,.35)),follow)
        wrist.lerp(ready,recover)
        ik(`upperarm_${armSide}`,`lowerarm_${armSide}`,`hand_${armSide}`,wrist,shoulder.clone().add(new THREE.Vector3(-mirror*.45,.12,-.22)))
        const throwingHand=bones.get(`hand_${armSide}`)!,q=throwingHand.getWorldQuaternion(new THREE.Quaternion())
        const handAxis=new THREE.Vector3(0,1,0).applyQuaternion(q),worldDirection=armDirection.clone().applyQuaternion(baseRot)
        const orientation=new THREE.Quaternion().setFromUnitVectors(handAxis,worldDirection).multiply(q)
        worldRotate(throwingHand,q.clone().slerp(orientation,1-recover))
      }
    }
    heldBall.visible=role==='pitcher'&&Boolean(frame&&frame.timeSeconds<0)
    if(heldBall.visible){heldBall.position.copy(localPoint(releaseSockets[armSide]));heldBall.scale.setScalar(1/root.scale.x)}
    const kit=`${identity?.team||''}:${identity?.home}`
    if(kit!==lastKit){
      const color=PALETTES[identity?.team||'']||'#28465b',pants=identity?.home===false?'#9ca5ac':'#e9ece8'
      mats.get('uniform_jersey')?.color.set(identity?.home===false?color:'#f3f3ed');mats.get('uniform_pants')?.color.set(pants);mats.get('socks')?.color.set(color)
      uniformTrim.forEach(m=>(m.material as THREE.MeshStandardMaterial).color.set(identity?.home===false?'#dce2df':color))
      mats.get('uniform_cuff')?.color.set(identity?.home===false?'#dce2df':color)
      ;(crown.material as THREE.MeshStandardMaterial).color.set(color);(visor.material as THREE.MeshStandardMaterial).color.set(color);(badge.material as THREE.MeshStandardMaterial).color.set(identity?.home===false?'#e5e9e5':color)
      lastKit=kit
    }
    model.updateMatrixWorld(true)
  }
  function staticArmAngle(angle:number|null|undefined,hand:string|undefined){
    if(role!=='pitcher'||angle==null||!Number.isFinite(angle)||Math.abs(angle)>90||(hand!=='L'&&hand!=='R'))return
    const side=hand==='L'?'l':'r',sign=hand==='L'?1:-1,radians=angle*Math.PI/180
    // Frozen frontal-plane illustration only: no clock, leg/root movement or inferred stride.
    const direction=new THREE.Vector3(sign*Math.cos(radians),Math.sin(radians),0)
    const upper=bones.get(`upperarm_${side}`)!,lower=bones.get(`lowerarm_${side}`)!,wrist=bones.get(`hand_${side}`)!
    model.updateMatrixWorld(true)
    const shoulder=upper.getWorldPosition(new THREE.Vector3()),axis=direction.clone().applyQuaternion(model.getWorldQuaternion(new THREE.Quaternion()))
    aim(upper,lower,shoulder.clone().add(axis));aim(lower,wrist,lower.getWorldPosition(new THREE.Vector3()).add(axis))
    const palmAxis=new THREE.Vector3(0,1,0).applyQuaternion(wrist.getWorldQuaternion(new THREE.Quaternion()))
    worldRotate(wrist,new THREE.Quaternion().setFromUnitVectors(palmAxis,axis).multiply(wrist.getWorldQuaternion(new THREE.Quaternion())))
    const gloveHand=bones.get(hand==='L'?'hand_r':'hand_l')!
    glove.position.copy(model.worldToLocal(gloveHand.localToWorld(new THREE.Vector3(0,.075,0))));glove.quaternion.copy(model.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(gloveHand.getWorldQuaternion(new THREE.Quaternion())))
    model.updateMatrixWorld(true)
  }
  function fitSwingBat(hand:'L'|'R'){
    const top=hand==='L'?'l':'r',bottom=hand==='L'?'r':'l'
    const upper=localPoint(bones.get(`hand_${top}`)!),lower=localPoint(bones.get(`hand_${bottom}`)!)
    const direction=upper.clone().sub(lower)
    if(direction.length()<.025)return false
    direction.normalize()
    const centre=localPoint(gripSockets[top]).add(localPoint(gripSockets[bottom])).multiplyScalar(.5)
    // B has no hand rotation or bat endpoints. A shared generic prop grip
    // constrains both hands; this is explicitly NOT a measured bat path.
    const hintTop=localPoint(bones.get(`lowerarm_${top}`)!),hintBottom=localPoint(bones.get(`lowerarm_${bottom}`)!)
    const sides=[top,bottom] as const
    const shoulder=Object.fromEntries(sides.map(s=>[s,localPoint(bones.get(`upperarm_${s}`)!)]))
    const reach=Object.fromEntries(sides.map(s=>[s,shoulder[s].distanceTo(localPoint(bones.get(`lowerarm_${s}`)!))+localPoint(bones.get(`lowerarm_${s}`)!).distanceTo(localPoint(bones.get(`hand_${s}`)!))-.015]))
    for(let i=0;i<24;i++){
      for(const s of sides){
        const offset=localPoint(gripSockets[s]).sub(localPoint(bones.get(`hand_${s}`)!))
        const target=centre.clone().addScaledVector(direction,s===top?.0375:-.0375).sub(offset)
        const delta=target.clone().sub(shoulder[s]),excess=delta.length()-reach[s]
        if(excess>0){const correction=delta.normalize().multiplyScalar(excess);centre.sub(correction);target.sub(correction)}
        ik(`upperarm_${s}`,`lowerarm_${s}`,`hand_${s}`,target,s===top?hintTop:hintBottom);orientGrip(s,direction)
      }
    }
    const primary=localPoint(gripSockets[top]),secondary=localPoint(gripSockets[bottom])
    const axis=primary.clone().sub(secondary).normalize()
    holdBat(bottom,secondary,axis);holdBat(top,primary,axis)
    bat.position.copy(secondary);bat.quaternion.setFromUnitVectors(UP,axis);bat.visible=true;glove.visible=false
    model.updateMatrixWorld(true);return true
  }
  return {root,model,update,mixer,bones,baseHeight,gripSockets,releaseSockets,rest,fitSwingBat,staticArmAngle}
}

export function applyVideoPose(actor:Actor,clip:ReplayVideoPoseClip,progress:number){
  const time=THREE.MathUtils.lerp(clip.sourceStart,clip.sourceEnd,THREE.MathUtils.clamp(progress,0,1))
  const end=clip.frames.findIndex(f=>f.sourceTime>=time),i=end<0?clip.frames.length-1:end
  const a=clip.frames[Math.max(0,i-1)],b=clip.frames[i],t=THREE.MathUtils.clamp((time-a.sourceTime)/(b.sourceTime-a.sourceTime||1),0,1)
  for(const r of actor.rest){r.bone.position.copy(r.position);r.bone.quaternion.copy(r.quaternion)}
  clip.boneNames.forEach((n,j)=>{
    const bone=actor.bones.get(n);if(!bone)return
    bone.quaternion.fromArray(a.rotations,j*4).slerp(new THREE.Quaternion().fromArray(b.rotations,j*4),t)
  })
  const offset=new THREE.Vector3().fromArray(a.root).lerp(new THREE.Vector3().fromArray(b.root),t)
  actor.root.position.addScaledVector(offset,actor.root.scale.x);actor.root.updateMatrixWorld(true)
  const glove=actor.model.getObjectByName('fielding-glove')!,hand=actor.bones.get('hand_l')!
  glove.position.copy(actor.model.worldToLocal(hand.getWorldPosition(new THREE.Vector3())))
  glove.quaternion.copy(actor.model.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(hand.getWorldQuaternion(new THREE.Quaternion())))
}

type Rig={root:THREE.Group;model:THREE.Group;bones:Map<string,THREE.Bone>;rest:{bone:THREE.Bone;position:THREE.Vector3;quaternion:THREE.Quaternion}[];fitSwingBat?:(hand:'L'|'R')=>boolean}
const v=(p:number[])=>new THREE.Vector3(p[0],-p[1],-p[2])
function frame(x:THREE.Vector3,y:THREE.Vector3){
  y.normalize();x.addScaledVector(y,-x.dot(y)).normalize()
  if(x.lengthSq()<.5||y.lengthSq()<.5)return null
  return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x,y,x.clone().cross(y).normalize()))
}
// Rotations only: anatomical sides, fixed rig lengths and bend planes come from
// B points. No two-bone target/hint IK, Euler knee rotations or planted-foot lock.
export function retargetReferencePose(actor:Rig,input:ReplayReferencePose):boolean{
  const swing=input.kind==='batter-swing'&&input.playerId===672695&&['L','R'].includes(input.hand)
  if(input.version!=='motionbert_reference_points_v1'||(!swing&&![669203,518876].includes(input.playerId))||!input.points||input.points.length!==17||!input.points.flat().every(Number.isFinite))return false
  for(const r of actor.rest){r.bone.position.copy(r.position);r.bone.quaternion.copy(r.quaternion)}
  actor.model.updateMatrixWorld(true)
  const bone=(name:string)=>actor.bones.get(name)!
  const pos=(name:string)=>bone(name).getWorldPosition(new THREE.Vector3())
  const restPos=new Map([...actor.bones].map(([n,b])=>[n,b.getWorldPosition(new THREE.Vector3())]))
  const restRot=new Map([...actor.bones].map(([n,b])=>[n,b.getWorldQuaternion(new THREE.Quaternion())]))
  const worldRotate=(name:string,q:THREE.Quaternion)=>{const b=bone(name);b.quaternion.copy(b.parent!.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(q));actor.model.updateMatrixWorld(true)}
  const cameraTurn=new THREE.Quaternion().setFromAxisAngle(UP,swing?input.cameraYaw??Math.PI:0)
  const points=input.points.map(p=>v(p).applyQuaternion(cameraTurn)),baseline=input.baseline.map(p=>v(p).applyQuaternion(cameraTurn))
  const hipX=points[4]!.clone().sub(points[1]!),up=points[8]!.clone().sub(points[0]!)
  const restX=restPos.get('thigh_l')!.clone().sub(restPos.get('thigh_r')!),restUp=restPos.get('spine_03')!.clone().sub(restPos.get('pelvis')!)
  const restBody=frame(restX.clone(),restUp.clone()),body=frame(hipX.clone(),up.clone())
  const shoulders=frame(points[11]!.clone().sub(points[14]!),up.clone())
  if(!restBody||!body||!shoulders)return false
  const change=body.clone().multiply(restBody.clone().invert())
  const legLength=(s:'l'|'r')=>restPos.get(`thigh_${s}`)!.distanceTo(restPos.get(`calf_${s}`)!)+restPos.get(`calf_${s}`)!.distanceTo(restPos.get(`foot_${s}`)!)
  const scale=(legLength('l')+legLength('r'))/2/input.legLengthUnits
  if(!Number.isFinite(scale)||scale<=0)return false
  if(swing){
    const footOrigin=baseline[3]!.clone().add(baseline[6]!).multiplyScalar(.5)
    const pelvisTarget=actor.root.position.clone().add(points[0]!.clone().sub(footOrigin).multiplyScalar(scale))
    actor.root.position.add(pelvisTarget.sub(restPos.get('pelvis')!))
  }else actor.root.position.add(points[0]!.clone().sub(baseline[0]!).multiplyScalar(scale))
  actor.root.updateMatrixWorld(true)
  worldRotate('pelvis',change.clone().multiply(restRot.get('pelvis')!))
  const chestChange=shoulders.clone().multiply(restBody.clone().invert())
  worldRotate('spine_01',chestChange.clone().multiply(restRot.get('spine_01')!))
  // The 17-point output has no measured head/hand/toe orientation: preserve
  // their neutral local rotations rather than inventing a recovered rotation.
  let chainIndex=0
  for(const s of ['l','r'] as const){
    const chains:[string,string,string,number,number,number][]=[
      [`thigh_${s}`,`calf_${s}`,`foot_${s}`,s==='l'?4:1,s==='l'?5:2,s==='l'?6:3],
      [`upperarm_${s}`,`lowerarm_${s}`,`hand_${s}`,s==='l'?11:14,s==='l'?12:15,s==='l'?13:16],
    ]
    for(const [a,b,c,ia,ib,ic] of chains){
      const upper=points[ib]!.clone().sub(points[ia]!).normalize(),lower=points[ic]!.clone().sub(points[ib]!).normalize()
      const axis=input.bendAxes?.[chainIndex*2],lowerAxis=input.bendAxes?.[chainIndex*2+1];chainIndex++
      const bend=axis?new THREE.Vector3(...axis).applyQuaternion(cameraTurn):upper.clone().cross(lower),restAxis=new THREE.Vector3(1,0,0).applyQuaternion(restRot.get(a)!)
      const expected=restAxis.clone().applyQuaternion(change)
      if(bend.lengthSq()<1e-5)bend.copy(expected)
      // Keep the roll axis on the same hemisphere when nearly straight.
      if(!axis&&bend.dot(expected)<0)bend.negate()
      const fromUpper=frame(restAxis.clone(),restPos.get(b)!.clone().sub(restPos.get(a)!))
      const fromLower=frame(restAxis.clone(),restPos.get(c)!.clone().sub(restPos.get(b)!))
      const toUpper=frame(bend.clone(),upper),toLower=frame(lowerAxis?new THREE.Vector3(...lowerAxis).applyQuaternion(cameraTurn):bend.clone(),lower)
      if(!fromUpper||!fromLower||!toUpper||!toLower)return false
      worldRotate(a,toUpper.multiply(fromUpper.invert()).multiply(restRot.get(a)!))
      worldRotate(b,toLower.multiply(fromLower.invert()).multiply(restRot.get(b)!))
    }
  }
  if(swing){
    for(const s of ['l','r'])worldRotate(`foot_${s}`,restRot.get(`foot_${s}`)!)
    // Presentation ground clearance only. Preserve both feet's X/Z travel and
    // their relative lift; never pin either foot to its starting position.
    const lowest=Math.min(pos('foot_l').y,pos('foot_r').y)
    actor.root.position.y+=.075*actor.root.scale.x-lowest;actor.root.updateMatrixWorld(true)
    return Boolean(actor.fitSwingBat?.(input.hand as 'L'|'R'))&&[...actor.bones.values()].every(b=>b.matrixWorld.elements.every(Number.isFinite))
  }
  const glove=actor.model.getObjectByName('fielding-glove')!,hand=bone(input.hand==='L'?'hand_r':'hand_l')
  glove.position.copy(actor.model.worldToLocal(hand.getWorldPosition(new THREE.Vector3())))
  glove.quaternion.copy(actor.model.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(hand.getWorldQuaternion(new THREE.Quaternion())))
  actor.model.updateMatrixWorld(true)
  return [...actor.bones.values()].every(b=>b.matrixWorld.elements.every(Number.isFinite))
}

export async function createReplayActors(signal:AbortSignal){
  const response=await fetch(actorUrl,{signal});if(!response.ok)throw new Error('Character asset unavailable')
  const asset=await new GLTFLoader().parseAsync(await response.arrayBuffer(),'')
  if(signal.aborted){disposeObjects(asset.scene);throw new Error('Character load cancelled')}
  const root=new THREE.Group();root.name='generic-baseball-actors'
  const batter=makeActor(asset.scene,asset.animations,'batter'),pitcher=makeActor(asset.scene,asset.animations,'pitcher');root.add(batter.root,pitcher.root)
  const actors:Actor[]=[batter,pitcher]
  return {root,
    update(input:Replay3DInput,time=0){
      root.visible=input.showActors!==false
      batter.root.visible=!input.previewOnly&&(input.stand==='L'||input.stand==='R');pitcher.root.visible=PITCHER_ACTOR_AVAILABLE&&(input.pitcherActor?.hand==='L'||input.pitcherActor?.hand==='R')
      batter.root.position.set((input.stand==='R'?-1:1)*3.2*.3048,0,-17/24*.3048);batter.root.rotation.y=input.stand==='R'?Math.PI/2:-Math.PI/2
      pitcher.root.position.set(0,.254,-60.5*.3048);pitcher.root.rotation.y=0
      batter.update({...input.batterActor,hand:input.stand,heightM:input.batterHeightM},'ready',0)
      if(PITCHER_ACTOR_AVAILABLE){pitcher.update(input.pitcherActor,'ready',0);pitcher.staticArmAngle(input.armAngleDeg,input.pitcherActor?.hand)}
      if(BATTER_SWING_RETARGET_AVAILABLE&&input.batterSwingReference)batter.root.visible=retargetReferencePose(batter,input.batterSwingReference)
      const pilot=input.videoPose
      if(VIDEO_POSE_RETARGET_AVAILABLE&&input.previewOnly&&pilot&&pilot.clip.previewOnly&&pilot.clip.playerId===pilot.playerId&&[702056,657044].includes(pilot.playerId))applyVideoPose(pitcher,pilot.clip,pilot.progress)
      if(REFERENCE_B_RETARGET_AVAILABLE&&input.previewOnly&&input.referencePose){
        pitcher.root.visible=retargetReferencePose(pitcher,input.referencePose)
      }
    },
    dispose(){actors.forEach(a=>a.mixer.stopAllAction());const holder=new THREE.Group();holder.add(root,asset.scene);disposeObjects(holder);holder.clear()},
  }
}
