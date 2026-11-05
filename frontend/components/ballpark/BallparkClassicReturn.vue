<template><!-- Keyboard R return is intentionally invisible; typing/dialog guards remain active. --></template>
<script setup lang="ts">
const {origin,restore}=useBallparkReturn()
const {user}=useAuth()
let returning=false
function returnWithR(event:KeyboardEvent){
  if(!origin.value || origin.value.accountId!==user.value?.id || returning || document.hidden)return
  if(event.defaultPrevented || event.repeat || event.isComposing || event.ctrlKey || event.metaKey || event.altKey || event.key.toLowerCase()!=='r')return
  const typing='input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[role="combobox"],[role="listbox"],[role="menu"]'
  if(event.composedPath().some(node=>node instanceof Element && node.closest(typing)) || document.activeElement?.closest(typing))return
  if(document.querySelector('dialog[open],[aria-modal="true"],[role="dialog"],[role="alertdialog"]'))return
  event.preventDefault()
  returning=true
  void Promise.resolve(navigateTo(origin.value.path)).finally(()=>{returning=false})
}
onMounted(()=>{restore();window.addEventListener('keydown',returnWithR)})
onBeforeUnmount(()=>window.removeEventListener('keydown',returnWithR))
</script>
