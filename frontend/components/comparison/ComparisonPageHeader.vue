<template>
  <header class="comparison-page-header">
    <div>
      <span>{{ eyebrow }}</span>
      <h1>{{ title }}</h1>
      <p>{{ description }}</p>
    </div>
    <nav v-if="backTo || secondaryTo" class="header-actions" aria-label="Page actions">
      <NuxtLink v-if="backTo" :to="backTo">{{ backLabel }}</NuxtLink>
      <NuxtLink v-if="secondaryTo" :to="secondaryTo">{{ secondaryLabel }}</NuxtLink>
    </nav>
  </header>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  eyebrow: string
  title: string
  description: string
  backTo?: string
  backLabel?: string
  secondaryTo?: string
  secondaryLabel?: string
}>(), {
  backTo: '',
  backLabel: 'Back',
  secondaryTo: '',
  secondaryLabel: ''
})
</script>

<style scoped>
.comparison-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 18px 20px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.comparison-page-header span {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.comparison-page-header h1 {
  margin: 6px 0 0;
  color: var(--color-foreground);
  font-size: clamp(30px, 3vw, 42px);
  line-height: 1;
}

.comparison-page-header p {
  margin: 8px 0 0;
  color: var(--color-muted-text);
  line-height: 1.45;
}

.header-actions {
  display: grid;
  gap: 10px;
  justify-items: stretch;
}

.comparison-page-header a {
  display: inline-flex;
  min-width: 130px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border-strong);
  border-radius: 999px;
  padding: 8px 12px;
  color: var(--color-primary);
  font-weight: 850;
  text-decoration: none;
  white-space: nowrap;
}

@media (max-width: 940px) {
  .comparison-page-header {
    flex-direction: column;
  }
}
</style>
