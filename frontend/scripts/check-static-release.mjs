// Numerical and in-memory state checks only: no browser, renderer or DOM inspection.
import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'
import * as vue from 'vue'
import { parse } from '@vue/compiler-sfc'
const read=p=>fs.readFileSync(new URL(`../${p}`,import.meta.url),'utf8')
const url=source=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText).toString('base64')
const {pitchReleaseGuide,releaseNumber}=await import(url(read('utils/pitchReleaseGuide.ts')))
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,`${a} != ${b}`)
for(const hand of ['L','R'])for(const angle of [-61,-12.2,0,50,65.8,90]){
  const row={p_throws:hand,arm_angle:angle,release_pos_x:hand==='R'?-3:3,release_pos_y:54,release_pos_z:6,release_extension:6.5}
  const original=JSON.stringify(row),front=pitchReleaseGuide(row,'front'),back=pitchReleaseGuide(row,'back')
  near(front.release.x+back.release.x,400);near(front.release.y,back.release.y)
  const dx=front.release.x-front.shoulder.x,dz=front.shoulder.y-front.release.y
  near(Math.atan2(dz,Math.abs(dx))*180/Math.PI,angle)
  near(Math.hypot(dx,dz),50);assert.equal(front.extension,6.5);assert.equal(front.y,54)
  assert.equal(JSON.stringify(row),original)
}
for(const missing of [null,undefined,'',' ',NaN,Infinity,true,[],{},'unavailable'])assert.equal(releaseNumber(missing),null)
assert.equal(pitchReleaseGuide({arm_angle:91,p_throws:'R'},'front').angle,null)
assert.equal(pitchReleaseGuide({arm_angle:0,p_throws:'R',release_pos_x:0,release_pos_z:0},'front').release.y,295)
assert.equal(pitchReleaseGuide({arm_angle:50,release_pos_x:1,release_pos_z:6},'front').shoulder,null)
assert.equal(pitchReleaseGuide({arm_angle:50,p_throws:'R',release_pos_x:null,release_pos_z:6},'front').release,null)
const teams=url(read('config/mlbTeams.ts'))
const context=url(read('utils/gameCenterContext.ts').replace("'~/config/mlbTeams'",`'${teams}'`))
const {objectClassicDestination}=await import(url(read('components/ballpark/runtime/classicDestinations.ts').replace("'~/utils/gameCenterContext'",`'${context}'`)))
for(const lane of ['west','east']){
  const d=objectClassicDestination({id:`pitcher-mound/in-game-${lane}`,kind:'in-game',links:[]},{year:2026,team:'AZ',player:123,game:456})
  assert.equal(d.path,'/pitcher-personal');assert.equal(d.query.bullpen,lane);assert.equal(d.query.pitcher_id,123);assert.equal(d.query.game_pk,456)
}
const fixture={freshness:'stale',retrieved_at:'snapshot',source_as_of:'as-of',players:[{player_id:11,name:'Pitcher one',position_type:'Pitcher'},{player_id:12,name:'Pitcher two',position_type:'Pitcher'},{player_id:99,name:'Batter',position_type:'Infielder'}]}
// Execute selector setup against fake API responses: late responses, manual priority, error/empty.
const script=parse(read('components/pitcher-personal/BullpenPitcherSelect.vue')).descriptor.scriptSetup.content.replace(/^import .+$/gm,'')
const compiled=ts.transpileModule(script,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace(/^export \{\};?$/gm,'')
const setup=new (Object.getPrototypeOf(async function(){}).constructor)('env',`with(env){${compiled};return {load,players,loading,error,choose}}`)
async function run(requested,response=fixture){
  const props=vue.reactive({year:2026,team:'AZ',pitcherId:requested||null,lane:'west'})
  const route={query:{pitcher_id:requested,game_pk:55,ballpark_from:'/ballpark/play?room=pitcher-mound',bullpen:'west'}}
  const calls=[],scope=vue.effectScope();let pending
  const state=await scope.run(()=>setup({...vue,MLB_TEAMS:[],defineProps:()=>props,defineEmits:()=>()=>{},useRuntimeConfig:()=>({public:{apiBase:'/api'}}),useRoute:()=>route,useRouter:()=>({replace:async({query})=>{calls.push(query);route.query=query}}),watch:()=>{},onBeforeUnmount:()=>{},$fetch:async()=>{if(pending)return await pending.promise;if(response instanceof Error)throw response;return response}}))
  await state.load()
  return {state,props,route,calls,scope,clearDelay(){pending=null},delay(){let resolve;pending={promise:new Promise(r=>resolve=r)};return r=>resolve(r)}}
}
const explicit=await run(12);assert.equal(explicit.calls.length,0);assert.deepEqual(explicit.state.players.value.map(p=>p.player_id),[11,12])
explicit.state.choose(11);assert.equal(explicit.route.query.pitcher_id,11);assert.equal(explicit.route.query.game_pk,undefined);assert.ok(explicit.route.query.ballpark_from)
const automatic=await run();assert.equal(automatic.route.query.pitcher_id,11)
const historical=await run(123);assert.equal(historical.calls.length,0,'never replace explicit historical selection with another player')
const unavailable=await run(null,{...fixture,freshness:'unavailable'});assert.equal(unavailable.state.players.value.length,0);assert.equal(unavailable.calls.length,0)
const failed=await run(null,new Error('offline'));assert.match(failed.state.error.value,/offline/);assert.equal(failed.state.loading.value,false)
const release=explicit.delay(),old=explicit.state.load();explicit.clearDelay();await explicit.state.load()
release({...fixture,players:[]});await old;assert.equal(explicit.state.players.value.length,2,'late roster cannot replace the latest snapshot')
for(const instance of [explicit,automatic,historical,unavailable,failed])instance.scope.stop()
// Static integration boundaries: shared component, no motion data or recurring idle render.
const chart=read('components/charts/PitchReplayChart.vue'),actors=read('components/charts/replay3d/createReplayActors.ts')
assert.match(chart,/MOTION_REFERENCES_AVAILABLE=false/);assert.match(chart,/actorPose:'ready'/)
assert.match(chart,/motion:undefined/);assert.match(chart,/batterSwingReference:undefined/)
assert.doesNotMatch(chart,/<PitchReleaseGuide/,'removed large arm-angle diagram')
for(const flag of ['PITCHER_DELIVERY_AVAILABLE','BATTER_SWING_RETARGET_AVAILABLE','REFERENCE_B_RETARGET_AVAILABLE','VIDEO_POSE_RETARGET_AVAILABLE'])assert.match(actors,new RegExp(`${flag}\\s*=\\s*false`))
assert.match(actors,/PITCHER_ACTOR_AVAILABLE\s*=\s*false/,'pitcher figure removed by user')
const runtime=read('components/charts/replay3d/createReplayScene.ts')
for(const token of ['observer.disconnect()','controls.dispose()','world.dispose()','renderer.dispose()','renderer.forceContextLoss()','canvas.remove()','cancelAnimationFrame','actorAbort.abort()'])assert.ok(runtime.includes(token),token)
assert.match(read('components/charts/PitchReplayPanel.vue'),/PitchReplayChart/)
assert.match(read('components/games/GamePitcherAnalysisPanel.vue'),/PitchReplayPanel/)
assert.match(read('pages/games/today.vue'),/GamePitcherAnalysisPanel/)
console.log('Static F2 source PASS: front/back L/R and negative angles, release immutability, nulls, canonical bullpen destinations, official roster filtering/manual priority/unavailable/error. No visual or device acceptance.')
