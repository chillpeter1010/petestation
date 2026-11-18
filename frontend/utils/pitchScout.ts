import type { BatterZoneRatesResponse } from '~/types/api'
export type ScoutRequest={year:number;batterId:number;pitcherHand:'L'|'R';stand:'L'|'R';beforeDate:string;balls:number;strikes:number;previousType:string;previousResult:string}
export type ScoutTarget={u:number;v:number;zone:string;swings:number;located_swings:number}
export type ScoutResponse={contract_version:string;mode:string;before_date:string;status:'ready'|'insufficient_history'|'unavailable';tier:string;context_pitches:number;swing_count:number;swing_pct:number|null;take_pct:number|null;candidates:{family:string;swings:number;share_pct:number}[];target:ScoutTarget|null;heatmap:BatterZoneRatesResponse;source_version:string}
export const scoutKey=(p:ScoutRequest)=>JSON.stringify(p)
// Full unfiltered rows are required; an absent predecessor is never substituted.
export function scoutRequest(year:number|undefined,selected:Record<string,unknown>|null,rows:Record<string,unknown>[]):ScoutRequest|null{
  if(!year||!selected)return null
  const {p_throws:hand,stand}=selected,b=selected.balls,s=selected.strikes,batterId=Number(selected.batter),pitch=Number(selected.pitch_number)
  const beforeDate=String(selected.game_date||'').slice(0,10)
  if((hand!=='L'&&hand!=='R')||(stand!=='L'&&stand!=='R')||b==null||s==null||!Number.isInteger(Number(b))||!Number.isInteger(Number(s))||Number(b)<0||Number(b)>3||Number(s)<0||Number(s)>2||batterId<=0||!/^\d{4}-\d{2}-\d{2}$/.test(beforeDate)||!Number.isInteger(pitch)||pitch<1)return null
  const prev=rows.find(r=>r.game_pk===selected.game_pk&&r.pitcher===selected.pitcher&&r.batter===selected.batter&&r.at_bat_number===selected.at_bat_number&&Number(r.pitch_number)===pitch-1)
  return {year,batterId,pitcherHand:hand,stand,beforeDate,balls:Number(b),strikes:Number(s),previousType:pitch===1?'__first__':String(prev?.pitch_type||'__missing__'),previousResult:pitch===1?'__first__':String(prev?.description||'__missing__')}
}
