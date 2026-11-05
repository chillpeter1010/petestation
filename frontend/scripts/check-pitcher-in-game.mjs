// Pure data/source checks only: no browser, rendered DOM, network or images.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import crypto from 'node:crypto'
import ts from 'typescript'

const root = new URL('../../', import.meta.url)
const read = name => fs.readFileSync(new URL(name, root), 'utf8')
const utilPath = 'frontend/utils/pitcherInGame.ts'
const js = ts.transpileModule(read(utilPath), { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
const { inGameOutings, initialInGameOuting, matchesInGameFilters } = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'))
const checks = []
function check(name, run) { run(); checks.push(name) }
const original = [
  { 'Game PK': 12, Date: '2026-09-25', Opponent: 'AZ' },
  { 'Game PK': 10, Date: '2026-09-27', Label: 'Game one' },
  { 'Game PK': 11, Date: '2026-09-27', Label: 'Game two' },
  { 'Game PK': 11, Date: '2026-09-27' },
  { 'Game PK': 0 }, { 'Game PK': null }, { 'Game PK': 'bad' }, { 'Game PK': 1.2 }
]
const before = JSON.stringify(original), outings = inGameOutings(original)
check('latest outing default, deterministic same-date ordering and no source mutation', () => {
  assert.deepEqual(outings.map(row => row.gamePk), [11, 10, 12])
  assert.equal(initialInGameOuting(outings), 11)
  assert.equal(JSON.stringify(original), before)
  assert.match(outings[0].label, /Game 11/)
})
check('valid explicit game deep link, invalid game fallback and empty season', () => {
  assert.equal(initialInGameOuting(outings, 12), 12)
  assert.equal(initialInGameOuting(outings, 999), 11)
  assert.equal(initialInGameOuting([], 12), null)
})
const all = { stand: 'All', count: 'All', pitch: 'All', pitchResult: 'All', inPlayResult: 'All', paResult: 'All', catcher: 'All' }
const pitch = { stand: 'R', balls: 0, strikes: 2, pitch_name: 'Slider', pitch_result_group: 'Whiff', in_play_result_group: 'Other', pa_result_group: 'Strikeout', catcher_name: 'Moreno', trajectory_status: 'unavailable', trajectory_points: [] }
check('all eligible rows including unavailable trajectory remain selectable', () => {
  const snapshot = JSON.stringify(pitch)
  assert.equal(matchesInGameFilters(pitch, all), true)
  assert.equal(matchesInGameFilters(pitch, { ...all, stand: 'R', pitch: 'Slider', pitchResult: 'Whiff', paResult: 'Strikeout', catcher: 'Moreno' }), true)
  assert.equal(matchesInGameFilters(pitch, { ...all, inPlayResult: 'Hit' }), false)
  assert.equal(matchesInGameFilters(pitch, { ...all, stand: 'L' }), false)
  assert.equal(JSON.stringify(pitch), snapshot)
})
check('exact/multi-count and ahead/two-strike filters preserve existing semantics', () => {
  for (const count of ['0-2', 'Two Strikes', 'Pitcher Ahead', '1-0,0-2']) assert.equal(matchesInGameFilters(pitch, { ...all, count }), true)
  for (const count of ['Hitter Ahead', '1-0']) assert.equal(matchesInGameFilters(pitch, { ...all, count }), false)
})
const panelPath = 'frontend/components/charts/PitchReplayPanel.vue', tabPath = 'frontend/components/pitcher-personal/PitcherInGameTab.vue'
const gamePath = 'frontend/components/games/GamePitcherAnalysisPanel.vue', pagePath = 'frontend/pages/pitcher-personal.vue'
const panel = read(panelPath), tab = read(tabPath), game = read(gamePath), page = read(pagePath)
check('Game and Personal delegate to the same lazy panel and unchanged game-scoped API', () => {
  assert.match(game, /<LazyPitchReplayPanel v-if="mode === 'replay'"/)
  assert.doesNotMatch(game, /api\.gamePitcherReplay/)
  assert.match(tab, /<LazyPitchReplayPanel/)
  assert.match(panel, /api\.gamePitcherReplay\(\{ year: props.year, gamePk: props.gamePk, pitcherId: props.pitcherId \}\)/)
})
check('In game label/direct tab, lazy fetch and keyed context are wired', () => {
  assert.match(page, /key: 'in-game', label: 'In game'/)
  assert.match(page, /<LazyPitcherInGameTab[\s\S]*?v-else-if="activeTab === 'in-game'"/)
  assert.match(tab, /title="In game"/)
  assert.match(tab, /initialInGameOuting\(outings.value, props.initialGamePk\)/)
  assert.match(tab, /:key="`\$\{year\}:\$\{pitcherId\}:\$\{selectedGamePk\}`"/)
})
check('pending response and unmount source guards clear previous context', () => {
  for (const source of [panel, tab]) {
    assert.match(source, /\+\+requestVersion/)
    assert.match(source, /version (?:===|!==) requestVersion/)
    assert.match(source, /onBeforeUnmount\(\(\) => \{ requestVersion \+= 1 \}\)/)
  }
  assert.match(panel, /analysis.value = null/)
  assert.match(tab, /selectedGamePk.value = null/)
})
check('chart change is title-only and historical trajectory contract remains named', () => {
  assert.match(read('frontend/components/charts/PitchReplayChart.vue'), /<h3>\{\{ title \}\}<\/h3>/)
  assert.match(panel, /Historical Statcast ball-path reconstruction/)
  assert.match(read('backend/app/services/game_pitcher_analysis_service.py'), /PITCH_REPLAY_CONTRACT_VERSION = "pitch_trajectory_statcast_v1"/)
})
const report = { updated_at: '2026-11-04', scope: 'source_only_not_visual_acceptance', status: 'pass', checks,
  files: Object.fromEntries([utilPath, panelPath, tabPath, gamePath, pagePath, 'frontend/components/charts/PitchReplayChart.vue', 'backend/app/services/game_pitcher_analysis_service.py'].map(name => [name, crypto.createHash('sha256').update(read(name)).digest('hex')])),
  manual_acceptance: 'pending_user; no browser/DOM/image/API interaction tests performed' }
const reportIndex = process.argv.indexOf('--report')
if (reportIndex >= 0) fs.writeFileSync(new URL(process.argv[reportIndex + 1], root), JSON.stringify(report, null, 2) + '\n')
console.log(`Pitcher In game source-only PASS: ${checks.length} checks; not visual acceptance`)
