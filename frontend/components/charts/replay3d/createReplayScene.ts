import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { buildReplayWorld } from './buildReplayWorld'
import { REPLAY_CAMERAS, worldPoint, type Replay3DInput, type ReplayView } from './replayContract'
import { createReplayActors } from './createReplayActors'

export function createReplayScene(host:HTMLElement,onPick:(key:string)=>void,onFailure:(message:string)=>void,onActorStatus:(message:string)=>void=()=>{},onHover:(key:string|null)=>void=()=>{}) {
  const world=buildReplayWorld(),scene=new THREE.Scene()
  scene.background=new THREE.Color(0x172b39);scene.fog=new THREE.Fog(0x172b39,48,120)
  scene.add(world.root,new THREE.HemisphereLight(0xeaf6ff,0x3c4d32,2.4))
  const sun=new THREE.DirectionalLight(0xffefd3,2.5);sun.position.set(-12,20,8);scene.add(sun)
  let renderer:THREE.WebGLRenderer
  try {renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'})}
  catch(error){world.dispose();throw error}
  const canvas=renderer.domElement
  canvas.tabIndex=0;canvas.setAttribute('role','img');canvas.setAttribute('aria-label','3D historical pitch scene. Drag or arrows to orbit, wheel or plus/minus to dolly, Home to reset.')
  host.appendChild(canvas);renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5))
  const camera=new THREE.PerspectiveCamera(52,1,.03,180),controls=new OrbitControls(camera,canvas)
  controls.enablePan=false;controls.enableDamping=false;controls.minDistance=1.8;controls.maxDistance=36
  controls.minPolarAngle=THREE.MathUtils.degToRad(1);controls.maxPolarAngle=THREE.MathUtils.degToRad(115)
  let currentView:ReplayView='catcher',disposed=false,frame=0
  let lastInput:Replay3DInput|undefined
  const actorAbort=new AbortController()
  const render=()=>{frame=0;if(!disposed&&!document.hidden)try{world.previewActors(performance.now()/1000);renderer.render(scene,camera);if(world.idlePreview)requestRender()}catch{onFailure('3D rendering failed. Use the schematic or retry 3D.')}}
  const requestRender=()=>{if(!disposed&&!document.hidden&&!frame)frame=requestAnimationFrame(render)}
  const resize=()=>{
    if(disposed)return
    const {width,height}=host.getBoundingClientRect();if(!width||!height)return
    renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix();requestRender()
  }
  const observer=new ResizeObserver(resize)
  const visibility=()=>{if(document.hidden&&frame){cancelAnimationFrame(frame);frame=0}else requestRender()}
  const lost=(event:Event)=>{event.preventDefault();onFailure('WebGL context lost. Use the schematic or retry 3D.')}
  function reset(view:ReplayView=currentView){
    currentView=view;const preset=REPLAY_CAMERAS[view]
    if(lastInput?.previewOnly){camera.position.set(-3.6,2,-14.2);camera.fov=45;camera.updateProjectionMatrix();controls.target.set(0,1.2,-17.6);controls.update();requestRender();return}
    camera.position.set(...preset.position);camera.fov=preset.fov;camera.updateProjectionMatrix()
    if(view==='batter-detail')camera.position.x=(lastInput?.stand==='L'?-1:1)*preset.position[0]+(lastInput?.stand==='L'?1:-1)*3.2*.3048
    controls.target.set(...preset.target);controls.update();requestRender()
    if(view==='pitcher-detail'&&lastInput?.points[0]){controls.target.set(...worldPoint(lastInput.points[0]));camera.position.copy(controls.target).add(new THREE.Vector3(2.4,1.1,4));controls.update()}
    if(view==='batter-detail'){controls.target.x=(lastInput?.stand==='L'?1:-1)*3.2*.3048;controls.update()}
  }
  const keydown=(event:KeyboardEvent)=>{
    if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-','=','Home'].includes(event.key))return
    event.preventDefault();event.stopPropagation()
    if(event.key==='Home'){reset();return}
    const offset=camera.position.clone().sub(controls.target),spherical=new THREE.Spherical().setFromVector3(offset)
    if(event.key==='ArrowLeft')spherical.theta-=.08
    if(event.key==='ArrowRight')spherical.theta+=.08
    if(event.key==='ArrowUp')spherical.phi-=.06
    if(event.key==='ArrowDown')spherical.phi+=.06
    if(event.key==='+'||event.key==='=')spherical.radius*=.9
    if(event.key==='-')spherical.radius*=1.1
    spherical.phi=THREE.MathUtils.clamp(spherical.phi,controls.minPolarAngle,controls.maxPolarAngle)
    spherical.radius=THREE.MathUtils.clamp(spherical.radius,controls.minDistance,controls.maxDistance)
    camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));controls.update();requestRender()
  }
  let down:[number,number]|null=null
  const hover=(event:PointerEvent)=>{
    if(down){onHover(null);return}
    const bounds=canvas.getBoundingClientRect(),ray=new THREE.Raycaster()
    ray.params.Line={threshold:.08};ray.setFromCamera(new THREE.Vector2((event.clientX-bounds.left)/bounds.width*2-1,-(event.clientY-bounds.top)/bounds.height*2+1),camera)
    const hit=ray.intersectObjects(world.ball.visible?[world.ball,...world.candidates]:world.candidates,false)[0]
    onHover(hit?.object.userData.pitchKey?String(hit.object.userData.pitchKey):null)
  }
  const leave=()=>{down=null;onHover(null)}
  const pointerdown=(event:PointerEvent)=>{down=event.button===0?[event.clientX,event.clientY]:null;canvas.focus({preventScroll:true})}
  const pointerup=(event:PointerEvent)=>{
    if(!down||Math.hypot(event.clientX-down[0],event.clientY-down[1])>5){down=null;return}
    down=null;const bounds=canvas.getBoundingClientRect(),ray=new THREE.Raycaster()
    ray.params.Line={threshold:.1};ray.setFromCamera(new THREE.Vector2((event.clientX-bounds.left)/bounds.width*2-1,-(event.clientY-bounds.top)/bounds.height*2+1),camera)
    const hit=ray.intersectObjects(world.ball.visible?[world.ball,...world.candidates]:world.candidates,false)[0]
    if(hit?.object.userData.pitchKey)onPick(String(hit.object.userData.pitchKey))
  }
  const orbitChange=()=>{
    // Allow lower viewing angles around the focus without entering the turf.
    if(camera.position.y<.12){camera.position.y=.12;controls.update()}
    requestRender()
  }
  controls.addEventListener('change',orbitChange)
  canvas.addEventListener('keydown',keydown);canvas.addEventListener('pointerdown',pointerdown);canvas.addEventListener('pointerup',pointerup);canvas.addEventListener('webglcontextlost',lost)
  canvas.addEventListener('pointermove',hover);canvas.addEventListener('pointerleave',leave)
  document.addEventListener('visibilitychange',visibility);observer.observe(host);reset();resize()
  const actorTimeout=setTimeout(()=>actorAbort.abort(),15000)
  void createReplayActors(actorAbort.signal).then(actors=>{
    if(disposed){actors.dispose();return}world.attachActors(actors);onActorStatus('Generic rig ready.');requestRender()
  }).catch(()=>{if(!disposed)onActorStatus('Character asset unavailable; position guide and pitch analysis remain usable.')}).finally(()=>clearTimeout(actorTimeout))
  return {
    update(input:Replay3DInput){if(!disposed){lastInput=input;world.update(input);requestRender()}},reset,
    dispose(){
      if(disposed)return;disposed=true;if(frame)cancelAnimationFrame(frame)
      actorAbort.abort();clearTimeout(actorTimeout)
      observer.disconnect();document.removeEventListener('visibilitychange',visibility)
      canvas.removeEventListener('keydown',keydown);canvas.removeEventListener('pointerdown',pointerdown);canvas.removeEventListener('pointerup',pointerup);canvas.removeEventListener('webglcontextlost',lost)
      canvas.removeEventListener('pointermove',hover);canvas.removeEventListener('pointerleave',leave)
      controls.removeEventListener('change',orbitChange);controls.dispose();world.dispose();renderer.dispose();renderer.forceContextLoss();canvas.remove()
    },
  }
}
