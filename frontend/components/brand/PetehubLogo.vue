<template>
  <NuxtLink
    class="petehub-logo"
    :class="`petehub-logo--${size}`"
    :to="to"
    :aria-label="ariaLabel"
  >
    <span>Pete</span><strong>hub</strong>
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
  ariaLabel: 'Petehub home'
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

.petehub-logo--home { font-size: clamp(34px, 5vw, 62px); }
.petehub-logo--compact { font-size: 25px; }

.petehub-logo strong {
  margin-left: 5px;
  border-radius: 7px;
  padding: 1px 9px 5px;
  color: #111;
  background: #ff9900;
}
</style>
