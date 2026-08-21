<template>
  <section class="fatigue-chart">
    <header class="chart-header">
      <h2>Fatigue By Inning</h2>
      <span>{{ rows.length }} innings</span>
    </header>
    <div v-if="bars.length" class="bars">
      <div v-for="bar in bars" :key="bar.inning" class="bar-row">
        <span class="inning">{{ bar.inning }}</span>
        <div class="track">
          <i :style="{ width: `${bar.score}%`, background: bar.color }" />
        </div>
        <strong>{{ bar.score.toFixed(0) }}</strong>
      </div>
    </div>
    <p v-else class="empty">No fatigue data available for the selected game.</p>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{
  rows: Array<Record<string, unknown>>
}>()

const bars = computed(() => props.rows.flatMap((row) => {
  const inning = Number(row.Inning)
  const score = Number(row['Fatigue Score'])
  if (!Number.isFinite(inning) || !Number.isFinite(score)) {
    return []
  }
  return [{
    inning: `Inning ${inning}`,
    score: Math.max(0, Math.min(100, score)),
    color: score >= 75 ? '#16a34a' : score >= 55 ? '#d97706' : '#dc2626'
  }]
}))
</script>

<style scoped>
.fatigue-chart {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.chart-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}

.chart-header h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

.chart-header span,
.empty {
  color: var(--color-muted-text);
  font-size: 13px;
}

.bars {
  display: grid;
  gap: 10px;
  padding: 14px;
}

.bar-row {
  display: grid;
  grid-template-columns: 74px minmax(0, 1fr) 42px;
  gap: 10px;
  align-items: center;
}

.inning {
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 700;
}

.track {
  height: 14px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.track i {
  display: block;
  height: 100%;
  border-radius: inherit;
}

strong {
  color: var(--color-text);
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 13px;
  text-align: right;
}

.empty {
  margin: 0;
  padding: 16px;
}
</style>
