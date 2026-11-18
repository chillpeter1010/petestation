<template>
  <div class="pitch-video-player" :aria-busy="loading">
    <video v-if="directUrl && !failed" :key="directUrl" :src="directUrl" controls playsinline preload="metadata" aria-label="Selected pitch video" @error="failed=true" />
    <p v-else-if="loading" role="status">Loading video…</p>
    <p v-else role="alert">Video unavailable. <button type="button" @click="resolve">Retry</button> You can still open the original source below.</p>
  </div>
</template>
<script setup lang="ts">
const props=defineProps<{url:string}>()
const api=useApi(),directUrl=ref(''),loading=ref(false),failed=ref(false)
let version=0
function direct(value:unknown){try{const url=new URL(String(value||''));return url.protocol==='https:'&&/\.(mp4|m3u8)$/i.test(url.pathname)?url.href:''}catch{return ''}}
async function resolve(){
  const request=++version;directUrl.value='';failed.value=false;loading.value=true
  try{
    const immediate=direct(props.url)
    if(immediate){directUrl.value=immediate;return}
    const url=new URL(props.url),playId=url.hostname==='baseballsavant.mlb.com'?url.searchParams.get('playId'):null
    if(!playId)return
    const result=await api.teamDirectVideo(playId)
    if(request===version)directUrl.value=direct(result.direct_video_url)
  }catch{if(request===version)failed.value=true}finally{if(request===version)loading.value=false}
}
watch(()=>props.url,resolve,{immediate:true})
onBeforeUnmount(()=>{++version})
</script>
<style scoped>
.pitch-video-player{display:grid;place-items:center;background:#000;min-height:180px;color:#dce6f2;overflow:hidden}video{display:block;width:100%;max-height:65vh;aspect-ratio:16/9;background:#000}p{padding:20px;text-align:center}button{font:inherit;cursor:pointer;padding:6px 10px}
</style>
