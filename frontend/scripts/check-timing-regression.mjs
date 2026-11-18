// Data and math only; no browser or visual acceptance.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { createRequire } from 'node:module'
const ts = createRequire(import.meta.url)('typescript')
const compile = path => ts.transpileModule(fs.readFileSync(new URL(path, import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText
const uri = source => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64')
const { timingRegressionPoints, timingRegressionDomain } = await import(uri(compile('../utils/timingRegression.ts')))
const { linearRegression } = await import(uri(compile('../utils/linearRegression.ts')))
const row = (id, x, y) => ({ batter_id: id, axis_metrics: { x, y } })
const rows = [row(1, -1, -1), row(2, 0, 1), row(3, 1, 3), row(4, null, 100), row(5, 2, NaN), row(6, Infinity, 2)]
const before = JSON.stringify(rows)
const points = timingRegressionPoints(rows, 'x', 'y')
assert.equal(points.length, 3)
assert.deepEqual(points.map(p => p.x), [-1, 0, 1])
const fit = linearRegression(points)
assert.equal(fit.n, 3)
assert.equal(fit.slope, 2)
assert.equal(fit.intercept, 1)
assert.equal(fit.rSquared, 1)
assert.equal(fit.pValue, 0)
assert.equal(linearRegression([{ x: 1, y: 1 }, { x: 1, y: 2 }, { x: 1, y: 3 }]), null)
assert.equal(linearRegression(points.slice(0, 2)), null)
assert.deepEqual(timingRegressionDomain([]), [0, 1])
assert.ok(timingRegressionDomain([0, 0])[1] > timingRegressionDomain([0, 0])[0])
assert.equal(timingRegressionPoints(Array.from({ length: 250 }, (_, i) => row(i, i, i)), 'x', 'y').length, 250)
assert.equal(JSON.stringify(rows), before)
console.log('Timing regression checks PASS: finite complete cases, genuine zero/negative values, all samples, shared OLS, degenerate axes, immutable input.')
