// Source-only contracts; no browser, DOM renderer, image checks or real input.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import ts from 'typescript'

const root = new URL('../../', import.meta.url)
const read = name => fs.readFileSync(new URL(name, root), 'utf8')
const guardPath = 'frontend/components/ballpark/runtime/runtimeGuards.ts'
const js = ts.transpileModule(read(guardPath), { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
const { createRuntimeLoadGate, createGamepadGate } = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'))
const checks = []
function check(name, run) { run(); checks.push(name) }
check('superseded runtime load is aborted and cannot update current state', () => {
  const gate = createRuntimeLoadGate(), first = gate.start(), second = gate.start()
  assert.equal(first.aborted, true); assert.equal(gate.isCurrent(first), false)
  assert.equal(gate.isCurrent(second), true)
  gate.cancel(); assert.equal(second.aborted, true); assert.equal(gate.isCurrent(second), false)
  assert.equal(gate.isCurrent(gate.start()), true)
})
check('gamepad waits for neutral on mount and after pause/blur', () => {
  const gate = createGamepadGate()
  assert.deepEqual(gate.sample(1, 0, true), { x: 0, y: 0, interact: false })
  gate.sample(0, 0, false)
  assert.equal(gate.sample(1, 0, false).x, 1)
  gate.block(); assert.equal(gate.sample(1, 0, false).x, 0)
  gate.sample(0, 0, false); assert.equal(gate.sample(-1, 0, false).x, -1)
})
check('gamepad action is edge-triggered and deadzone/non-finite axes are safe', () => {
  const gate = createGamepadGate(); gate.sample(0, 0, false)
  assert.equal(gate.sample(0, 0, true).interact, true)
  assert.equal(gate.sample(0, 0, true).interact, false)
  gate.sample(0, 0, false); assert.equal(gate.sample(0, 0, true).interact, true)
  assert.deepEqual(gate.sample(.1, NaN, false), { x: 0, y: 0, interact: false })
})
const runtimePath = 'frontend/components/ballpark/runtime/createBallparkGame.ts'
const wrapperPath = 'frontend/components/ballpark/BallparkRuntime.client.vue'
const runtime = read(runtimePath), wrapper = read(wrapperPath)
check('Phaser import remains lazy and Classic shell has no engine import', () => {
  assert.match(runtime, /await import\('phaser'\)/)
  const syntax = ts.createSourceFile(runtimePath, runtime, ts.ScriptTarget.Latest, true)
  for (const node of syntax.statements) if (ts.isImportDeclaration(node) && node.moduleSpecifier.text === 'phaser') assert.equal(node.importClause?.isTypeOnly, true)
  for (const name of ['frontend/app.vue', 'frontend/nuxt.config.ts']) assert.doesNotMatch(read(name), /(?:from\s*|import\s*\()['"](?:phaser|[^'"]*createBallparkGame)/)
  assert.match(read('frontend/pages/ballpark/play.vue'), /<ClientOnly>/)
})
check('load cancellation, error cleanup and owned-canvas teardown stay wired', () => {
  assert.equal((runtime.match(/if \(options\.signal\?\.aborted\)/g) || []).length, 2)
  assert.match(wrapper, /const signal = loadGate\.start\(\)/)
  assert.match(wrapper, /if \(!isCurrent\(\)\) return/)
  assert.match(wrapper, /onBeforeUnmount/)
  assert.match(runtime, /removeEventListener\('visibilitychange', visibility\)/)
  assert.match(runtime, /removeEventListener\('abort', destroy\)/)
  assert.match(runtime, /observer\?\.disconnect\(\)/)
  assert.doesNotMatch(runtime, /parent\.replaceChildren/)
  assert.match(runtime, /game\.canvas\?\.parentNode === options\.parent/)
  assert.match(runtime, /game\.destroy\(true\)/)
})
const inputs = [guardPath, runtimePath, wrapperPath, 'frontend/pages/ballpark/play.vue', 'frontend/app.vue', 'frontend/nuxt.config.ts']
const evidence = { schema_version: 1, generated_at: new Date().toISOString(), scope: 'E1/E2 source-only contracts', status: 'PASS', checks,
  input_hashes: Object.fromEntries(inputs.map(name => [name, crypto.createHash('sha256').update(read(name)).digest('hex')])),
  limitations: ['No browser or visual/interaction acceptance', 'Import/source review is not a measured production bundle graph', 'Scheduled Phaser destroy is not measured GPU/listener leak certification; E6 remains separate', 'Accepted D5 movement/scene geometry reused, not re-tested visually'], manual_acceptance: 'pending_user' }
if (process.argv.includes('--report')) {
  const filename = process.argv[process.argv.indexOf('--report') + 1]
  const destination = new URL(filename, root)
  assert.ok(destination.pathname.startsWith(root.pathname) && !path.isAbsolute(filename), 'Report stays within workspace')
  fs.writeFileSync(destination, JSON.stringify(evidence, null, 2) + '\n', 'utf8')
}
console.log(`E1/E2 source-only contracts PASS (${checks.length} checks); manual acceptance pending.`)
