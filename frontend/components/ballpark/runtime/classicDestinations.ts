import type { Interaction } from './interactionCatalog'
import { gameDate } from '~/utils/gameCenterContext'

export function objectClassicDestination(target:Interaction,context:{team:string;year:number;player?:number;game?:number;path?:string;date?:string}){
  if(target.npc||target.kind==='dialogue'||target.kind==='unavailable'||target.adminOnly)return null
  const {team,year,player,game}=context
  let path=context.path && target.links.some(l=>l.path===context.path)?context.path:target.links[0]?.path
  const query:Record<string,string|number|undefined>={year,team:team||undefined}
  if(target.id==='batting-cages/batter-analysis')path='/batter-personal'
  if(target.kind==='in-game'){path='/pitcher-personal';query.tab='in-game';query.game_pk=game}
  if(target.id==='pitcher-mound/pitch-analysis'){path='/pitcher-personal';query.tab='movement'}
  if(target.kind==='games'){path='/games/today';query.game_pk=game;query.pitcher_id=player;query.date=gameDate(context.date,year)||undefined;query.tab=target.id.endsWith('replay-screen')?'replay':target.id.endsWith('game-analysis-console')?'box':'feed'}
  if(path==='/batter-personal')query.batter_id=player
  if(path==='/pitcher-personal')query.pitcher_id=player
  if(!path)return null
  return {path:path==='/teams'&&team?`/teams/${team}`:path,query}
}
