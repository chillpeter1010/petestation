// Pure saved-data/math/lifecycle contracts, never browser or visual acceptance.
import fs from 'node:fs'
import crypto from 'node:crypto'
import assert from 'node:assert/strict'
import ts from 'typescript'
const root=new URL('../../',import.meta.url)
const read=name=>fs.readFileSync(new URL(name,root),'utf8')
const moduleUrl=source=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64')
const kit=JSON.parse(read('frontend/assets/ballpark/scenes/scene-kit-v4.json'))
const geometry=moduleUrl(read('frontend/components/ballpark/runtime/sceneGeometry.ts'))
const model=read('frontend/components/ballpark/runtime/worldState.ts').replace("import kit from '~/assets/ballpark/scenes/scene-kit-v4.json'",`const kit=${JSON.stringify(kit)}`).replace("from './sceneGeometry'",`from '${geometry}'`)
const {emptyWorldSave,readWorldSave,resolveWorldPosition,canRestorePosition,createWorldRepository,WORLD_REVISION}=await import(moduleUrl(model)).catch(e=>{console.error(e.message);process.exit(1)})
const {summarizeFrames,createFrameRecorder}=await import(moduleUrl(read('frontend/components/ballpark/runtime/runtimeTelemetry.ts')))
const checks=[]
function check(name,fn){fn();checks.push(name)}
check('account-scoped round trip includes room/position/facing/team, excludes unexpected payload',()=>{
  const save=emptyWorldSave(12);save.last_room='clubhouse';save.viewing_team='AZ';save.rooms.clubhouse={x:810,y:825,facing:'west',objectId:'clubhouse/player-list'}
  const parsed=readWorldSave(JSON.stringify({...save,secret:'must not survive'}),12).save
  assert.equal(parsed.last_room,'clubhouse');assert.equal(parsed.viewing_team,'AZ');assert.equal(parsed.rooms.clubhouse.facing,'west');assert.ok(!('secret'in parsed))
  assert.deepEqual(readWorldSave(JSON.stringify(save),13).save.rooms,{})
})
check('malformed/unknown-version saves safely recover without deleting avatar data',()=>{
  for(const raw of ['{',JSON.stringify({schema_version:999}),JSON.stringify([]),'x'.repeat(30001)]){
    const result=readWorldSave(raw,12);assert.equal(result.save.last_room,'campus');assert.ok(result.notice)
  }
  const save=emptyWorldSave(12);save.rooms.clubhouse={x:'bad',y:null,facing:'up'}
  assert.ok(!readWorldSave(JSON.stringify(save),12).save.rooms.clubhouse)
})
check('all nine scenes resolve safe defaults and current collision invalidates wall/out-of-world saves',()=>{
  for(const room of Object.keys(kit.scenes)){
    const fallback=resolveWorldPosition(room);assert.ok(canRestorePosition(room,fallback.position),room)
    for(const point of [{x:-1,y:0,facing:'north'},{x:Infinity,y:0,facing:'south'},{x:99999,y:99999,facing:'east'}]){
      const recovered=resolveWorldPosition(room,point);assert.equal(recovered.recovered,true);assert.ok(canRestorePosition(room,recovered.position))
    }
  }
  assert.equal(resolveWorldPosition('team-office',{x:200,y:250,facing:'south'}).recovered,true)
})
check('valid pose retained; explicit portal wins; invalid pose can use safe object-adjacent point',()=>{
  const saved={x:870,y:881,facing:'east'}
  assert.deepEqual(resolveWorldPosition('campus',saved).position,saved)
  const portal=resolveWorldPosition('campus',saved,'game');assert.equal(portal.position.x,840);assert.equal(portal.position.y,576)
  assert.deepEqual(resolveWorldPosition('campus',{x:-1,y:-1,facing:'west'},undefined,[850,745]).position,{x:850,y:745,facing:'south'})
  const save=emptyWorldSave(12);save.world_revision='old-package';assert.ok(readWorldSave(JSON.stringify(save),12).notice)
})
check('separate account keys; storage errors never prevent fallback; no cross-account writes',()=>{
  const map=new Map(),storage={getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v)}
  const a=createWorldRepository(storage,12),b=createWorldRepository(storage,13)
  const save=emptyWorldSave(12);save.last_room='pitcher-mound';assert.equal(a.write(save),true);assert.equal(b.write(save),false);assert.equal(b.load().save.last_room,'campus')
  const denied=createWorldRepository({getItem(){throw Error('denied')},setItem(){throw Error('quota')}},12)
  assert.equal(denied.load().available,false);assert.equal(denied.write(save),false);assert.throws(()=>createWorldRepository(storage,0))
})
check('frame recorder excludes paused intervals, caps samples and never certifies idle-only or dev samples',()=>{
  const recorder=createFrameRecorder();recorder.start(0);recorder.sample(0,true,true);recorder.sample(16,true,true);recorder.sample(500,false,false);recorder.sample(1000,true,true);recorder.sample(1016,true,true)
  const report=recorder.finish(1020);assert.deepEqual(report.raw_frame_ms,[16,16]);assert.equal(report.moving_samples,2);assert.match(report.interpretation,/limited/)
  assert.equal(summarizeFrames(Array(120).fill(40),120).interpretation,'offer_classic_fallback')
  assert.equal(summarizeFrames(Array(120).fill(16.7),120).p95_ms,16.7)
  recorder.start(0);for(let n=0;n<4000;n++)recorder.sample(n*16,true,true);assert.equal(recorder.finish(64000).sample_count,3600)
  recorder.cancel();assert.equal(recorder.finish(1),null)
})
check('runtime error and owned-resource cleanup hooks remain wired and engine stays lazy',()=>{
  const runtime=read('frontend/components/ballpark/runtime/createBallparkGame.ts'),wrapper=read('frontend/components/ballpark/BallparkRuntime.client.vue'),page=read('frontend/pages/ballpark/play.vue')
  for(const text of ["await import('phaser')","removeEventListener('webglcontextlost',contextLost)","removeEventListener('visibilitychange', visibility)",'observer?.disconnect()','P.Core.Events.DESTROY','game.destroy(true)'])assert.ok(runtime.includes(text),text)
  assert.ok(wrapper.includes("media?.removeEventListener('change',syncMotion)"));assert.ok(wrapper.includes('clearTimeout(recordTimer)'));assert.ok(wrapper.includes('recorder.cancel()'))
  assert.ok(page.includes("window.removeEventListener('pagehide',checkpoint)"));assert.ok(page.includes('onBeforeRouteLeave'))
  for(const f of ['frontend/app.vue','frontend/composables/useBallparkReturn.ts','frontend/components/ballpark/runtime/bridgeContract.ts'])assert.doesNotMatch(read(f),/from ['"]phaser|import\(['"]phaser|from ['"].*worldState/)
})
const inputs=['frontend/components/ballpark/runtime/worldState.ts','frontend/composables/useBallparkWorld.ts','frontend/components/ballpark/runtime/runtimeTelemetry.ts','frontend/components/ballpark/runtime/createBallparkGame.ts','frontend/components/ballpark/runtime/ballparkCharacter.ts','frontend/components/ballpark/BallparkRuntime.client.vue','frontend/pages/ballpark/play.vue']
const evidence={schema_version:1,generated_at:new Date().toISOString(),slices:['E5','E6'],status:'source_contracts_pass',manual_acceptance:'pending_user',release_decision:'not_released',world_revision:WORLD_REVISION,storage_policy:'browser-local per-account v1; no server/cross-device sync; unsupported versions recover to safe spawn',checks,input_hashes:Object.fromEntries(inputs.map(f=>[f,crypto.createHash('sha256').update(read(f)).digest('hex')])),measurements:{browser:'not_run_by_agent',frames:'await_user_recording',heap:'await_user_or_unavailable',production_bundle:'not_measured',production_lcp:'not_measured',input_latency:'not_measured',forced_gc_retained_heap:'not_measured',real_low_end:'await_user_or_unavailable',gpu_resources:'not_measured'},limitations:['Source contracts are not browser/visual/collision/input acceptance','Lifecycle counters describe owned game instances, not a global leak/GPU certificate','20-second user sample in dev mode cannot certify deployed performance budgets','All browser/device checks belong to user; no automation or extra servers'],manual_checklist:['Refresh/relogin and Classic return preserve room/pose/team for same account; other account separate','Portal/C/R arrivals, room travel, Safe reset and safe invalid-save recovery','Desktop/narrow/available real hardware, keyboard/touch/gamepad and reduced motion','User 20-second walking recording/JSON, repeat room/Classic transitions and idle; report unavailable devices/APIs','Canvas/error/Classic fallback, form/panel focus/back and no duplicate runtime after repeated navigation']}
if(process.argv.includes('--report'))fs.writeFileSync(new URL('data/sample/petehub_ballpark_e5_e6_source_gate_v1.json',root),JSON.stringify(evidence,null,2)+'\n','utf8')
console.log(`E5/E6 source-only PASS (${checks.length} contracts). User acceptance/performance release pending.`)
