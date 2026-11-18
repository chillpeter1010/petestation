// Pure source/math checks; never opens or renders a browser.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { createRequire } from 'node:module'
const ts = createRequire(import.meta.url)('typescript')
const compile = path => ts.transpileModule(fs.readFileSync(new URL(path, import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText
const uri = js => 'data:text/javascript;base64,' + Buffer.from(js).toString('base64')
const paletteUri = uri(compile('../utils/heatmapPalette.ts'))
const { buildZoneRateContours, formatZoneRate, zonePRColor } = await import(uri(compile('../utils/batterZoneRates.ts').replace("'./heatmapPalette'", JSON.stringify(paletteUri))))
const cell = (id, bounds, numerator, denominator, metric = 'swing', pr = 50) => ({ id, bounds, region: 'zone', pitches: denominator, rates: { [metric]: { numerator, denominator, value: denominator ? numerator / denominator * (metric === 'woba' ? 1 : 100) : null, color_pr: denominator >= 10 ? pr : null, benchmark_status: denominator >= 10 ? 'ready' : 'low_sample' } } })
assert.deepEqual(buildZoneRateContours([], 'swing'), [])
assert.deepEqual(buildZoneRateContours([cell('missing', [0,0,1,1], 0, 0)], 'swing'), [{id:'missing-missing',bounds:[0,0,1,1],color:'#64748b',opacity:1}])
const zero = [cell('zero', [0,0,1,1], 0, 100)]
const snapshot = JSON.stringify(zero)
const zeroBands = buildZoneRateContours(zero, 'swing')
assert.strictEqual(buildZoneRateContours(zero,'swing'),zeroBands,'same immutable payload/metric reuses contour geometry')
assert.ok(zeroBands.length > 0 && zeroBands.every(b => b.color === zonePRColor(50)), 'raw zero can have neutral PR; do not force blue')
assert.equal(JSON.stringify(zero), snapshot, 'render smoothing cannot mutate statistics')
const weighted = buildZoneRateContours([cell('many', [0,0,1/3,1/3], 0, 100, 'swing', 20), cell('one', [1/3,0,2/3,1/3], 1, 1, 'swing', 100)], 'swing')
assert.equal(weighted.find(b => b.bounds[0] <= .32 && b.bounds[2] >= .32 && b.bounds[1] <= .16 && b.bounds[3] >= .16)?.color, zonePRColor(20), 'low-sample high raw rate must not influence PR color')
const grid = Array.from({ length: 9 }, (_, i) => cell(String(i), [i%3/3, Math.floor(i/3)/3, (i%3+1)/3, (Math.floor(i/3)+1)/3], 1, i === 4 ? 0 : 20))
const bands = buildZoneRateContours(grid, 'swing')
const centre=bands.filter(b => b.bounds[0] < .5 && b.bounds[2] > .5 && b.bounds[1] < .5 && b.bounds[3] > .5)
assert.equal(centre.length,1);assert.equal(centre[0].color,'#64748b','missing-support cell is neutral grey, not a transparent hole or invented PR')
assert.ok(bands.every(b => b.bounds.every(Number.isFinite) && b.bounds[0] >= 0 && b.bounds[2] <= 1))
assert.ok(bands.length < 48*48, 'row-run compression bounds polygon count')
assert.ok(buildZoneRateContours([cell('w', [0,0,1,1], 21, 10, 'woba', 80)], 'woba').every(b => b.color === zonePRColor(80)))
assert.equal(formatZoneRate(2.1, 'woba'), '2.100')
assert.equal(zonePRColor(50), 'rgb(250,250,255)')
const ring = [cell('inside',[0,0,1,1],10,20,'swing',50), { ...cell('outside',[-.5,0,0,1],10,20,'swing',90), region:'outside' }]
const ringBands = buildZoneRateContours(ring,'swing')
const exterior = ringBands.filter(b => b.bounds[2] <= 0)
assert.ok(exterior.length && exterior.every(b => b.bounds[0] >= -.32 && b.opacity < .86), 'outside halo is bounded and weaker than zone fill')
assert.ok(Math.min(...exterior.map(b => b.opacity)) < Math.max(...exterior.map(b => b.opacity)), 'outside fill fades instead of a solid rectangular block')
console.log('Source-only PR contour checks PASS: neutral missing/low-sample cells, PR rather than absolute colors, bounds, non-mutation, compression, decimal preservation.')
const rawCells=[cell('raw',[0,0,1,1],4,5,'swing',null)]
const rawSnapshot=JSON.stringify(rawCells)
assert.ok(buildZoneRateContours(rawCells,'swing','rate').every(b=>b.color===zonePRColor(80)))
assert.ok(buildZoneRateContours(rawCells,'swing','pr').every(b=>b.color==='#64748b'))
assert.equal(JSON.stringify(rawCells),rawSnapshot,'absolute context display cannot modify original PR data')
const whiff=[cell('whiff',[0,0,1,1],1,5,'whiff',null)]
assert.ok(buildZoneRateContours(whiff,'whiff','rate').every(b=>b.color===zonePRColor(80)))
assert.ok(buildZoneRateContours([cell('low',[0,0,1,1],4,4)],'swing','rate').every(b=>b.color==='#64748b'))
console.log('Context absolute-rate colors PASS: separate PR cache, inverse Whiff, five-denominator floor, no input mutation.')
