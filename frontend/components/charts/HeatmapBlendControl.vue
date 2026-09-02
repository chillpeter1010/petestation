<template>
  <section class="heatmap-blend-control">
    <strong>{{ title }}</strong>
    <label>
      <span>Heatmap Blend</span>
      <input v-model.number="blend" type="range" min="0" max="1" step="0.1">
      <b>{{ Math.round(blend * 100) }}%</b>
    </label>
  </section>
</template>

<script setup lang="ts">
const blend = defineModel<number>({ required: true })

withDefaults(defineProps<{ title?: string }>(), {
  title: 'Pitch Location'
})
</script>

<style scoped>
.heatmap-blend-control {
  display: grid;
  grid-template-columns: minmax(150px, .75fr) minmax(360px, 1.25fr);
  align-items: center;
  gap: 24px;
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 13px 16px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.heatmap-blend-control > strong {
  color: var(--color-foreground);
  font-size: 15px;
}

label {
  display: grid;
  grid-template-columns: auto minmax(160px, 1fr) 44px;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

label span,
label b {
  color: var(--color-text);
  font-size: 13px;
  font-weight: 800;
}

label b { text-align: right; }
input { width: 100%; accent-color: var(--color-primary); }

@media (max-width: 760px) {
  .heatmap-blend-control { grid-template-columns: 1fr; gap: 10px; }
  label { grid-template-columns: 1fr 42px; }
  label span { grid-column: 1 / -1; }
}
</style>
