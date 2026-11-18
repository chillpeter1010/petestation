// Vue reactivity and mocked transport only; no DOM, browser or HTTP.
import fs from 'node:fs'
import assert from 'node:assert/strict'
import ts from 'typescript'
import {computed,ref,shallowRef,watch,effectScope,nextTick} from 'vue'
const url=src=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(src,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText).toString('base64')
const utils=url(fs.readFileSync('utils/pitchScout.ts','utf8'))
const transport=[],cleanup=[]
Object.assign(globalThis,{computed,ref,shallowRef,watch,useApi:()=>({pitchScout:p=>new Promise((resolve,reject)=>transport.push({p,resolve,reject}))}),onBeforeUnmount:fn=>cleanup.push(fn)})
const {usePitchScout}=await import(url(fs.readFileSync('composables/usePitchScout.ts','utf8').replace("'~/utils/pitchScout'",JSON.stringify(utils))))
const a={year:2026,batterId:5,pitcherHand:'R',stand:'L',beforeDate:'2026-09-27',balls:0,strikes:0,previousType:'__first__',previousResult:'__first__'}
const request=ref(a),scope=effectScope()
const state=scope.run(()=>usePitchScout(computed(()=>request.value),computed(()=>null)))
assert.equal(state.loading.value,true)
request.value={...a,batterId:6}
assert.equal(transport.length,2)
const flush=async()=>{for(let i=0;i<5;i++)await Promise.resolve();await nextTick()}
transport[0].resolve({batter:5});await flush()
assert.equal(state.data.value,null,'late old batter cannot replace current context')
transport[1].resolve({batter:6});await flush()
assert.equal(state.data.value.batter,6)
request.value=a;await flush();assert.equal(state.data.value.batter,5);assert.equal(transport.length,2,'warm context uses cache')
const retry=state.retry();assert.equal(transport.length,3,'explicit retry bypasses completed cache');transport[2].reject(new Error('offline'));await retry
assert.equal(state.error.value,true);assert.equal(state.data.value,null)
const second=state.retry();assert.equal(transport.length,4);transport[3].resolve({batter:5});await second
assert.equal(state.error.value,false)
for(const fn of cleanup)fn();scope.stop()
console.log('Scout cache source PASS: late identity rejected, warm reuse, forced retry, error recovery and cleanup.')
