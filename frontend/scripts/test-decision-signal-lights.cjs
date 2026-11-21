const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const assert = require('node:assert/strict')
const ts = require('typescript')

const root = path.resolve(__dirname, '..')
const source = fs.readFileSync(path.join(root, 'utils/decisionSignalLights.ts'), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } })
const sandbox = { exports: {} }
vm.runInNewContext(compiled.outputText, sandbox)
const { assessSignalLights } = sandbox.exports
const gates = { value: 'pass', legal: 'pass', availability: 'pass', statePersistence: 'pass', validation: 'pass' }
const lights = states => states.map((state, index) => ({ id: 'ABCD'[index], title: 'signal', state, calibrated: true, supportKnown: true, reason: '', evidence: [] }))
let passed = 0
function test(name, check) { check(); passed++; process.stdout.write(`PASS ${name}\n`) }

test('missing evidence is not a zero score or normal status', () => {
  const result = assessSignalLights(lights(['red', 'red', 'gray', 'gray']), gates, 'demo')
  assert.equal(result.score, null)
  assert.equal(result.knownScore, 4)
  assert.equal(result.color, 'gray')
  assert.equal(result.researchCandidate, false)
  assert.equal(result.scoreRange[1], 8)
})
test('uncalibrated observed signals cannot acquire confident colors', () => {
  const input = lights(['green', 'red', 'red', 'green']).map(light => ({ ...light, calibrated: false }))
  const result = assessSignalLights(input, gates, 'observed')
  assert.equal(result.known, 0)
  assert.equal(result.score, null)
  assert.equal(result.researchCandidate, false)
})
test('five score bands and full-range monotonicity', () => {
  const colors = ['green', 'lime', 'lime', 'yellow', 'yellow', 'orange', 'orange', 'red', 'red']
  for (let score = 0; score <= 8; score++) {
    let left = score
    const states = [0, 1, 2, 3].map(() => { const n = Math.min(left, 2); left -= n; return ['green', 'yellow', 'red'][n] })
    const result = assessSignalLights(lights(states), gates, 'demo')
    assert.equal(result.score, score)
    assert.equal(result.color, colors[score])
  }
})
test('high score alone cannot skip the two-red or core-evidence gate', () => {
  const result = assessSignalLights(lights(['yellow', 'yellow', 'red', 'red']), gates, 'demo')
  assert.equal(result.score, 6)
  assert.equal(result.researchCandidate, false)
})
test('each external condition independently blocks candidate promotion', () => {
  const input = lights(['red', 'red', 'yellow', 'green'])
  for (const key of ['value', 'legal', 'availability', 'statePersistence', 'validation']) {
    for (const state of ['fail', 'unknown']) {
      assert.equal(assessSignalLights(input, { ...gates, [key]: state }, 'demo').researchCandidate, false)
    }
  }
})
test('eligible demonstrations remain non-operational', () => {
  const result = assessSignalLights(lights(['red', 'red', 'red', 'yellow']), gates, 'demo')
  assert.equal(result.researchCandidate, true)
  assert.equal(result.recommendationAllowed, false)
})
test('support missing blocks even a calibrated observation', () => {
  const input = lights(['red', 'red', 'red', 'red'])
  input[0].supportKnown = false
  assert.equal(assessSignalLights(input, gates, 'observed').researchCandidate, false)
})
test('a duplicated cause cannot count as a second vote', () => {
  const input = lights(['red', 'red', 'green', 'green']); input[1].id = 'A'
  assert.throws(() => assessSignalLights(input, gates, 'demo'), /Exactly one/)
})
test('invalid severity cannot produce a nonfinite score', () => {
  const input = lights(['red', 'red', 'green', 'green']); input[0].state = 'invalid'
  assert.throws(() => assessSignalLights(input, gates, 'demo'), /Unknown signal/)
})
test('all retained real cases stay gray and block recommendations', () => {
  const data = JSON.parse(fs.readFileSync(path.join(root, '../data/sample/petehub_pitcher_decision_signal_lights_v1.json'), 'utf8'))
  assert.equal(data.cases.length, 11)
  assert.equal(data.counts.belowObservationMinimum, 7)
  for (const item of data.cases) {
    const result = assessSignalLights(item.lights, item.gates, 'observed')
    assert.equal(result.known, 0)
    assert.equal(result.researchCandidate, false)
    assert.equal(result.recommendationAllowed, false)
    assert.equal(item.gates.statePersistence, 'unknown')
    assert.equal(item.gates.availability, 'unknown')
  }
})
test('colors and persistence cannot bypass missing predictive validation', () => {
  const input = lights(['red', 'red', 'red', 'yellow'])
  const { validation, ...legacyGates } = gates
  assert.equal(assessSignalLights(input, legacyGates, 'observed').researchCandidate, false)
  assert.equal(assessSignalLights(input, { ...gates, validation: 'fail' }, 'observed').researchCandidate, false)
})
test('calibrated real snapshots preserve unknowns and unsuccessful predictive support', () => {
  const data = JSON.parse(fs.readFileSync(path.join(root, '../data/sample/petehub_pitcher_decision_signal_lights_v2.json'), 'utf8'))
  assert.equal(data.calibrationSummary.replay.flow.nominal_research_alerts, 0)
  for (const item of data.cases) {
    const result = assessSignalLights(item.lights, item.gates, 'observed')
    assert.equal(result.researchCandidate, false)
    assert.equal(result.recommendationAllowed, false)
    assert.equal(item.gates.validation, 'fail')
    assert.equal(item.gates.availability, 'unknown')
    assert.equal(result.known, item.lights.filter(light => light.supportKnown).length)
    if (item.lights.some(light => !light.supportKnown)) assert.equal(result.score, null)
  }
})
process.stdout.write(`${passed} signal-light contract tests passed\n`)
