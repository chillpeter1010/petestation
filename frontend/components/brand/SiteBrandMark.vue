<template>
  <span class="site-brand-mark">
    <img v-if="!failed" src="/brand/dapeter-logo.png" alt="DaPeter" width="1672" height="941" decoding="async" @error="failed=true">
    <span v-else class="brand-fallback">DaPeter</span>
  </span>
</template>

<script setup lang="ts">
const failed=ref(false)
</script>

<style scoped>
.site-brand-mark{display:block;width:160px;max-width:100%}.site-brand-mark img{display:block;width:100%;height:auto;object-fit:contain}.brand-fallback{display:block;color:#fff;background:#000;border-radius:5px;padding:8px 12px;font-size:25px;font-weight:900;font-style:italic}
</style>
