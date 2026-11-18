// Pure data context checks. No browser, server or rendered DOM.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'
const source=fs.readFileSync(new URL('../utils/pitcherInGame.ts',import.meta.url),'utf8')
const js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const {previousReplayPitch,replayComparisonRows}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'))
const row=(game,pa,pitch,name,pitcher=1)=>({game_pk:game,at_bat_number:pa,pitch_number:pitch,pitch_name:name,pitcher})
const rows=[row(1,1,1,'Sinker'),row(1,1,2,'Slider'),row(1,1,3,'Changeup'),row(1,2,1,'Cutter'),row(1,2,3,'Slider'),row(2,1,1,'Curveball'),row(1,1,4,'Fastball',2)]
const before=JSON.stringify(rows)
assert.equal(previousReplayPitch(rows,rows[0]).key,'__first__')
assert.equal(previousReplayPitch(rows,rows[2]).key,'Slider')
assert.equal(previousReplayPitch(rows,rows[4]).key,null,'do not bridge a missing pitch')
assert.equal(previousReplayPitch(rows,rows[5]).key,'__first__','do not cross game/PA')
assert.equal(previousReplayPitch(rows,rows[6]).key,null,'do not borrow another pitcher within PA')
assert.equal(previousReplayPitch(rows,{...rows[2],at_bat_number:99}).key,null)
assert.equal(JSON.stringify(rows),before)
assert.deepEqual(replayComparisonRows(rows,rows[0],'pa'),[],'PA first pitch cannot display future balls')
assert.deepEqual(replayComparisonRows(rows,rows[2],'pa'),rows.slice(0,2),'only earlier pitches of this PA')
assert.deepEqual(replayComparisonRows(rows,rows[3],'pa'),[],'next PA must clear earlier PA balls')
assert.ok(replayComparisonRows(rows,rows[2],'game').every(r=>r.game_pk===1&&r.pitcher===1),'game comparison still excludes other game/pitcher')
assert.equal(JSON.stringify(rows),before,'comparison cannot modify raw pitches')
console.log('Replay Sequence context source PASS: same game/pitcher/PA exact preceding pitch, first pitch and gaps, immutable input.')
