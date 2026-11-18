// Source/math only. No browser or visual acceptance.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { createRequire } from 'node:module'
const ts=createRequire(import.meta.url)('typescript')
const compile=p=>ts.transpileModule(fs.readFileSync(new URL(p,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ES2022}}).outputText
const uri=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64')
const palette=uri(compile('../utils/heatmapPalette.ts'))
const {buildPitchHeatmap,pitchHeatmapReplayBands}=await import(uri(compile('../utils/pitchLocationHeatmap.ts').replace("'./heatmapPalette'",JSON.stringify(palette))))
const {heatColor}=await import(palette)
const options={blend:1,mode:'choice',xDomain:[-2.2,2.2],zDomain:[0,4.8]}
const points=Array.from({length:16},(_,i)=>({x:(i%4-1.5)*.1,z:2+(Math.floor(i/4)-1.5)*.1,swung:false,batSpeed:null}))
const snapshot=JSON.stringify(points)
assert.deepEqual(buildPitchHeatmap([],options),[])
assert.deepEqual(buildPitchHeatmap(points.slice(0,7),options),[])
assert.deepEqual(buildPitchHeatmap(points,{...options,blend:0}),[])
const zero=buildPitchHeatmap(points,options)
assert.ok(zero.length>9&&zero.every(c=>c.color===heatColor(0)),'actual zero swing rate is blue, not missing/grey')
const full=buildPitchHeatmap(points.map(p=>({...p,swung:true})),options)
assert.ok(full.every(c=>c.color===heatColor(1)),'all swings use the same Personal red')
assert.equal(JSON.stringify(points),snapshot,'source pitches are unchanged')
assert.deepEqual(pitchHeatmapReplayBands(full,2,2),[])
const band=pitchHeatmapReplayBands([{x:0,z:0,x0:-.6,x1:-.4,z0:1.5,z1:3.5,color:'red',opacity:1}],1.5,3.5)[0]
assert.deepEqual(band.bounds.slice(1).filter((_,i)=>i!==1),[0,1])
assert.ok(band.bounds[0]>.5&&band.bounds[2]>band.bounds[0],'negative Personal display X becomes positive physical plate_x once')
const personal=fs.readFileSync(new URL('../components/charts/StrikeZoneScatter.vue',import.meta.url),'utf8')
const replay=fs.readFileSync(new URL('../components/charts/BatterInGameHeatmap.vue',import.meta.url),'utf8')
assert.ok(personal.includes('buildPitchHeatmap')&&replay.includes('buildPitchHeatmap'),'both views call one shared kernel')
assert.ok(replay.includes("metric=ref<PitchHeatMode>('choice'),blend=ref(1)"))
assert.ok(!replay.includes('batterZoneRates(')&&!replay.includes('color_pr'))
console.log('Personal/replay heatmap source checks PASS: shared kernel, Swing/100%, true zero, sparse input, source identity, physical projection.')
