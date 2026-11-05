import kit from '~/assets/ballpark/scenes/scene-kit-v4.json'
import { canStand, type CollisionShape, type Point } from './sceneGeometry'

export type WorldRoom = keyof typeof kit.scenes
export type Facing = 'north' | 'east' | 'south' | 'west'
export type WorldPosition = { x:number; y:number; facing:Facing; objectId?:string }
export type WorldSave = {
  schema_version:1; account_id:number; world_revision:string; saved_at:string
  last_room:WorldRoom; viewing_team:string; rooms:Partial<Record<WorldRoom,WorldPosition>>
}
export const WORLD_REVISION = kit.asset_version
export const WORLD_STORAGE_PREFIX = 'petehub.ballpark.world.v1:'
const facings:Facing[]=['north','east','south','west']
const object = (v:unknown):v is Record<string,unknown> => Boolean(v && typeof v==='object' && !Array.isArray(v))
export const isWorldRoom = (v:unknown):v is WorldRoom => typeof v==='string' && Object.hasOwn(kit.scenes,v)
export function emptyWorldSave(accountId:number):WorldSave {
  return {schema_version:1,account_id:accountId,world_revision:WORLD_REVISION,saved_at:new Date().toISOString(),last_room:'campus',viewing_team:'',rooms:{}}
}
export function readWorldSave(raw:string|null,accountId:number):{save:WorldSave;notice:string} {
  const fallback=emptyWorldSave(accountId)
  if(!raw)return {save:fallback,notice:''}
  try {
    if(raw.length>30000)throw new Error('oversized')
    const data:unknown=JSON.parse(raw)
    if(!object(data) || data.schema_version!==1 || data.account_id!==accountId || !isWorldRoom(data.last_room) || !object(data.rooms))throw new Error('invalid version/account')
    const save:WorldSave={...fallback,last_room:data.last_room,viewing_team:typeof data.viewing_team==='string' && /^[A-Z]{2,3}$/.test(data.viewing_team)?data.viewing_team:'',rooms:{}}
    let recovered=0
    for(const [room,value] of Object.entries(data.rooms)){
      if(!isWorldRoom(room)){recovered++;continue}
      if(!object(value)||typeof value.x!=='number'||typeof value.y!=='number'||!Number.isFinite(value.x)||!Number.isFinite(value.y)||!facings.includes(value.facing as Facing)){recovered++;continue}
      save.rooms[room]={x:value.x,y:value.y,facing:value.facing as Facing,...(typeof value.objectId==='string' && value.objectId.startsWith(`${room}/`) && value.objectId.length<150?{objectId:value.objectId}:{})}
    }
    return {save,notice:data.world_revision!==WORLD_REVISION?'The scene package changed. Saved positions will be checked against current collision.':recovered?'Some saved room data was invalid. A safe arrival will be used.':''}
  }catch{return {save:fallback,notice:'Saved Ballpark data was invalid or from an unsupported version. Starting safely; your character profile is unchanged.'}}
}
export function canRestorePosition(room:WorldRoom,position:WorldPosition):boolean {
  return Number.isFinite(position.x)&&Number.isFinite(position.y)&&canStand(position.x,position.y,kit.scenes[room].collision as unknown as CollisionShape[],kit.footprint,kit.world_size)
}
export function resolveWorldPosition(room:WorldRoom,saved?:WorldPosition,arrivalId?:string,objectApproach?:Point):{position:WorldPosition;recovered:boolean} {
  const scene=kit.scenes[room]
  if(!arrivalId && saved && canRestorePosition(room,saved))return {position:saved,recovered:false}
  const portal=arrivalId ? scene.portals.find(p=>p.id===arrivalId) : undefined
  const candidates:Point[]=[...(portal?[portal.arrival as unknown as Point]:[]),...(!arrivalId && objectApproach?[objectApproach]:[]),scene.spawn as unknown as Point]
  const point=candidates.find(p=>canRestorePosition(room,{x:p[0],y:p[1],facing:'south'}))
  if(!point)throw new Error(`No safe arrival for ${room}. Open Classic UI.`)
  return {position:{x:point[0],y:point[1],facing:'south'},recovered:Boolean(saved && !arrivalId)}
}

export type WorldStorage = Pick<Storage,'getItem'|'setItem'>
export function createWorldRepository(storage:WorldStorage,accountId:number){
  if(!Number.isSafeInteger(accountId)||accountId<=0)throw new Error('A signed-in account is required for world saves')
  const key=WORLD_STORAGE_PREFIX+accountId
  return {
    load(){try{return {...readWorldSave(storage.getItem(key),accountId),available:true}}catch{return {save:emptyWorldSave(accountId),notice:'Browser storage is unavailable. This visit remains in memory only.',available:false}}},
    write(save:WorldSave){if(save.account_id!==accountId)return false;try{storage.setItem(key,JSON.stringify(save));return true}catch{return false}}
  }
}
