import type { BatterZoneRatesResponse } from '~/types/api'

export type HeatmapRequest = {year:number;batterId:number;pitcherHand:'All'|'L'|'R'}
export const heatmapRequestKey=(p:HeatmapRequest)=>`${p.year}:${p.batterId}:${p.pitcherHand}`

// Component-scoped: foreground and one-ahead prefetch share the same request.
export function createBatterHeatmapCache<T=BatterZoneRatesResponse>(now=()=>Date.now(),ttl=(data:T)=>(data as {benchmark_status?:string}).benchmark_status==='ready'?120_000:5_000){
  const values=new Map<string,{until:number;data:T}>()
  const pending=new Map<string,Promise<T>>()
  function peek(p:HeatmapRequest){const key=heatmapRequestKey(p),item=values.get(key);if(item&&item.until>now())return item.data;values.delete(key)}
  function load(p:HeatmapRequest,fetcher:(params:HeatmapRequest)=>Promise<T>,force=false){
    const key=heatmapRequestKey(p),cached=force?undefined:peek(p)
    if(cached)return Promise.resolve(cached)
    const active=pending.get(key);if(active)return active
    const request=Promise.resolve().then(()=>fetcher(p)).then(data=>{
      if(values.size>=32)values.delete(values.keys().next().value!)
      values.set(key,{data,until:now()+ttl(data)})
      return data
    }).finally(()=>{pending.delete(key)})
    pending.set(key,request);return request
  }
  return {peek,load}
}
