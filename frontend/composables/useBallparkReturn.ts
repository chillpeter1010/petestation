import { safeWalkReturn } from '~/components/ballpark/runtime/bridgeContract'

// Nuxt-only return token: room/query context, never Phaser instances or persisted positions (E5).
export function useBallparkReturn() {
  const {user}=useAuth()
  const route=useRoute()
  const origin=useState<{path:string;label:string;accountId:number|null}|null>('ballpark-classic-origin',()=>null)
  const storageKey=()=>`ballpark-classic-origin-v1:${user.value?.id || 'anonymous'}`
  function remember(path:string,label:string){
    if(!safeWalkReturn(path))return
    origin.value={path,label,accountId:user.value?.id || null}
    if(import.meta.client)try{sessionStorage.setItem(storageKey(),JSON.stringify(origin.value))}catch{/* In-memory return remains available. */}
  }
  function restore(){
    if(!import.meta.client)return
    const from=route.query.ballpark_from
    if(user.value && safeWalkReturn(from)){
      const room=new URL(from,location.origin).searchParams.get('room')||'campus'
      remember(from,room.split('-').map(word=>word.charAt(0).toUpperCase()+word.slice(1)).join(' '));return
    }
    if(origin.value?.accountId===(user.value?.id || null))return
    origin.value=null
    try{const saved=JSON.parse(sessionStorage.getItem(storageKey())||'null');if(saved && saved.accountId===(user.value?.id || null) && typeof saved.label==='string')remember(saved.path,saved.label)}catch{/* Ignore invalid return token. */}
  }
  function clear(){origin.value=null;if(import.meta.client)try{sessionStorage.removeItem(storageKey())}catch{/* Storage may be disabled. */}}
  watch(()=>user.value?.id,restore)
  watch(()=>route.query.ballpark_from,restore,{immediate:true,flush:'sync'})
  return {origin,remember,restore,clear}
}
