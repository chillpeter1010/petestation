<template>
  <section class="standard-comparison">
    <header class="standard-comparison__header">
      <div>
        <h2>Standard Comparison</h2>
        <p>Basic pitch-level and plate-appearance stats for the selected periods.</p>
      </div>
      <span>{{ rows.length }} metrics</span>
    </header>

    <div class="standard-comparison__grid">
      <article v-for="row in rows" :key="String(row.metric)" class="standard-comparison__item">
        <span class="metric">{{ row.metric }}</span>
        <div class="values">
          <strong>{{ row.period_a }}</strong>
          <em>vs</em>
          <strong>{{ row.period_b }}</strong>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { TablePayload } from '~/types/api'

const props = withDefaults(defineProps<{
  table?: TablePayload
}>(), {
  table: undefined
})

const rows = computed(() => props.table?.rows || [])
</script>

<style scoped>
.standard-comparison {
  margin-top: 18px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  overflow: hidden;
}

.standard-comparison__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
}

.standard-comparison h2 {
  margin: 0;
  font-size: 1.05rem;
}

.standard-comparison p,
.standard-comparison__header span {
  margin: 4px 0 0;
  color: var(--muted);
}

.standard-comparison__grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(150px, 1fr));
  gap: 1px;
  background: var(--border);
}

.standard-comparison__item {
  min-width: 0;
  padding: 14px 16px;
  background: var(--surface);
}

.metric {
  display: block;
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
}

.values {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-top: 6px;
}

.values strong {
  color: var(--text);
  font-size: 1.16rem;
}

.values em {
  color: var(--muted);
  font-style: normal;
  font-size: 0.78rem;
}

@media (max-width: 1260px) {
  .standard-comparison__grid {
    grid-template-columns: repeat(4, minmax(140px, 1fr));
  }
}

@media (max-width: 860px) {
  .standard-comparison__grid {
    grid-template-columns: repeat(2, minmax(130px, 1fr));
  }
}
</style>
