import { nearestPose, referenceBendAxes, referenceRenderSequence, type PitchMotionReview } from './pitchMotionReview'
import type { ReplayReferencePose } from '../components/charts/replay3d/replayContract'

export type BatterSwingData=Pick<PitchMotionReview,'times'|'methods'|'filled'|'observed'|'segments'|'sourceDuration'|'width'|'height'>&{
  clip:PitchMotionReview['clip']&{stand:'L'|'R';pitcherId:number;sourceBatSpeedMph:number|null;sourceSwingLengthFt:number|null}
  processingWindow:[number,number];quality:{bodyCoverage:number;bothWristsCoverage:number;analysisWindow:number[]}
}
export function prepareBatterSwing(data:BatterSwingData){
  if(data.clip.playerId!==672695||!['L','R'].includes(data.clip.stand))throw new Error('Swing source identity mismatch')
  const missing=new Set(data.filled)
  // Only a derived, bounded render filter. Never fill source gaps or edit B cache.
  const sequence=referenceRenderSequence(data.methods.motionbert.map((p,i)=>missing.has(i)?null:p),data.times)
  const baseline=sequence.find(Boolean)
  if(!baseline)throw new Error('No usable B swing segment')
  const distance=(a:number[],b:number[])=>Math.hypot(...a.map((v,k)=>v-b[k]!))
  const lengths=sequence.filter(p=>p!==null).map(p=>(distance(p[1]!,p[2]!)+distance(p[2]!,p[3]!)+distance(p[4]!,p[5]!)+distance(p[5]!,p[6]!))/2).sort((a,b)=>a-b)
  const legLengthUnits=lengths[Math.floor(lengths.length/2)]!
  if(!Number.isFinite(legLengthUnits)||legLengthUnits<=0)throw new Error('Invalid B source scale')
  const axes=referenceBendAxes(sequence,data.times)
  return {data,sequence,baseline,legLengthUnits,axes}
}
export function sampleBatterSwing(clip:ReturnType<typeof prepareBatterSwing>,progress:number):ReplayReferencePose{
  const {data}=clip,[start,end]=data.processingWindow,sourceTime=start+Math.max(0,Math.min(1,progress))*(end-start)
  const i=nearestPose(data.times,sourceTime)
  return {version:'motionbert_reference_points_v1',kind:'batter-swing',playerId:672695,hand:data.clip.stand,
    sourceId:data.clip.playId,sourceTime,points:clip.sequence[i]||null,baseline:clip.baseline!,legLengthUnits:clip.legLengthUnits,
    bendAxes:clip.axes[i],cameraYaw:Math.PI}
}
