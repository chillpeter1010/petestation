import { createWorldRepository, emptyWorldSave, WORLD_REVISION, type WorldRoom, type WorldPosition } from '~/components/ballpark/runtime/worldState'
import { normalizeMlbTeamCode } from '~/config/mlbTeams'

// Browser-local, account-scoped position save. No auth secrets, engine objects or server sync.
export function useBallparkWorld(){
  const {user}=useAuth()
  const owner=user.value?.id || 0
  const save=shallowRef(emptyWorldSave(owner)),notice=ref(''),loaded=ref(false)
  let repository:ReturnType<typeof createWorldRepository>|undefined,timer:ReturnType<typeof setTimeout>|undefined,dirty=false
  function load(){
    if(loaded.value)return
    try{repository=createWorldRepository(window.localStorage,owner);const result=repository.load();save.value=result.save;notice.value=result.notice}
    catch{notice.value='Browser storage is unavailable. This visit remains in memory only.'}
    loaded.value=true
  }
  function flush(){
    clearTimeout(timer);timer=undefined
    // The repository key is frozen to the owner. Flush their last captured state even on logout.
    if(!loaded.value||!dirty)return
    if(repository && !repository.write(save.value))notice.value='Could not save to browser storage. This visit remains in memory; Classic UI is still available.'
    dirty=false
  }
  function update(room:WorldRoom,position:WorldPosition,team:string){
    if(!loaded.value || user.value?.id!==owner)return
    const old=save.value.rooms[room],normalized=normalizeMlbTeamCode(team)
    if(save.value.last_room===room && save.value.viewing_team===normalized && old?.x===position.x && old?.y===position.y && old?.facing===position.facing && old?.objectId===position.objectId)return
    save.value={...save.value,world_revision:WORLD_REVISION,last_room:room,viewing_team:normalized,saved_at:new Date().toISOString(),rooms:{...save.value.rooms,[room]:position}}
    dirty=true
    if(!timer)timer=setTimeout(flush,1000)
  }
  onBeforeUnmount(flush)
  return {save,notice,load,update,flush}
}
