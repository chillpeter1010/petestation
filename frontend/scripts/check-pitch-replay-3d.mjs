// Numeric/source checks only. Never creates a renderer, browser, DOM or screenshot.
import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'
const read=path=>fs.readFileSync(new URL(`../${path}`,import.meta.url),'utf8')
const moduleUrl=source=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64')
const contractUrl=moduleUrl(read('components/charts/replay3d/replayContract.ts'))
const contract=await import(contractUrl)
const worldUrl=moduleUrl(read('components/charts/replay3d/buildReplayWorld.ts').replace("'three'",`'${import.meta.resolve('three')}'`).replace("'./replayContract'",`'${contractUrl}'`))
const {buildReplayWorld}=await import(worldUrl)
const {FT_TO_METRES:FT,PLATE_FRONT_Y_FT,RUBBER_Y_FT,worldPoint,sampleReplay,REPLAY_CAMERAS}=contract
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`)
assert.deepEqual(worldPoint({x_ft:1,y_ft:2,z_ft:3}),[FT,3*FT,-2*FT])
near(Math.hypot(...worldPoint({x_ft:0,y_ft:RUBBER_Y_FT,z_ft:0})),18.4404)
const points=[{progress:0,time_seconds:0,x_ft:-1.8,y_ft:54.2,z_ft:6.1},{progress:.25,time_seconds:.1,x_ft:-1.2,y_ft:40,z_ft:5},{progress:1,time_seconds:.4,x_ft:.3,y_ft:PLATE_FRONT_Y_FT,z_ft:2.2}]
const before=JSON.stringify(points),half=sampleReplay(points,.5)
near(half.y_ft,40+(PLATE_FRONT_Y_FT-40)/3)
assert.deepEqual(sampleReplay(points,-1),points[0]);assert.deepEqual(sampleReplay(points,2),points[2]);assert.equal(sampleReplay([],0),null)
const world=buildReplayWorld(),heatmap=[{id:'centre',bounds:[0,0,1,1],color:'#ff142d',opacity:.8}]
const input={selectedKey:'selected-pitch',points,progress:0,color:'#f5a623',paths:[{key:'other-pitch',label:'other',color:'#00aaff',points}],zoneBottom:1.5,zoneTop:3.5,stand:'R',heatmap}
world.update(input)
assert.deepEqual(world.release.position.toArray(),worldPoint(points[0]))
assert.deepEqual(world.ball.position.toArray(),worldPoint(points[0]))
assert.deepEqual(world.candidates.map(item=>item.userData.pitchKey),['other-pitch','selected-pitch'])
near(world.field.getObjectByName('pitching-rubber').position.z,-RUBBER_Y_FT*FT)
assert.equal(world.field.getObjectByName('mound').geometry.type,'LatheGeometry','mound must be one continuous slope')
assert.equal(world.field.children.filter(o=>o.name==='dirt').length,1,'no second flat dirt disc under mound')
assert.notEqual(world.release.position.z,world.field.getObjectByName('pitching-rubber').position.z)
const frame=world.zone.getObjectByName('true-zone-17-inch').geometry.getAttribute('position')
near(Math.abs(frame.getX(1)-frame.getX(0)),17/12*FT)
near(frame.getY(2)-frame.getY(0),2*FT)
for(const side of [-1,1]){
  const box=world.field.getObjectByName(`batter-box-${side}`).geometry.getAttribute('position')
  near(Math.abs(box.getX(1)-box.getX(0)),4*FT);near(Math.abs(box.getZ(2)-box.getZ(1)),6*FT)
}
const geometry=world.pitches.getObjectByName('selected-source-path').geometry
world.update({...input,batterHeightM:2.0066})
near(world.root.getObjectByName('generic-height-guide-not-player-model').scale.y*1.65,2.0066)
world.update({...input,batterHeightM:null})
near(world.root.getObjectByName('generic-height-guide-not-player-model').scale.y*1.65,1.65)
for(let i=0;i<100;i++)world.update({...input,progress:i/99})
assert.equal(world.pitches.getObjectByName('selected-source-path').geometry,geometry,'timeline must not rebuild static paths every frame')
world.update({...input,stand:'L',progress:1})
assert.deepEqual(world.release.position.toArray(),worldPoint(points[0]));assert.deepEqual(world.ball.position.toArray(),worldPoint(points[2]))
world.update({...input,motion:contract.replayMotionFrame(0,.4,'called_strike',55),progress:0})
assert.equal(world.ball.visible,false,'during pre-pitch the actor-held ball owns presentation')
world.update({...input,motion:contract.replayMotionFrame(1.2/2.4,.4,'called_strike',55),progress:0})
assert.equal(world.ball.visible,true);assert.deepEqual(world.ball.position.toArray(),worldPoint(points[0]))
assert.equal(JSON.stringify(points),before,'rendering must not modify source coordinates/times')
for(const preset of Object.values(REPLAY_CAMERAS)){assert.ok(preset.position[1]>0);assert.ok(preset.target[1]>0)}
let disposed=0;geometry.addEventListener('dispose',()=>disposed++);world.dispose();assert.equal(disposed,1);assert.equal(world.root.children.length,0)
const chart=read('components/charts/PitchReplayChart.vue'),runtime=read('components/charts/replay3d/createReplayScene.ts'),component=read('components/charts/PitchReplayScene3D.client.vue')
assert.doesNotMatch(chart,/catcher-batters-v\d|catcher-stadium-v\d|translate\(-30 80\)/)
assert.match(chart,/defineAsyncComponent\(\(\) => import\('\.\/PitchReplayScene3D.client.vue'\)\)/)
assert.match(component,/await import\('\.\/replay3d\/createReplayScene'\)/)
assert.match(runtime,/controls.enablePan=false/)
for(const token of ['observer.disconnect()','controls.dispose()','world.dispose()','renderer.dispose()','renderer.forceContextLoss()','canvas.remove()','cancelAnimationFrame'])assert.ok(runtime.includes(token),token)
assert.match(component,/if\(disposed\|\|!host.value\)return/)
console.log('F2.1/F2.2 numeric/source PASS: axis/unit map, source release and plate, 17-inch zone, ground boxes, timeline interpolation, source immutability/handedness, stable geometry, disposal and lazy import boundaries. No renderer or visual acceptance.')
