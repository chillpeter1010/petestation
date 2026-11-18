// Source-only request/cache checks; no browser or rendered UI.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'
const source=fs.readFileSync(new URL('../utils/batterHeatmapCache.ts',import.meta.url),'utf8')
const js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const {createBatterHeatmapCache}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'))
let clock=0,calls=0,resolve
const cache=createBatterHeatmapCache(()=>clock)
const request={year:2026,batterId:1,pitcherHand:'R'}
const data={status:'ready',benchmark_status:'ready'}
const fetcher=()=>{calls++;return new Promise(done=>{resolve=done})}
const prefetch=cache.load(request,fetcher),foreground=cache.load(request,fetcher)
assert.strictEqual(prefetch,foreground,'switch must reuse in-flight prefetch')
await Promise.resolve();assert.equal(calls,1)
resolve(data);await foreground
assert.strictEqual(cache.peek(request),data,'switch can synchronously use warm data')
await cache.load(request,fetcher);assert.equal(calls,1,'warm identity must not fetch again')
assert.equal(cache.peek({...request,pitcherHand:'L'}),undefined,'never reuse opposite hand')
assert.equal(cache.peek({...request,batterId:2}),undefined,'never reuse another batter')
assert.equal(cache.peek({...request,year:2025}),undefined,'never reuse another season')
clock=120001;assert.equal(cache.peek(request),undefined,'ready data expires')
await cache.load(request,async()=>({status:'ready',benchmark_status:'stale'}))
clock+=5001;assert.equal(cache.peek(request),undefined,'non-ready baseline retries soon')
await assert.rejects(cache.load(request,async()=>{throw Error('offline')}))
await cache.load(request,async()=>data)
assert.strictEqual(cache.peek(request),data,'failed request must not poison retries')
await cache.load(request,async()=>({...data,revision:2}),true)
assert.equal(cache.peek(request).revision,2,'explicit Retry bypasses completed cache')
console.log('Heatmap cache PASS: in-flight deduplication, warm switch, identity isolation, expiry, failed retry, refresh.')
