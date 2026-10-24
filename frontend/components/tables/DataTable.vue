<template>
  <section class="data-table-wrap">
    <header v-if="title" class="table-header">
      <div class="table-title-group">
        <h2>{{ title }}</h2>
        <slot name="title-extra" />
      </div>
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
          <template v-for="(row, rowIndex) in limitedRows" :key="rowIdentity(row, rowIndex)">
            <tr
              :class="{ 'expandable-row': expandable, 'is-expanded': isExpanded(row, rowIndex) }"
              :tabindex="expandable ? 0 : undefined"
              :aria-expanded="expandable ? isExpanded(row, rowIndex) : undefined"
              @click="toggleRow(row, rowIndex)"
              @keydown.enter.prevent="toggleRow(row, rowIndex)"
              @keydown.space.prevent="toggleRow(row, rowIndex)"
            >
              <td v-for="column in visibleColumns" :key="column.key" :style="cellStyle(row, column)">
                <NuxtLink
                  v-if="column.key === linkColumn && getRowLink(row)"
                  class="table-link"
                  :class="{ 'table-link--with-headshot': column.key === headshotColumn }"
                  :to="getRowLink(row)"
                  @click.stop
                  @keydown.enter.stop
                  @keydown.space.stop
                >
                  <MlbPlayerHeadshot
                    v-if="column.key === headshotColumn"
                    :player-id="headshotPlayerId(row)"
                    :name="formatCell(getCell(row, column.key))"
                    :size="headshotSize"
                    :source-width="160"
                    decorative
                    shape="circle"
                  />
                  <span>{{ formatCell(getCell(row, column.key)) }}</span>
                </NuxtLink>
                <NuxtLink
                  v-else-if="column.key === secondaryLinkColumn && getSecondaryRowLink(row)"
                  class="table-link"
                  :class="{ 'table-link--with-headshot': Boolean(secondaryHeadshotIdKey) }"
                  :to="getSecondaryRowLink(row)"
                  @click.stop
                  @keydown.enter.stop
                  @keydown.space.stop
                >
                  <MlbPlayerHeadshot
                    v-if="secondaryHeadshotIdKey"
                    :player-id="secondaryHeadshotPlayerId(row)"
                    :name="formatCell(getCell(row, column.key))"
                    :size="secondaryHeadshotSize"
                    :source-width="160"
                    decorative
                    shape="circle"
                  />
                  <span>{{ formatCell(getCell(row, column.key)) }}</span>
                </NuxtLink>
                <template v-else>
                  {{ formatCell(getCell(row, column.key)) }}
                </template>
              </td>
            </tr>
            <tr v-if="isExpanded(row, rowIndex)" class="expanded-content-row">
              <td :colspan="visibleColumns.length">
                <slot name="expanded" :row="row" />
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <p v-else class="empty">{{ emptyText }}</p>
  </section>
</template>

<script setup lang="ts">
import type { TablePayload } from '~/types/api'
import { performanceColorStyle } from '~/utils/performanceColor'

const props = withDefaults(defineProps<{
  title?: string
  table?: TablePayload
  maxRows?: number
  linkColumn?: string
  linkTo?: (row: Record<string, unknown>) => string | Record<string, unknown> | undefined
  headshotColumn?: string
  headshotIdKey?: string
  headshotSize?: number
  secondaryLinkColumn?: string
  secondaryLinkTo?: (row: Record<string, unknown>) => string | Record<string, unknown> | undefined
  secondaryHeadshotIdKey?: string
  secondaryHeadshotSize?: number
  cellStyleFor?: (row: Record<string, unknown>, column: { key: string; label: string }) => Record<string, string | number> | undefined
  expandable?: boolean
  rowKey?: string
  emptyText?: string
}>(), {
  title: '',
  table: undefined,
  maxRows: 12,
  linkColumn: '',
  linkTo: undefined,
  headshotColumn: '',
  headshotIdKey: 'player_id',
  headshotSize: 38,
  secondaryLinkColumn: '',
  secondaryLinkTo: undefined,
  secondaryHeadshotIdKey: '',
  secondaryHeadshotSize: 38,
  cellStyleFor: undefined,
  expandable: false,
  rowKey: 'player_id',
  emptyText: 'No rows available for the current filters.'
})

const emit = defineEmits<{
  rowToggle: [row: Record<string, unknown>, expanded: boolean]
}>()

const rows = computed(() => props.table?.rows || [])
const sortKey = ref('')
const sortDirection = ref<'asc' | 'desc'>('desc')
const expandedRowKey = ref<string | null>(null)

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

function rowIdentity(row: Record<string, unknown>, rowIndex: number) {
  return String(row[props.rowKey] ?? rowIndex)
}

function isExpanded(row: Record<string, unknown>, rowIndex: number) {
  return props.expandable && expandedRowKey.value === rowIdentity(row, rowIndex)
}

function toggleRow(row: Record<string, unknown>, rowIndex: number) {
  if (!props.expandable) return
  const key = rowIdentity(row, rowIndex)
  const expanded = expandedRowKey.value !== key
  expandedRowKey.value = expanded ? key : null
  emit('rowToggle', row, expanded)
}

function getRowLink(row: Record<string, unknown>) {
  return props.linkTo ? props.linkTo(row) : undefined
}

function getSecondaryRowLink(row: Record<string, unknown>) {
  return props.secondaryLinkTo ? props.secondaryLinkTo(row) : undefined
}

function headshotPlayerId(row: Record<string, unknown>) {
  const playerId = Number(row[props.headshotIdKey])
  return Number.isInteger(playerId) && playerId > 0 ? playerId : null
}

function secondaryHeadshotPlayerId(row: Record<string, unknown>) {
  const playerId = Number(row[props.secondaryHeadshotIdKey])
  return Number.isInteger(playerId) && playerId > 0 ? playerId : null
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
  const customStyle = props.cellStyleFor?.(row, column)
  if (customStyle) {
    return customStyle
  }
  const key = column.key
  if (key === props.linkColumn || key === props.secondaryLinkColumn || /name|id|team|date|role/i.test(key)) {
    return {}
  }
  const value = toNumber(getCell(row, key))
  if (!Number.isFinite(value)) {
    return {}
  }
  if (isPercentileColumn(column, value)) {
    return performanceColorStyle((value - 50) / 49)
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

.table-title-group {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
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

.table-link--with-headshot {
  display: inline-flex;
  align-items: center;
  gap: 9px;
}

.table-link:hover {
  text-decoration: underline;
}

tbody tr:hover td {
  background: color-mix(in srgb, var(--color-muted) 62%, transparent);
}

.expandable-row {
  cursor: pointer;
}

.expandable-row:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.expandable-row.is-expanded td {
  background: color-mix(in srgb, var(--color-primary) 9%, var(--color-surface));
}

.expanded-content-row td {
  padding: 0;
  white-space: normal;
  background: color-mix(in srgb, var(--color-muted) 35%, var(--color-surface));
}

.expanded-content-row:hover td {
  background: color-mix(in srgb, var(--color-muted) 35%, var(--color-surface));
}

tbody tr:last-child td {
  border-bottom: 0;
}

.empty {
  margin: 0;
  padding: 18px 14px;
}
</style>
