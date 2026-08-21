<template>
  <section class="data-table-wrap">
    <header v-if="title" class="table-header">
      <h2>{{ title }}</h2>
      <span>{{ rows.length.toLocaleString() }} rows</span>
    </header>
    <div v-if="rows.length" class="table-scroll">
      <table>
        <thead>
          <tr>
            <th v-for="column in visibleColumns" :key="column.key">
              <button
                type="button"
                class="sort-button"
                :class="{ active: sortKey === column.key }"
                @click="toggleSort(column.key)"
              >
                <span>{{ column.label }}</span>
                <b aria-hidden="true">{{ sortIndicator(column.key) }}</b>
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, rowIndex) in limitedRows" :key="rowIndex">
            <td v-for="column in visibleColumns" :key="column.key" :style="cellStyle(row, column)">
              <NuxtLink
                v-if="column.key === linkColumn && getRowLink(row)"
                class="table-link"
                :to="getRowLink(row)"
              >
                {{ formatCell(getCell(row, column.key)) }}
              </NuxtLink>
              <template v-else>
                {{ formatCell(getCell(row, column.key)) }}
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="empty">No rows available for the current filters.</p>
  </section>
</template>

<script setup lang="ts">
import type { TablePayload } from '~/types/api'

const props = withDefaults(defineProps<{
  title?: string
  table?: TablePayload
  maxRows?: number
  linkColumn?: string
  linkTo?: (row: Record<string, unknown>) => string | Record<string, unknown> | undefined
}>(), {
  title: '',
  table: undefined,
  maxRows: 12,
  linkColumn: '',
  linkTo: undefined
})

const rows = computed(() => props.table?.rows || [])
const sortKey = ref('')
const sortDirection = ref<'asc' | 'desc'>('desc')

const visibleColumns = computed(() => {
  const columns = props.table?.columns || []
  return columns.map((column) => ({
    key: String(column.key),
    label: String(column.label || column.key)
  }))
})

const sortedRows = computed(() => {
  if (!sortKey.value) {
    return rows.value
  }
  return rows.value.slice().sort((left, right) => {
    const leftValue = getSortableValue(left, sortKey.value)
    const rightValue = getSortableValue(right, sortKey.value)
    const direction = sortDirection.value === 'asc' ? 1 : -1
    if (typeof leftValue === 'number' && typeof rightValue === 'number') {
      return (leftValue - rightValue) * direction
    }
    return String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true }) * direction
  })
})

const limitedRows = computed(() => sortedRows.value.slice(0, props.maxRows))

function getCell(row: Record<string, unknown>, key: string) {
  return row[key]
}

function getRowLink(row: Record<string, unknown>) {
  return props.linkTo ? props.linkTo(row) : undefined
}

function formatCell(value: unknown) {
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

function toggleSort(key: string) {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortKey.value = key
  sortDirection.value = 'desc'
}

function sortIndicator(key: string) {
  if (sortKey.value !== key) {
    return '-'
  }
  return sortDirection.value === 'asc' ? '^' : 'v'
}

function getSortableValue(row: Record<string, unknown>, key: string) {
  const value = getCell(row, key)
  const numberValue = toNumber(value)
  return Number.isFinite(numberValue) ? numberValue : formatCell(value)
}

function toNumber(value: unknown) {
  if (typeof value === 'number') {
    return value
  }
  if (typeof value === 'string') {
    const cleaned = value.replaceAll(',', '').replace('%', '').trim()
    if (!cleaned || cleaned === '-') {
      return Number.NaN
    }
    return Number(cleaned)
  }
  return Number.NaN
}

function cellStyle(row: Record<string, unknown>, column: { key: string; label: string }) {
  const key = column.key
  if (key === props.linkColumn || /name|id|team|date|role/i.test(key)) {
    return {}
  }
  const value = toNumber(getCell(row, key))
  if (!Number.isFinite(value)) {
    return {}
  }
  if (isPercentileColumn(column, value)) {
    const color = percentileColor(value)
    if (!color) {
      return {}
    }
    return {
      background: color.background,
      boxShadow: color.boxShadow
    }
  }
  return {}
}

function isPercentileColumn(column: { key: string; label: string }, value: number) {
  if (value < 1 || value > 99) {
    return false
  }
  const text = `${column.key} ${column.label}`.toLowerCase()
  return /\bpr\b|percentile|pctile|pct_rank|percentile_rank/.test(text)
}

function percentileColor(value: number) {
  const pr = Math.max(1, Math.min(99, value))
  if (Math.abs(pr - 50) <= 1) {
    return null
  }

  const stops = [
    { value: 1, color: [19, 55, 103], alpha: 0.78 },
    { value: 25, color: [126, 181, 220], alpha: 0.42 },
    { value: 50, color: [0, 0, 0], alpha: 0 },
    { value: 75, color: [238, 161, 155], alpha: 0.42 },
    { value: 99, color: [178, 42, 45], alpha: 0.78 }
  ]

  const upperIndex = stops.findIndex((stop) => pr <= stop.value)
  const upper = stops[Math.max(1, upperIndex)]
  const lower = stops[Math.max(0, upperIndex - 1)]
  const span = upper.value - lower.value || 1
  const ratio = (pr - lower.value) / span
  const color = lower.color.map((channel, index) => Math.round(channel + (upper.color[index] - channel) * ratio))
  const alpha = lower.alpha + (upper.alpha - lower.alpha) * ratio
  const rgb = color.join(', ')

  return {
    background: `rgba(${rgb}, ${alpha.toFixed(3)})`,
    boxShadow: `inset 0 0 0 9999px rgba(${rgb}, ${Math.max(0, alpha - 0.18).toFixed(3)})`
  }
}
</script>

<style scoped>
.data-table-wrap {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.table-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}

.table-header h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
  letter-spacing: 0;
}

.table-header span,
.empty {
  color: var(--color-muted-text);
  font-size: 13px;
}

.table-scroll {
  max-height: 520px;
  overflow-x: auto;
  overflow-y: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th,
td {
  padding: 8px 11px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  white-space: nowrap;
}

th {
  position: sticky;
  top: 0;
  z-index: 1;
  color: var(--color-foreground);
  background: var(--color-muted);
  font-weight: 650;
}

.sort-button {
  display: inline-flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 0;
  padding: 0;
  color: inherit;
  background: transparent;
  font: inherit;
  font-weight: 800;
  text-align: left;
  cursor: pointer;
}

.sort-button b {
  color: var(--color-muted-text);
  font-size: 10px;
}

.sort-button.active b {
  color: var(--color-primary);
}

td {
  color: var(--color-text);
}

.table-link {
  color: var(--color-foreground);
  font-weight: 850;
  text-decoration: none;
}

.table-link:hover {
  text-decoration: underline;
}

tbody tr:hover td {
  background: color-mix(in srgb, var(--color-muted) 62%, transparent);
}

tbody tr:last-child td {
  border-bottom: 0;
}

.empty {
  margin: 0;
  padding: 18px 14px;
}
</style>
