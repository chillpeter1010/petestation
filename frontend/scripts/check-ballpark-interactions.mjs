import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'
import crypto from 'node:crypto'

const read=name=>fs.readFileSync(new URL(name,import.meta.url),'utf8')
const kit=JSON.parse(read('../assets/ballpark/scenes/scene-kit-v4.json'))
const moduleUrl=source=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64')
const geometryUrl=moduleUrl(read('../components/ballpark/runtime/sceneGeometry.ts'))
const source=read('../components/ballpark/runtime/interactionCatalog.ts')
  .replace("import kit from '~/assets/ballpark/scenes/scene-kit-v4.json'",`const kit=${JSON.stringify(kit)}`)
  .replace("from './sceneGeometry'",`from '${geometryUrl}'`)
const loaded=await import(moduleUrl(source)).catch(error=>{console.error(error.message);process.exit(1)})
const {INTERACTIONS,roomInteractions,nearestInteraction,createActivationGate,positiveId}=loaded
const {canStand}=await import(geometryUrl)
const {baseWalkQuery,safeWalkReturn}=await import(moduleUrl(read('../components/ballpark/runtime/bridgeContract.ts')))
assert.deepEqual(baseWalkQuery({room:'pitcher-mound',spawn:'return',team:'AZ',object:'pitcher-mound/in-game-west',year:'2026',player:'123',game:'42',date:'2026-10-01',mode:'replay'}),{room:'pitcher-mound',spawn:'return',team:'AZ'})
assert.ok(safeWalkReturn('/ballpark/play?room=pitcher-mound&team=AZ'))
for(const invalid of ['https://example.com','//example.com/ballpark/play','/ballpark/playground','/ballpark/play/../../admin/updates',null,'/ballpark/play\\..\\admin'])assert.ok(!safeWalkReturn(invalid))
assert.equal(new Set(INTERACTIONS.map(o=>o.id)).size,INTERACTIONS.length)
for(const object of INTERACTIONS){
  assert.ok(object.id.endsWith('/guide')||kit.object_index.some(o=>o.id===object.id),object.id)
  if(!object.pointerOnly)assert.ok(canStand(...object.approach,kit.scenes[object.room].collision,kit.footprint,kit.world_size),`safe approach ${object.id}`)
  assert.ok(object.links.every(l=>l.path.startsWith('/')&&!l.path.startsWith('//')))
  if(!object.pointerOnly)assert.ok(nearestInteraction([object],...object.approach)?.id===object.id)
}
assert.ok(!roomInteractions('team-office',false).some(o=>o.adminOnly))
assert.ok(roomInteractions('team-office',true).some(o=>o.adminOnly&&o.pointerOnly))
for(const id of ['in-game-west','in-game-east'])assert.equal(INTERACTIONS.find(o=>o.id===`pitcher-mound/${id}`).kind,'in-game')
assert.equal(INTERACTIONS.find(o=>o.id==='pitcher-mound/pitch-analysis').kind,'pitcher')
assert.ok(!INTERACTIONS.some(o=>o.id==='batting-cages/practice-cage'||o.id==='clubhouse/tv-cabinet'))
assert.equal(INTERACTIONS.find(o=>o.id==='video-game-room/future-minigames').kind,'unavailable')
const gate=createActivationGate()
assert.equal(gate(100),true);assert.equal(gate(101),false);assert.equal(gate(500),true);assert.equal(gate(NaN),false)
for(const invalid of [null,undefined,[],{},'Infinity','-1','0','1.2'])assert.equal(positiveId(invalid),undefined)
assert.equal(positiveId('123'),123)
const overlap=[{...INTERACTIONS[0],id:'b',pointerOnly:false,approach:[100,100]},{...INTERACTIONS[0],id:'a',pointerOnly:false,approach:[100,100]}]
assert.equal(nearestInteraction(overlap,100,100).id,'a')
console.log(`E3/E4 source contracts PASS: ${INTERACTIONS.length} bindings/guides, authorization, independent anchors, typed intent selection/debounce, decoration exclusions. User UI acceptance pending.`)
if(process.argv.includes('--anchors'))for(const o of INTERACTIONS)console.log(o.id,o.approach)
if(process.argv.includes('--report')){
  const files=['../components/ballpark/runtime/interactionCatalog.ts','../components/ballpark/runtime/bridgeContract.ts','../components/ballpark/runtime/createBallparkGame.ts','../components/ballpark/BallparkRuntime.client.vue','../components/ballpark/BallparkOverlay.vue','../components/ballpark/BallparkObjectPanel.vue','../components/ballpark/BallparkGamePanel.vue','../pages/ballpark/play.vue','../composables/useBallparkReturn.ts','../components/ballpark/BallparkClassicReturn.vue','../components/pitcher-personal/PitcherInGameTab.vue','../app.vue','../assets/ballpark/scenes/scene-kit-v4.json']
  const evidence={schema_version:1,generated_at:new Date().toISOString(),slices:['E3','E3.1','E3.2','E3.3','E4'],status:'source_contracts_pass',manual_acceptance:'pending_user',
    counts:{scene_objects:kit.object_index.length,bindings:INTERACTIONS.length,additional_generic_guides:INTERACTIONS.filter(o=>o.id.endsWith('/guide')).length},
    checks:['stable unique IDs and catalog membership','walk approaches pass foot/polygon contract; pointer-only exceptions explicit','nearest prompt tie-break and 400ms activation debounce','admin-frame hidden from general accounts; no extra visible easter-egg button','both bullpens dispatch In game; Shape remains separate','decoration exclusions and unavailable minigames','positive context IDs reject invalid values','close base retains origin room/team/spawn and removes panel query','return tokens reject external/wrong paths'],
    bindings:INTERACTIONS.map(({id,kind,bounds,approach,npc,adminOnly,pointerOnly,links})=>({id,kind,bounds,approach,npc:Boolean(npc),admin_only:Boolean(adminOnly),pointer_only:Boolean(pointerOnly),classic_routes:links.map(l=>l.path)})),
    input_hashes:Object.fromEntries(files.map(name=>[new URL(name,import.meta.url).pathname.split('/project_transfer/')[1],crypto.createHash('sha256').update(read(name)).digest('hex')])),
    limitations:['No browser, screenshots, DOM visual checks, collision feel or UI acceptance performed','Safe anchor math is not user walking/reachability acceptance','Section F full business parity and real roster NPC art/dialogue are not implemented','NPCs are fictional stationary idle guides, not randomized official players or action animations','E5 exact position/session persistence and E6 performance/release certification remain planned'],
    manual_checklist:['Object click / nearby E-Enter / direct menu parity, one activation per press','Game selection, shared analysis/pitch video, both bullpen official pitcher + outing menus','Close/Escape/Back/forward/refresh, pause/form input/focus/scroll and Classic return link','Nine rooms: generic guide dialogue, mini-map, fast travel/team and C/R exits','Admin frame visibility/authorization, unavailable mini-games, roster freshness and empty/error states']}
  fs.writeFileSync(new URL('../../data/sample/petehub_ballpark_e3_e4_source_gate_v1.json',import.meta.url),JSON.stringify(evidence,null,2)+'\n','utf8')
}
