// Export authored ready/idle bone targets into editable glTF and self-contained
// GLB. Pure geometry; never renders, reads images visually or creates a browser.
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import ts from 'typescript'
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js'
globalThis.ProgressEvent ??= class extends Event {constructor(type,init){super(type);Object.assign(this,init)}}
const root=path.resolve(import.meta.dirname,'../..'),sourceDir=path.join(root,'output/ballpark/f2-character-source-v1')
const sourceFile=path.join(sourceDir,'actor-base-v1.gltf'),gltf=JSON.parse(fs.readFileSync(sourceFile,'utf8'))
let bin=fs.readFileSync(path.join(sourceDir,'actor-base-v1.bin'))
const load=structuredClone(gltf);load.buffers=[{byteLength:bin.length,uri:'data:application/octet-stream;base64,'+bin.toString('base64')}]
delete load.images;delete load.textures;for(const mat of load.materials)delete mat.pbrMetallicRoughness.baseColorTexture
const asset=await new GLTFLoader().parseAsync(JSON.stringify(load),'')
let text=fs.readFileSync(path.join(root,'frontend/components/charts/replay3d/createReplayActors.ts'),'utf8')
text=text.replace("import actorUrl from '~/assets/ballpark/characters3d/actor-base-v1.glb?url'","const actorUrl='unused-for-export'")
for(const id of ['three','three/addons/loaders/GLTFLoader.js','three/addons/utils/SkeletonUtils.js'])text=text.replace(`'${id}'`,`'${import.meta.resolve(id)}'`)
const js=ts.transpileModule(text,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {makeActor}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'))
function append(array,kind){
  const values=new Float32Array(array.flat()),padding=Buffer.alloc(-bin.length&3)
  bin=Buffer.concat([bin,padding]);const start=bin.length;bin=Buffer.concat([bin,Buffer.from(values.buffer)])
  gltf.bufferViews.push({buffer:0,byteOffset:start,byteLength:values.byteLength})
  const accessor={bufferView:gltf.bufferViews.length-1,componentType:5126,count:array.length,type:kind}
  if(kind==='SCALAR'){accessor.min=[Math.min(...array.flat())];accessor.max=[Math.max(...array.flat())]}
  gltf.accessors.push(accessor);return gltf.accessors.length-1
}
const time=append([[0],[.6],[1.2],[1.8],[2.4]],'SCALAR')
gltf.animations=gltf.animations.filter(a=>a.name==='ready'||a.name==='idle')
for(const role of ['batter','pitcher'])for(const hand of ['R','L'])for(const pose of ['ready','idle']){
  const actor=makeActor(asset.scene,asset.animations,role),tracks=new Map()
  for(const t of [0,.6,1.2,1.8,2.4]){
    actor.update({hand,heightM:actor.baseHeight},pose,t)
    for(const [name,bone] of actor.bones){
      const track=tracks.get(name)||{position:[],quaternion:[]};track.position.push(bone.position.toArray());track.quaternion.push(bone.quaternion.toArray());tracks.set(name,track)
    }
  }
  const animation={name:`${role}_${pose}_${hand}`,samplers:[],channels:[]}
  for(const [name,track] of tracks){
    const node=gltf.nodes.findIndex(n=>n.name===name)
    for(const [property,kind,target] of [['position','VEC3','translation'],['quaternion','VEC4','rotation']]){
      const rest=gltf.nodes[node][target]||(target==='translation'?[0,0,0]:[0,0,0,1])
      if(track[property].every(frame=>frame.every((v,i)=>Math.abs(v-rest[i])<1e-6)))continue
      const output=append(track[property],kind);animation.samplers.push({input:time,output,interpolation:'LINEAR'});animation.channels.push({sampler:animation.samplers.length-1,target:{node,path:target}})
    }
  }
  gltf.animations.push(animation)
}
gltf.buffers=[{uri:'actor-base-v1.bin',byteLength:bin.length}]
fs.writeFileSync(sourceFile,JSON.stringify(gltf));fs.writeFileSync(path.join(sourceDir,'actor-base-v1.bin'),bin)
const packed=structuredClone(gltf)
for(const image of packed.images){
  bin=Buffer.concat([bin,Buffer.alloc(-bin.length&3)]);const bytes=fs.readFileSync(path.join(sourceDir,image.uri));delete image.uri
  packed.bufferViews.push({buffer:0,byteOffset:bin.length,byteLength:bytes.length});image.bufferView=packed.bufferViews.length-1;bin=Buffer.concat([bin,bytes])
}
bin=Buffer.concat([bin,Buffer.alloc(-bin.length&3)]);packed.buffers=[{byteLength:bin.length}]
let json=Buffer.from(JSON.stringify(packed));json=Buffer.concat([json,Buffer.alloc(-json.length&3,32)])
const header=Buffer.alloc(20);header.writeUInt32LE(0x46546c67);header.writeUInt32LE(2,4);header.writeUInt32LE(28+json.length+bin.length,8);header.writeUInt32LE(json.length,12);header.writeUInt32LE(0x4e4f534a,16)
const bh=Buffer.alloc(8);bh.writeUInt32LE(bin.length);bh.writeUInt32LE(0x004e4942,4)
const file=Buffer.concat([header,json,bh,bin]),runtime=path.join(root,'frontend/assets/ballpark/characters3d/actor-base-v1.glb');fs.writeFileSync(runtime,file)
const manifestPath=path.join(root,'data/sample/petehub_replay_actor_manifest_v1.json'),manifest=JSON.parse(fs.readFileSync(manifestPath,'utf8'))
manifest.sha256=crypto.createHash('sha256').update(file).digest('hex');manifest.bytes=file.length;manifest.clips=gltf.animations.map(a=>a.name)
manifest.pose_exporter='frontend/scripts/bake-replay-actors.mjs';manifest.runtime_pose_policy='procedural handed IK over neutral ready/idle base; exported full poses available for DCC editing; no historical body mocap'
manifest.source_hashes=Object.fromEntries(fs.readdirSync(sourceDir).map(n=>[n,crypto.createHash('sha256').update(fs.readFileSync(path.join(sourceDir,n))).digest('hex')]))
manifest.recipe_hashes=Object.fromEntries(['backend/scripts/build_replay_character.py','frontend/scripts/bake-replay-actors.mjs','frontend/components/charts/replay3d/createReplayActors.ts'].map(n=>[n,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,n))).digest('hex')]))
fs.writeFileSync(manifestPath,JSON.stringify(manifest,null,2)+'\n')
console.log(`Baked ${manifest.clips.length} clips, ${file.length} bytes. No visual validation.`)
