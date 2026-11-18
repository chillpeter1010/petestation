import * as THREE from 'three'
import { FT_TO_METRES as FT, PLATE_FRONT_Y_FT, RUBBER_Y_FT, sampleReplay, worldPoint, type Replay3DInput, type ReplayPoint } from './replayContract'

export function disposeGroup(group:THREE.Object3D) {
  const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>()
  group.traverse(object=>{
    const drawable=object as THREE.Mesh
    if(drawable.geometry)geometries.add(drawable.geometry)
    if(drawable.material)for(const material of Array.isArray(drawable.material)?drawable.material:[drawable.material])materials.add(material)
  })
  for(const geometry of geometries)geometry.dispose()
  for(const material of materials)material.dispose()
  group.clear()
}

export function buildReplayWorld() {
  const root=new THREE.Group();root.name='historical-world-metres'
  const field=new THREE.Group(),zone=new THREE.Group(),pitches=new THREE.Group(),positionGuide=new THREE.Group()
  field.name='calibration-field';zone.name='statcast-zone';pitches.name='historical-pitches';positionGuide.name='generic-position-guide'
  root.add(field,zone,pitches,positionGuide)
  let texture:THREE.DataTexture|undefined,previous:Replay3DInput|undefined,selectedLine:THREE.Line|undefined
  let actors:{root:THREE.Group;update:(input:Replay3DInput,time?:number)=>void;dispose:()=>void}|undefined
  const mesh=(geometry:THREE.BufferGeometry,color:string|number,position:[number,number,number],name:string,parent=field)=>{
    const item=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:.94}))
    item.position.set(...position);item.name=name;parent.add(item);return item
  }
  const line=(points:[number,number,number][],color:string|number,opacity=1,parent=field)=>{
    const item=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(...p))),new THREE.LineBasicMaterial({color,transparent:opacity<1,opacity}))
    parent.add(item);return item
  }
  const ground=mesh(new THREE.PlaneGeometry(160,160),0x326b43,[0,-.015,-30],'ground')
  ground.rotation.x=-Math.PI/2
  for(let i=0;i<14;i++){
    const stripe=mesh(new THREE.PlaneGeometry(74,4),i%2?0x386f46:0x417a4b,[0,-.012,-i*4],'turf-stripe')
    stripe.rotation.x=-Math.PI/2
  }
  for(const [radius,z] of [[3.8,0]] as const){
    const dirt=mesh(new THREE.CircleGeometry(radius,64),0x996742,[0,0,z],'dirt');dirt.rotation.x=-Math.PI/2
  }
  const moundProfile=[[9*FT,0],[2.2,.06],[1.7,.14],[1.15,.22],[.8,.254],[0,.254]].map(([r,y])=>new THREE.Vector2(r,y))
  mesh(new THREE.LatheGeometry(moundProfile,64),0x996742,[0,.002,-59*FT],'mound')
  mesh(new THREE.BoxGeometry(2*FT,.025,.5*FT),0xeeeadd,[0,.267,-RUBBER_Y_FT*FT],'pitching-rubber')
  const plateShape=new THREE.Shape()
  for(const [i,[x,y]] of [[-17/24,0],[17/24,0],[17/24,17/24],[0,17/12],[-17/24,17/24]].entries()){
    if(!i)plateShape.moveTo(x*FT,y*FT);else plateShape.lineTo(x*FT,y*FT)
  }
  plateShape.closePath()
  const plate=mesh(new THREE.ShapeGeometry(plateShape),0xf6f0df,[0,.012,0],'home-plate');plate.rotation.x=-Math.PI/2
  // Two ground-plane boxes: 4 x 6 ft, centred along the plate; never shifted in screen pixels.
  for(const side of [-1,1]){
    const inner=17/24+.5,outer=inner+4,centerY=17/24
    const corners=[[side*inner,centerY-3],[side*outer,centerY-3],[side*outer,centerY+3],[side*inner,centerY+3],[side*inner,centerY-3]]
    line(corners.map(([x,y])=>[x*FT,.02,-y*FT]),0xf8f1d9).name=`batter-box-${side}`
  }
  for(const side of [-1,1])line([[0,.018,0],[side*27.4,.018,-27.4]],0xf8f1d9,.8)
  const wall=mesh(new THREE.CylinderGeometry(58,58,4,72,1,true),0x1b4144,[0,2,-18],'illustrative-outfield-wall')
  ;(wall.material as THREE.MeshStandardMaterial).side=THREE.DoubleSide
  // Deliberately no stadium photograph or human sprite in this geometry slice.
  const ball=mesh(new THREE.SphereGeometry(.037,14,10),0xffffff,[0,0,0],'ball',root)
  const release=mesh(new THREE.SphereGeometry(.075,14,10),0xffc454,[0,0,0],'measured-release',root)
  const releaseStem=line([[0,0,0],[0,0,0]],0xffc454,.6,root);releaseStem.name='release-ground-reference'
  const scoutRing=new THREE.Mesh(new THREE.RingGeometry(.92,1,64),new THREE.MeshBasicMaterial({color:0xffd34d,side:THREE.DoubleSide,depthTest:false,depthWrite:false}))
  scoutRing.name='historical-swing-concentration-not-observed-intent';scoutRing.renderOrder=8;scoutRing.visible=false;root.add(scoutRing)
  const guide=mesh(new THREE.TorusGeometry(.22,.018,6,28),0x81ddf2,[0,.03,0],'batter-feet-guide',positionGuide);guide.rotation.x=-Math.PI/2
  const guideStem=line([[0,0,0],[0,1.65,0]],0x81ddf2,.5,positionGuide)
  guideStem.name='generic-height-guide-not-player-model'
  const candidates:THREE.Object3D[]=[]
  const previewStage=new THREE.Group();previewStage.name='video-pose-stage';root.add(previewStage)
  const stage=mesh(new THREE.PlaneGeometry(9,8),0x31464b,[0,.254,-RUBBER_Y_FT*FT],'reference-stage',previewStage);stage.rotation.x=-Math.PI/2
  const grid=new THREE.GridHelper(8,16,0x82aaa7,0x496568);grid.position.set(0,.255,-RUBBER_Y_FT*FT);previewStage.add(grid);previewStage.visible=false

  function update(input:Replay3DInput) {
    scoutRing.visible=Boolean(input.scoutTarget)&&!input.previewOnly
    if(input.scoutTarget){
      const {u,v}=input.scoutTarget
      scoutRing.position.set((-17/24+u*17/12)*FT,(input.zoneBottom+v*(input.zoneTop-input.zoneBottom))*FT,-PLATE_FRONT_Y_FT*FT+.008)
      scoutRing.scale.setScalar((.55-.36*Math.max(0,Math.min(1,input.progress)))*FT)
    }
    field.visible=!input.previewOnly;zone.visible=!input.previewOnly;pitches.visible=!input.previewOnly&&!input.batterSwingReference;previewStage.visible=Boolean(input.previewOnly)
    if(previous?.zoneTop!==input.zoneTop||previous?.zoneBottom!==input.zoneBottom||previous?.heatmap!==input.heatmap){
      disposeGroup(zone);texture?.dispose();texture=undefined
      const z=-PLATE_FRONT_Y_FT*FT,half=17/24*FT,bottom=input.zoneBottom*FT,top=input.zoneTop*FT
      const outline=(x0:number,y0:number,x1:number,y1:number,color:number)=>line([[x0,y0,z],[x1,y0,z],[x1,y1,z],[x0,y1,z],[x0,y0,z]],color,1,zone)
      outline(-half,bottom,half,top,0xffffff).name='true-zone-17-inch'
      outline(-half-.18*FT,bottom-.18*FT,half+.18*FT,top+.18*FT,0x75f3cd).name='margin-guide-only'
      if(input.heatmap.length){
        const size=256,pad=Math.max(.3,...input.heatmap.flatMap(b=>[-b.bounds[0],-b.bounds[1],b.bounds[2]-1,b.bounds[3]-1])),span=1+2*pad,bytes=new Uint8Array(size*size*4)
        for(const band of input.heatmap){
          const [x0,y0,x1,y1]=band.bounds,color=new THREE.Color(band.color).convertLinearToSRGB()
          for(let y=Math.max(0,Math.floor((y0+pad)/span*size));y<Math.min(size,Math.ceil((y1+pad)/span*size));y++){
            for(let x=Math.max(0,Math.floor((x0+pad)/span*size));x<Math.min(size,Math.ceil((x1+pad)/span*size));x++){
              const offset=(y*size+x)*4;bytes.set([Math.round(color.r*255),Math.round(color.g*255),Math.round(color.b*255),Math.round(band.opacity*255)],offset)
            }
          }
        }
        texture=new THREE.DataTexture(bytes,size,size);texture.colorSpace=THREE.SRGBColorSpace;texture.needsUpdate=true
        texture.magFilter=THREE.LinearFilter;texture.minFilter=THREE.LinearFilter
        const overlay=new THREE.Mesh(new THREE.PlaneGeometry(2*half*span,(top-bottom)*span),new THREE.MeshBasicMaterial({map:texture,transparent:true,side:THREE.DoubleSide,depthWrite:false}))
        overlay.position.set(0,(top+bottom)/2,z);zone.add(overlay)
      }
    }
    if(previous?.points!==input.points||previous?.paths!==input.paths||previous?.color!==input.color||previous?.selectedKey!==input.selectedKey){
      disposeGroup(pitches);candidates.length=0
      for(const path of input.paths){
        if(path.key===input.selectedKey)continue
        const item=line(path.points.map(worldPoint),path.color,.3,pitches)
        item.userData.pitchKey=path.key;candidates.push(item)
        const end=path.points.at(-1)
        if(end){const dot=mesh(new THREE.SphereGeometry(.035,8,6),path.color,worldPoint(end),'pitch-location',pitches);dot.userData.pitchKey=path.key;candidates.push(dot)}
      }
      selectedLine=line(input.points.map(worldPoint),input.color,1,pitches);selectedLine.name='selected-source-path'
      selectedLine.userData.pitchKey=input.selectedKey;candidates.push(selectedLine)
      if(input.points[0]){
        const start=worldPoint(input.points[0]);release.position.set(...start)
        releaseStem.geometry.dispose();releaseStem.geometry=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(start[0],.02,start[2]),new THREE.Vector3(...start)])
      }
    }
    const current=sampleReplay(input.points,input.progress)
    ball.userData.pitchKey=input.selectedKey
    ball.visible=!input.batterSwingReference&&Boolean(current)&&(!input.motion||input.motion.timeSeconds>=0);release.visible=!input.batterSwingReference&&Boolean(input.points.length);releaseStem.visible=release.visible
    if(current)ball.position.set(...worldPoint(current))
    positionGuide.visible=!input.previewOnly&&(!actors||input.showActors===false)&&(input.stand==='R'||input.stand==='L')
    positionGuide.position.set((input.stand==='R'?-1:1)*3.2*FT,0,-17/24*FT)
    const height=input.batterHeightM
    guideStem.scale.y=typeof height==='number'&&Number.isFinite(height)&&height>0 ? height/1.65 : 1
    previous=input
    actors?.update(input)
  }
  return {root,field,zone,pitches,ball,release,candidates,update,
    attachActors(value:NonNullable<typeof actors>){actors=value;root.add(value.root);if(previous)update(previous)},
    previewActors(time:number){if(previous?.actorPose==='idle')actors?.update(previous,time)},
    get idlePreview(){return Boolean(actors&&previous?.actorPose==='idle'&&previous.showActors!==false)},
    dispose(){actors?.root.removeFromParent();actors?.dispose();actors=undefined;texture?.dispose();disposeGroup(root)},
  }
}
