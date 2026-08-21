<template>
  <section class="advantage-panel">
    <header>
      <h2>{{ title }}</h2>
      <p>{{ subtitle }}</p>
    </header>
    <div class="advantage-columns">
      <div>
        <h3>{{ leftTitle }}</h3>
        <p v-if="!leftRows.length" class="empty">No clear edge.</p>
        <article v-for="row in leftRows" :key="`left-${row.Metric}`">
          <strong>{{ row.Metric }}</strong>
          <span>+{{ gapText(row) }} pct</span>
        </article>
      </div>
      <div>
        <h3>{{ rightTitle }}</h3>
        <p v-if="!rightRows.length" class="empty">No clear edge.</p>
        <article v-for="row in rightRows" :key="`right-${row.Metric}`">
          <strong>{{ row.Metric }}</strong>
          <span>+{{ gapText(row) }} pct</span>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  subtitle: string
  leftTitle?: string
  rightTitle?: string
  leftRows: Record<string, unknown>[]
  rightRows: Record<string, unknown>[]
}>(), {
  leftTitle: 'Left Edge',
  rightTitle: 'Right Edge'
})

function gapText(row: Record<string, unknown>) {
  return Math.abs(Number(row['Pctl Gap'] || 0)).toFixed(1)
}
</script>

<style scoped>
.advantage-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.advantage-panel header {
  margin-bottom: 14px;
}

.advantage-panel h2,
.advantage-panel h3,
.advantage-panel p {
  margin: 0;
}

.advantage-panel h2 {
  color: var(--color-foreground);
  font-size: 15px;
}

.advantage-panel p,
.empty {
  color: var(--color-muted-text);
  font-size: 13px;
}

.advantage-columns {
  display: grid;
  gap: 12px;
}

.advantage-columns h3 {
  margin-bottom: 8px;
  color: var(--color-primary);
  font-size: 12px;
  text-transform: uppercase;
}

.advantage-columns article {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid var(--color-border);
  padding: 9px 0;
  color: var(--color-text);
}

.advantage-columns article strong,
.advantage-columns article span {
  font-size: 13px;
}

.advantage-columns article span {
  color: var(--color-primary);
  font-weight: 900;
}
</style>
