<template>
  <section class="research-table">
    <header><h2>{{ title }}</h2><span>{{ rows.length }} rows</span></header>
    <div><table><thead><tr><th v-for="column in columns" :key="column">{{ label(column) }}</th></tr></thead><tbody><tr v-for="(row, index) in rows" :key="index"><td v-for="column in columns" :key="column">{{ display(row[column], column) }}</td></tr></tbody></table></div>
  </section>
</template>
<script setup lang="ts">
defineProps<{ title: string; columns: string[]; rows: Array<Record<string, unknown>> }>()
function label(value: string) { return value.replaceAll('_pct', '%').replaceAll('_', ' ') }
function display(value: unknown, column: string) { if (value === null || value === undefined) return '—'; if (typeof value === 'number') { if (column.includes('pct')) return `${value.toFixed(1)}%`; if (['avg','obp','slg','woba','reliability','start_probability'].includes(column)) return value.toFixed(3).replace(/^0/, ''); return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2) } return String(value) }
</script>
<style scoped>
.research-table { margin-top: 16px; border: 1px solid var(--color-border); background: var(--color-surface); }
header { display: flex; justify-content: space-between; align-items: center; padding: 13px 16px; border-bottom: 1px solid var(--color-border); }
h2 { margin: 0; color: var(--color-foreground); font-size: 18px; } header span { color: var(--color-muted-text); font-size: 12px; }
.research-table > div { overflow-x: auto; } table { width: 100%; border-collapse: collapse; } th, td { padding: 10px 12px; border-bottom: 1px solid var(--color-border); text-align: right; white-space: nowrap; } th:first-child, td:first-child { text-align: left; } th { color: var(--color-muted-text); background: var(--color-plot-bg); font-size: 10px; text-transform: uppercase; } td { color: var(--color-text); font-size: 13px; }
</style>
