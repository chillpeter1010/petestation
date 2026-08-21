<template>
  <section class="bar-list">
    <header v-if="title">
      <h2>{{ title }}</h2>
    </header>
    <div v-if="items.length" class="bars">
      <div v-for="item in normalizedItems" :key="item.label" class="bar-row">
        <div class="bar-label">
          <span>{{ item.label }}</span>
          <strong>{{ formatValue(item.value) }}</strong>
        </div>
        <div class="track">
          <div class="fill" :style="{ width: `${item.width}%` }" />
        </div>
      </div>
    </div>
    <p v-else class="empty">No chart data available for the current filters.</p>
  </section>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  title?: string
  items: Array<Record<string, unknown>>
  labelKey?: string
  valueKey?: string
}>(), {
  title: '',
  labelKey: 'pitch',
  valueKey: 'count'
})

const normalizedItems = computed(() => {
  const rawItems = props.items.map((item) => ({
    label: String(item[props.labelKey] ?? item.Pitch ?? item.pitch_name ?? '-'),
    value: Number(item[props.valueKey] ?? item.pitches ?? item.count ?? 0)
  }))
  const maxValue = Math.max(...rawItems.map((item) => item.value), 0)
  return rawItems.map((item) => ({
    ...item,
    width: maxValue > 0 ? Math.max(3, item.value / maxValue * 100) : 0
  }))
})

function formatValue(value: number) {
  return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(1)
}
</script>

<style scoped>
.bar-list {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 13px 14px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

header h2 {
  margin: 0 0 12px;
  color: var(--color-foreground);
  font-size: 15px;
}

.bars {
  display: grid;
  gap: 10px;
}

.bar-label {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 4px;
  color: var(--color-text);
  font-size: 12px;
}

.bar-label strong {
  color: #1f2937;
  font-family: "Fira Code", "Consolas", monospace;
}

.track {
  height: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-muted);
}

.fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--color-primary), var(--color-secondary));
}

.empty {
  margin: 0;
  color: var(--color-muted-text);
  font-size: 13px;
}
</style>
