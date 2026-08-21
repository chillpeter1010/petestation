<template>
  <section class="summary-grid">
    <article v-for="metric in metrics" :key="metric.key" class="summary-card">
      <span>{{ metric.label }}</span>
      <strong>{{ formatValue(metric.value) }}</strong>
      <small v-if="metric.unit">{{ metric.unit }}</small>
    </article>
  </section>
</template>

<script setup lang="ts">
import type { MetricItem } from '~/types/api'

defineProps<{
  metrics: MetricItem[]
}>()

function formatValue(value: MetricItem['value']) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'number') {
    if (Math.abs(value) < 1 && value !== 0) {
      return value.toFixed(3)
    }
    if (!Number.isInteger(value)) {
      return value.toFixed(1)
    }
  }
  return String(value)
}
</script>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.summary-card {
  min-height: 86px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 13px 14px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.summary-card span {
  display: block;
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 650;
  line-height: 1.25;
  text-transform: uppercase;
}

.summary-card strong {
  display: block;
  margin-top: 6px;
  color: var(--color-foreground);
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 22px;
  line-height: 1.1;
}

.summary-card small {
  display: block;
  margin-top: 4px;
  color: var(--color-muted-text);
  font-size: 12px;
}
</style>
