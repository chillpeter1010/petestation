<template>
  <p v-if="error" class="comparison-status error">{{ error }}</p>
  <p v-else-if="pending" class="comparison-status">{{ label }}</p>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  pending: boolean
  error?: string
  label?: string
}>(), {
  error: '',
  label: 'Loading comparison...'
})
</script>

<style scoped>
.comparison-status {
  margin: 16px 0 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px;
  color: var(--color-muted-text);
  background: var(--color-surface);
}

.comparison-status.error {
  color: var(--color-destructive);
}
</style>
