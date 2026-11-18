<template>
  <NuxtLink
    class="petehub-logo"
    :class="`petehub-logo--${size}`"
    :to="to"
    :aria-label="ariaLabel"
  >
    <SiteBrandMark />
  </NuxtLink>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  size?: 'home' | 'compact'
  to?: string
  ariaLabel?: string
}>(), {
  size: 'compact',
  to: '/',
  ariaLabel: 'DaPeter home'
})
</script>

<style scoped>
.petehub-logo {
  display: inline-flex;
  align-items: center;
  color: #f7f7f7;
  font-family: inherit;
  font-weight: 950;
  letter-spacing: -1.4px;
  line-height: normal;
  text-decoration: none;
}

.petehub-logo--home { width:clamp(180px,20vw,240px); }
.petehub-logo--compact { width:160px; }
.petehub-logo :deep(.site-brand-mark){width:100%}
.petehub-logo:focus-visible{outline:2px solid #00d4cc;outline-offset:4px;border-radius:5px}

</style>
