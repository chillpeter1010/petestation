import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'
const source=fs.readFileSync('utils/pitchScout.ts','utf8')
const js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const {scoutRequest,scoutKey}=await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
const row={game_pk:10,pitcher:7,batter:5,at_bat_number:3,pitch_number:2,balls:0,strikes:1,stand:'L',p_throws:'R',game_date:'2026-09-27T00:00:00',pitch_type:'SL',plate_x:1,description:'foul'}
const previous={...row,pitch_number:1,pitch_type:'FF',description:'called_strike'}
const expected=scoutRequest(2026,row,[previous,row])
assert.equal(expected.previousType,'FF');assert.equal(expected.previousResult,'called_strike')
assert.equal(scoutKey(expected),scoutKey(scoutRequest(2026,{...row,pitch_type:'CH',description:'hit_into_play',plate_x:-3,plate_z:5,release_speed:99},[previous,row])))
assert.equal(scoutRequest(2026,row,[{...previous,game_pk:11}]).previousType,'__missing__')
assert.equal(scoutRequest(2026,row,[{...previous,at_bat_number:2}]).previousType,'__missing__')
assert.equal(scoutRequest(2026,row,[{...previous,batter:6}]).previousType,'__missing__')
assert.equal(scoutRequest(2026,{...row,pitch_number:1},[]).previousType,'__first__')
assert.equal(scoutRequest(2026,{...row,p_throws:''},[]),null)
assert.equal(scoutRequest(2026,{...row,balls:null},[]),null)
assert.equal(scoutRequest(2026,{...row,game_date:''},[]),null)
assert.notEqual(scoutKey(expected),scoutKey({...expected,beforeDate:'2026-09-28'}))
assert.notEqual(scoutKey(expected),scoutKey({...expected,strikes:2}))
console.log('Pitch scout request contract PASS: exact predecessor, cutoff/count/hand identity, no current outcome/type/location input.')
const moduleUrl=source=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64')
const contractUrl=moduleUrl(fs.readFileSync('components/charts/replay3d/replayContract.ts','utf8'))
const worldSource=fs.readFileSync('components/charts/replay3d/buildReplayWorld.ts','utf8').replace("'three'",JSON.stringify(import.meta.resolve('three'))).replace("'./replayContract'",JSON.stringify(contractUrl))
const {buildReplayWorld}=await import(moduleUrl(worldSource))
const world=buildReplayWorld(),points=[{progress:0,time_seconds:0,x_ft:-1.5,y_ft:54,z_ft:6},{progress:1,time_seconds:.4,x_ft:.1,y_ft:17/12,z_ft:2.4}]
const snapshot=JSON.stringify(points)
const input={selectedKey:'1',points,progress:0,color:'#f80',paths:[],zoneTop:3.5,zoneBottom:1.5,stand:'L',heatmap:[],scoutTarget:{u:.5,v:.5}}
world.update(input)
const ring=world.root.getObjectByName('historical-swing-concentration-not-observed-intent')
assert.equal(ring.visible,true);assert.equal(ring.position.x,0)
const startScale=ring.scale.x,pos=ring.position.toArray(),geometry=ring.geometry
world.update({...input,progress:1})
assert.ok(ring.scale.x<startScale);assert.deepEqual(ring.position.toArray(),pos);assert.equal(ring.geometry,geometry)
world.update({...input,scoutTarget:undefined});assert.equal(ring.visible,false)
assert.equal(JSON.stringify(points),snapshot)
world.dispose()
console.log('Scout target geometry PASS: fixed historical zone, shrink only, no source path change, hidden when unavailable; no renderer/browser used.')
