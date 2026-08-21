<template>
  <section v-if="notes.length" class="comparison-notes">
    <h2>{{ title }}</h2>
    <p v-for="note in notes" :key="note">{{ note }}</p>
  </section>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  notes: string[]
  title?: string
}>(), {
  title: 'Migration Notes'
})
</script>

<style scoped>
.comparison-notes {
  margin-top: 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 18px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.comparison-notes h2 {
  margin: 0 0 8px;
  color: var(--color-foreground);
  font-size: 16px;
}

.comparison-notes p {
  color: var(--color-muted-text);
}
</style>
