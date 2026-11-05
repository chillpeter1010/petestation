// Source/data contracts only: no browser, DOM, HTTP, login fixture or visual acceptance.
import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'
import * as vue from 'vue'
import { parse } from '@vue/compiler-sfc'
const read = path => fs.readFileSync(new URL(`../${path}`,import.meta.url),'utf8')
const moduleUrl = source => 'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64')
const teams = moduleUrl(read('config/mlbTeams.ts'))
const contextUrl = moduleUrl(read('utils/gameCenterContext.ts').replace("'~/config/mlbTeams'",`'${teams}'`))
const context = await import(contextUrl)
const destinations = await import(moduleUrl(read('components/ballpark/runtime/classicDestinations.ts').replace("'~/utils/gameCenterContext'",`'${contextUrl}'`)))
const details = await import(moduleUrl(read('utils/pitcherInGame.ts')))
assert.equal(context.gameDate('2025-02-29',2025),'')
assert.equal(context.gameDate('2024-02-29',2024),'2024-02-29')
assert.equal(context.gameDate('2025-09-27',2026),'')
for (const id of [[],{},'-1','1.5','Infinity',0]) assert.equal(context.contextId(id),undefined)
assert.deepEqual(context.gameContext({year:'2025',date:'2025-09-27',team:'az',game_pk:'42',pitcher_id:'100',tab:'replay'}),{year:2025,date:'2025-09-27',team:'AZ',gamePk:42,pitcherId:100,tab:'replay'})
assert.equal(context.gameContext({year:'1999',tab:'admin'}).tab,'feed')
assert.deepEqual(context.leaderboardContext({year:'2025',team:'az',tab:'location',role:'RP'}),{year:2025,team:'AZ',tab:'location',role:'RP'})
assert.deepEqual(context.leaderboardContext({year:'2025',tab:'stamina',role:'RP',team:'invalid'}),{year:2026,team:'All',tab:'stamina',role:'SP'})
for (const [id,tab] of [['schedule-board','feed'],['game-analysis-console','box'],['replay-screen','replay']]) {
  const result=destinations.objectClassicDestination({id:`game-center/${id}`,kind:'games',links:[]},{year:2025,team:'AZ',game:42,player:100,date:'2025-09-27'})
  assert.equal(result.path,'/games/today'); assert.equal(result.query.tab,tab)
  assert.equal(result.query.game_pk,42); assert.equal(result.query.pitcher_id,100); assert.equal(result.query.date,'2025-09-27')
}
assert.equal(destinations.objectClassicDestination({id:'campus/scoreboard',kind:'links',links:[{path:'/leaderboards'}]},{year:2025,team:'AZ'}).query.team,'AZ')
assert.deepEqual(details.inGamePitchDetails({pitcher_name:'Pitcher Test',batter_name:'Batter Test'}).filter(f=>f.key.endsWith('_name')&&f.key!=='pitch_name'&&f.key!=='catcher_name').map(f=>f.value),['Pitcher Test','Batter Test'])
const fixture = id => ({game:{game_pk:id,game_date:id===44?'2025-08-01':'2025-09-27',home_team:'AZ',away_team:'LAD'},teams:[{pitchers:[{pitcher_id:100,name:'Pitcher Test'},{pitcher_id:200,name:'Other Pitcher'}]}],plays:[],scoreboard:{}})
assert.equal(context.gameFitsScope(fixture(42).game,{year:2025,date:'2025-09-27',team:'AZ'}),true)
assert.equal(context.gameFitsScope(fixture(42).game,{year:2026,date:'',team:'AZ'}),false)
assert.equal(context.gameFitsScope(fixture(42).game,{year:2025,date:'',team:'NYY'}),false)

// Execute the actual Game page setup with in-memory Vue state/API responses.
// This tests identity restoration and stale-request exclusion, without rendering UI.
const page=read('pages/games/today.vue')
const source=parse(page).descriptor.scriptSetup.content.replace(/^import .+$/gm,'').replaceAll('import.meta.client','false')
const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace(/^export \{\};?$/gm,'')
const setup=new (Object.getPrototypeOf(async function(){}).constructor)('env',`with(env){${compiled};return {games,selectedGamePk,selectedPitcherId,activeTab,selectedDate,loadError,contextNotice,selectGame,loadGames}}`)
async function run(query) {
  const route=vue.reactive({query:{...query},path:'/games/today',fullPath:'/games/today'})
  const resolve=target=>({fullPath:'/games/today?'+new URLSearchParams(Object.entries(target.query).filter(([,v])=>v!==undefined).map(([k,v])=>[k,String(v)]))})
  const router={resolve,replace:async target=>{route.query={...target.query};route.fullPath=resolve(target).fullPath;await vue.nextTick()}}
  let delayed=null
  const api={gamesList:async ({date})=>({games:(date==='2025-08-01'?[44]:[42,43]).map(id=>fixture(id).game),latest_game_date:'2025-09-27'}),gamePitching:async ({gamePk})=>delayed?.id===gamePk?await delayed.promise:gamePk===999?{teams:[]}:fixture(gamePk)}
  const scope=vue.effectScope()
  let ready
  scope.run(()=>{ready=setup({...vue,...context,watch:(...args)=>scope.run(()=>vue.watch(...args)),useApi:()=>api,useRoute:()=>route,useRouter:()=>router,onBeforeUnmount:()=>{},getPitchColor:()=>'',definePageMeta:()=>{}})})
  const state=await ready
  return {state,route,scope,failList(){api.gamesList=async()=>{throw new Error('Unavailable snapshot')}},delay(id){let release;delayed={id,promise:new Promise(resolve=>{release=resolve})};return ()=>{delayed=null;release(fixture(id))}}}
}
const exact=await run({year:'2025',team:'AZ',date:'2025-09-27',game_pk:'43',pitcher_id:'200',tab:'replay',ballpark_from:'/ballpark/play?room=game-center'})
assert.equal(exact.state.selectedGamePk.value,43);assert.equal(exact.state.selectedPitcherId.value,200);assert.equal(exact.state.activeTab.value,'replay')
assert.equal(exact.route.query.game_pk,43);assert.ok(exact.route.query.ballpark_from)
const release=exact.delay(42),old=exact.state.selectGame(42)
await exact.state.selectGame(43);release();await old
assert.equal(exact.state.selectedGamePk.value,43)
assert.equal(exact.route.query.game_pk,43)
const historic=await run({year:'2025',team:'AZ',game_pk:'44',tab:'box'})
assert.equal(historic.state.selectedDate.value,'2025-08-01');assert.equal(historic.state.selectedGamePk.value,44)
const missing=await run({year:'2025',team:'AZ',game_pk:'999',tab:'box'})
assert.equal(missing.state.selectedGamePk.value,42);assert.match(missing.state.contextNotice.value,/unavailable/)
exact.failList();await exact.state.loadGames()
assert.match(exact.state.loadError.value,/could not load/);assert.equal(exact.state.selectedGamePk.value,null)
for(const instance of [exact,historic,missing])instance.scope.stop()
console.log('F1 source/data contracts PASS: canonical destinations, year/date/team identities, doubleheader game PK, requested tab/pitcher, historical date recovery, unavailable fallback, stale detail exclusion, preserved origin and names. No visual acceptance.')
