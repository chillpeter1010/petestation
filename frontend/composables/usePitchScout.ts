import {scoutKey,type ScoutRequest,type ScoutResponse} from '~/utils/pitchScout'

export function usePitchScout(request:ComputedRef<ScoutRequest|null>,next:ComputedRef<ScoutRequest|null>){
  const api=useApi(),data=shallowRef<ScoutResponse|null>(null),loading=ref(false),error=ref(false)
  const values=new Map<string,{data:ScoutResponse;until:number}>(),pending=new Map<string,Promise<ScoutResponse>>()
  let version=0,timer:ReturnType<typeof setTimeout>|undefined
  function fetch(p:ScoutRequest,force=false){
    const key=scoutKey(p),cached=values.get(key)
    if(!force&&cached&&cached.until>Date.now())return Promise.resolve(cached.data)
    const active=pending.get(key);if(active)return active
    const result=api.pitchScout(p).then(value=>{if(values.size>=64)values.delete(values.keys().next().value!);values.set(key,{data:value,until:Date.now()+120000});return value}).finally(()=>pending.delete(key))
    pending.set(key,result);return result
  }
  async function load(force=false){
    const token=++version,p=request.value;data.value=null;loading.value=false;error.value=false;clearTimeout(timer)
    if(!p)return
    const cached=values.get(scoutKey(p))
    if(!force&&cached&&cached.until>Date.now())data.value=cached.data
    else{loading.value=true;try{const result=await fetch(p,force);if(token===version)data.value=result}catch{if(token===version)error.value=true}finally{if(token===version)loading.value=false}}
    if(token===version&&next.value){const n=next.value;timer=setTimeout(()=>{void fetch(n).catch(()=>{})},80)}
  }
  watch(()=>request.value?scoutKey(request.value):'',()=>void load(),{immediate:true,flush:'sync'})
  onBeforeUnmount(()=>{++version;clearTimeout(timer)})
  return {data,loading,error,retry:()=>load(true)}
}
