// In-memory URL and response-state tests only. No network, browser or video decoding.
import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'
import * as vue from 'vue'
import {parse} from '@vue/compiler-sfc'
const source=fs.readFileSync(new URL('../components/charts/PitchVideoPlayer.vue',import.meta.url),'utf8')
const script=parse(source).descriptor.scriptSetup.content
const js=ts.transpileModule(script,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace(/^export \{\};?$/gm,'')
const setup=new (Object.getPrototypeOf(async function(){}).constructor)('env',`with(env){${js};return {resolve,directUrl,loading,failed,direct}}`)
const props={url:'https://baseballsavant.mlb.com/sporty-videos?playId=one'}
let response={direct_video_url:'https://mlb-cuts-diamond.mlb.com/one.mp4'},pending
const state=await setup({...vue,defineProps:()=>props,watch:()=>{},onBeforeUnmount:()=>{},useApi:()=>({teamDirectVideo:async()=>pending?await pending:response})})
await state.resolve();assert.match(state.directUrl.value,/one\.mp4$/)
assert.equal(state.direct('javascript:alert(1)'), '');assert.equal(state.direct('https://example.com/page.html'),'')
props.url='https://mlb-cuts-diamond.mlb.com/direct.mp4';await state.resolve();assert.match(state.directUrl.value,/direct\.mp4$/)
props.url='https://baseballsavant.mlb.com/sporty-videos?playId=bad';response={direct_video_url:null};await state.resolve();assert.equal(state.directUrl.value,'');assert.equal(state.loading.value,false)
let release;pending=new Promise(r=>release=r);const old=state.resolve();pending=null
props.url='https://mlb-cuts-diamond.mlb.com/latest.mp4';await state.resolve();release({direct_video_url:'https://mlb-cuts-diamond.mlb.com/old.mp4'});await old
assert.match(state.directUrl.value,/latest\.mp4$/)
assert.doesNotMatch(source,/<iframe/);assert.match(source,/<video/)
console.log('Video player source PASS: direct media only, metadata resolution, unavailable state and stale-response exclusion. No playback/visual acceptance.')
