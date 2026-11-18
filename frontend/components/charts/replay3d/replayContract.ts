// Historical Statcast data remains in feet: X lateral, Y plate-to-mound, Z up.
// Three.js is right-handed, metres, Y up: (X, Z, -Y) * 0.3048.
export const REPLAY_SCENE_VERSION = 'historical_replay_scene_v1'
export const FT_TO_METRES = 0.3048
export const PLATE_FRONT_Y_FT = 17 / 12
export const RUBBER_Y_FT = 60.5
export type ReplayPoint = { progress:number; time_seconds:number; x_ft:number; y_ft:number; z_ft:number }
export type ReplayView = 'catcher' | 'pitcher' | 'side' | 'batter-detail' | 'pitcher-detail'
export type Replay3DPath = { key:string; label:string; color:string; points:ReplayPoint[]; source?:Record<string,unknown> }
export type Replay3DHeatBand = { id:string; bounds:[number,number,number,number]; color:string; opacity:number }
export type ReplayActorIdentity = {heightM?:number|null;hand?:string;team?:string;home?:boolean|null}
export type ReplayReferencePose={version:'motionbert_reference_points_v1';playerId:number;sourceId:string;sourceTime:number;hand:string;points:number[][]|null;baseline:number[][];legLengthUnits:number;bendAxes?:number[][]|null;kind?:'batter-swing';cameraYaw?:number}
export type ReplayVideoPoseClip={version:'video_pose_rig_pilot_v1';id:string;playerId:number;playerName:string;date:string;playId:string;sourceUrl:string;sourceStart:number;sourceEnd:number;boneNames:string[];frames:{sourceTime:number;rotations:number[];root:number[];uncertain:number[];filled:boolean}[];previewOnly:true}
export type ReplayMotionFrame = {timeSeconds:number;flightSeconds:number;durationSeconds:number;ballProgress:number;delivery:number;follow:number;phase:'pre-pitch'|'release'|'flight'|'plate'|'post-pitch';batterAction:'take'|'swing'|'unknown';armAngleDeg:number|null}
export const DELIVERY_LEAD_SECONDS=1.2,DELIVERY_TAIL_SECONDS=.8
export function replayMotionFrame(progress:number,flightSeconds:number,description:unknown,armAngle:unknown):ReplayMotionFrame {
  const flight=Number.isFinite(flightSeconds)&&flightSeconds>0?flightSeconds:.4
  const duration=DELIVERY_LEAD_SECONDS+flight+DELIVERY_TAIL_SECONDS
  const raw=-DELIVERY_LEAD_SECONDS+Math.min(1,Math.max(0,Number.isFinite(progress)?progress:1))*duration
  const time=Math.abs(raw)<1e-8?0:Math.abs(raw-flight)<1e-8?flight:raw
  const result=String(description||'').toLowerCase()
  const batterAction=/^(swinging_strike(?:_blocked)?|foul(?:_tip)?|hit_into_play(?:_no_out|_score)?)$/.test(result)?'swing':/^(ball|blocked_ball|called_strike|hit_by_pitch|pitchout|automatic_ball|automatic_strike)$/.test(result)?'take':'unknown'
  const angle=armAngle==null||armAngle===''?NaN:Number(armAngle)
  return {timeSeconds:time,flightSeconds:flight,durationSeconds:duration,ballProgress:Math.min(1,Math.max(0,time/flight)),delivery:Math.min(1,Math.max(0,(time+DELIVERY_LEAD_SECONDS)/DELIVERY_LEAD_SECONDS)),follow:Math.min(1,Math.max(0,time/.65)),phase:Math.abs(time)<1e-7?'release':Math.abs(time-flight)<1e-7?'plate':time<0?'pre-pitch':time<flight?'flight':'post-pitch',batterAction,armAngleDeg:Number.isFinite(angle)&&angle>=-90&&angle<=90?angle:null}
}
export type Replay3DInput = { selectedKey:string; points:ReplayPoint[]; progress:number; color:string; paths:Replay3DPath[]; zoneTop:number; zoneBottom:number; stand:string; heatmap:Replay3DHeatBand[]; scoutTarget?:{u:number;v:number}; batterHeightM?:number|null; pitcherActor?:ReplayActorIdentity;batterActor?:ReplayActorIdentity;actorPose?:'delivery'|'ready'|'idle';motion?:ReplayMotionFrame;showActors?:boolean;releaseExtensionFt?:number|null;armAngleDeg?:number|null;previewOnly?:boolean;videoPose?:{clip:ReplayVideoPoseClip;playerId:number;progress:number};referencePose?:ReplayReferencePose;batterSwingReference?:ReplayReferencePose }
export function worldPoint(point: Pick<ReplayPoint,'x_ft'|'y_ft'|'z_ft'>): [number,number,number] {
  return [point.x_ft*FT_TO_METRES,point.z_ft*FT_TO_METRES,-point.y_ft*FT_TO_METRES]
}
export function sampleReplay(points:ReplayPoint[],progress:number): ReplayPoint | null {
  if (!points.length) return null
  const target = Math.min(1,Math.max(0,progress))
  if (target <= points[0].progress) return {...points[0]}
  if (target >= points[points.length-1].progress) return {...points[points.length-1]}
  const right = points.findIndex(point => point.progress >= target)
  if (right <= 0) return {...points[right===0?0:points.length-1]}
  const a=points[right-1],b=points[right],t=(target-a.progress)/(b.progress-a.progress||1)
  return {progress:target,time_seconds:a.time_seconds+(b.time_seconds-a.time_seconds)*t,x_ft:a.x_ft+(b.x_ft-a.x_ft)*t,y_ft:a.y_ft+(b.y_ft-a.y_ft)*t,z_ft:a.z_ft+(b.z_ft-a.z_ft)*t}
}
// Positions are viewer presets, not measured player eye positions.
export const REPLAY_CAMERAS: Record<ReplayView,{position:[number,number,number];target:[number,number,number];fov:number}> = {
  catcher:{position:[0,1.8,3.2],target:[0,1.0,-5],fov:52},
  pitcher:{position:[0,2.1,-20.8],target:[0,.8,-.6],fov:48},
  side:{position:[10,3.5,-8.8],target:[0,1,-8.8],fov:58},
  'batter-detail':{position:[2.5,1.4,1.7],target:[0,1,0],fov:40},
  'pitcher-detail':{position:[-2,1.5,-15.8],target:[0,1.25,-60.5*.3048],fov:40},
}
