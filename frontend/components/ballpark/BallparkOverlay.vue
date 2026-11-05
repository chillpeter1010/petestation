<template>
  <Teleport to="body">
    <div class="ballpark-overlay" @click.self="emit('close')">
      <section ref="dialog" role="dialog" aria-modal="true" aria-labelledby="ballpark-panel-title" tabindex="-1" @keydown="trapKeys">
        <header><div><small>{{ origin }} · {{ team || 'MLB' }}</small><h2 id="ballpark-panel-title">{{ title }}</h2></div><button ref="closeButton" type="button" @click="emit('close')">Close · Esc</button></header>
        <slot />
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
defineProps<{ title: string; origin: string; team: string }>()
const emit=defineEmits<{close:[]}>()
const dialog=ref<HTMLElement|null>(null), closeButton=ref<HTMLButtonElement|null>(null)
let previous: HTMLElement|null=null, overflow=''
onMounted(() => {
  previous=document.activeElement instanceof HTMLElement ? document.activeElement : null
  overflow=document.body.style.overflow
  document.body.style.overflow='hidden'
  closeButton.value?.focus({preventScroll:true})
})
onBeforeUnmount(() => {
  document.body.style.overflow=overflow
  if (previous?.isConnected) previous.focus({preventScroll:true})
})
function trapKeys(event: KeyboardEvent) {
  // R/C/WASD stay in the form; only Escape and Tab belong to this dialog.
  if(event.key==='Escape') { event.preventDefault();event.stopPropagation();emit('close');return }
  if(event.key!=='Tab')return
  const elements=Array.from(dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), iframe, [tabindex="0"]') || []).filter(el=>el.getClientRects().length>0)
  const first=elements[0],last=elements.at(-1)
  if (!first) {event.preventDefault();dialog.value?.focus();return}
  if(event.shiftKey && (document.activeElement===first || document.activeElement===dialog.value)) {event.preventDefault();last?.focus()}
  else if(!event.shiftKey && (document.activeElement===last || document.activeElement===dialog.value)) {event.preventDefault();first.focus()}
}
</script>

<style scoped>
.ballpark-overlay{position:fixed;inset:0;z-index:900;display:grid;place-items:center;padding:20px;background:rgb(0 0 0 / 78%)}
section{width:min(1400px,96vw);max-height:94dvh;overflow:auto;overscroll-behavior:contain;padding:22px;border:1px solid #d99a38;border-radius:14px;color:var(--color-foreground,#f6f0dd);background:var(--color-background,#121923);box-shadow:0 20px 80px #0008}
header{display:flex;justify-content:space-between;align-items:start;gap:20px;margin-bottom:20px}h2{margin:4px 0}small{color:#d7ac63}
button{min-height:44px;padding:8px 16px;border:1px solid #d99a38;border-radius:7px;background:#252f24;color:#fff3db;cursor:pointer;white-space:nowrap}
button:focus-visible{outline:3px solid #ffbd53;outline-offset:3px}
@media(max-width:600px){.ballpark-overlay{padding:6px}section{padding:12px;width:100%;max-height:98dvh}}
</style>
