<template>
  <section class="leaderboard-shell">
    <header>
      <div>
        <span class="eyebrow"><ListFilter :size="15" aria-hidden="true" /> Ranked results</span>
        <h2>{{ title }}</h2>
      </div>
      <span>{{ sortedRows.length.toLocaleString() }} qualified hitters</span>
    </header>

    <div v-if="sortedRows.length" class="table-scroll">
      <table :class="{ 'table--combined': view === 'standard' }">
        <thead>
          <tr>
            <th class="rank-column">#</th>
            <th class="player-column"><button type="button" @click="sortBy('name')">Player <SortIcon :size="13" /></button></th>
            <th v-for="column in columns" :key="column.key">
              <button type="button" :class="{ active: sortKey === column.key }" @click="sortBy(column.key)">
                {{ column.label }} <SortIcon :size="13" />
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in sortedRows" :key="row.player_id">
            <td class="rank-column">{{ index + 1 }}</td>
            <td class="player-column">
              <NuxtLink :to="playerLink(row)">
                <MlbPlayerHeadshot :player-id="row.player_id" :name="row.name" :size="58" :source-width="160" decorative shape="circle" />
                <span><strong>{{ row.name }}</strong><small>{{ row.team }} · {{ row.plate_appearances ?? 0 }} PA</small></span>
              </NuxtLink>
            </td>
            <td v-for="column in columns" :key="column.key" :class="metricClass(row, column.key)">
              {{ formatMetric(row[column.key], column.format) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="empty">No hitters match the current filters.</p>
  </section>
</template>

<script setup lang="ts">
import { ArrowDownUp as SortIcon, ListFilter } from '@lucide/vue'
import type { BatterLeaderboardRow } from '~/types/api'

type MetricKey = keyof BatterLeaderboardRow
type MetricFormat = 'integer' | 'rate' | 'percent' | 'decimal'

const props = defineProps<{
  rows: BatterLeaderboardRow[]
  view: 'standard' | 'contact'
  year: number
}>()

const sortKey = ref<MetricKey>('ops')
const sortDirection = ref<'asc' | 'desc'>('desc')

const viewConfig: Record<typeof props.view, { title: string; defaultSort: MetricKey; columns: Array<{ key: MetricKey; label: string; format: MetricFormat }> }> = {
  standard: {
    title: 'Production & plate discipline', defaultSort: 'ops',
    columns: [
      { key: 'plate_appearances', label: 'PA', format: 'integer' }, { key: 'games', label: 'G', format: 'integer' },
      { key: 'home_runs', label: 'HR', format: 'integer' },
      { key: 'avg', label: 'AVG', format: 'rate' }, { key: 'obp', label: 'OBP', format: 'rate' },
      { key: 'slg', label: 'SLG', format: 'rate' }, { key: 'ops', label: 'OPS', format: 'rate' },
      { key: 'walks', label: 'BB', format: 'integer' }, { key: 'strikeouts', label: 'SO', format: 'integer' },
      { key: 'walk_rate', label: 'BB%', format: 'percent' }, { key: 'strikeout_rate', label: 'K%', format: 'percent' },
      { key: 'whiff_rate', label: 'Whiff%', format: 'percent' }
    ]
  },
  contact: {
    title: 'Quality of contact', defaultSort: 'xwoba',
    columns: [
      { key: 'woba', label: 'wOBA', format: 'rate' }, { key: 'xwoba', label: 'xwOBA', format: 'rate' },
      { key: 'xba', label: 'xBA', format: 'rate' }, { key: 'xslg', label: 'xSLG', format: 'rate' },
      { key: 'avg_ev', label: 'Avg EV', format: 'decimal' }, { key: 'hard_hit_rate', label: 'HardHit%', format: 'percent' },
      { key: 'barrel_rate', label: 'Barrel%', format: 'percent' }
    ]
  }
}

const config = computed(() => viewConfig[props.view])
const title = computed(() => config.value.title)
const columns = computed(() => config.value.columns)

watch(() => props.view, () => {
  sortKey.value = config.value.defaultSort
  sortDirection.value = 'desc'
})

const sortedRows = computed(() => props.rows.slice().sort((left, right) => {
  const a = left[sortKey.value]
  const b = right[sortKey.value]
  const direction = sortDirection.value === 'asc' ? 1 : -1
  if (typeof a === 'number' && typeof b === 'number') return (a - b) * direction
  if (a === null || a === undefined) return 1
  if (b === null || b === undefined) return -1
  return String(a).localeCompare(String(b)) * direction
}))

function sortBy(key: MetricKey) {
  if (sortKey.value === key) sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  else { sortKey.value = key; sortDirection.value = key === 'name' ? 'asc' : 'desc' }
}

function formatMetric(value: unknown, format: MetricFormat) {
  if (value === null || value === undefined) return '-'
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  if (format === 'percent') return `${(numeric * 100).toFixed(1)}%`
  if (format === 'rate') return numeric.toFixed(3)
  if (format === 'decimal') return numeric.toFixed(1)
  return Math.round(numeric).toLocaleString()
}

function metricClass(row: BatterLeaderboardRow, key: MetricKey) {
  if (key !== sortKey.value) return ''
  return row[key] !== null && row[key] !== undefined ? 'sorted-metric' : ''
}

function playerLink(row: BatterLeaderboardRow) {
  return { path: '/batter-personal', query: { year: props.year, team: row.team, batter_id: row.player_id } }
}
</script>

<style scoped>
.leaderboard-shell { min-width: 0; overflow: hidden; border: 1px solid var(--color-border); border-radius: 18px; background: var(--color-surface); box-shadow: var(--shadow-md); }
.leaderboard-shell > header { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 20px 22px; border-bottom: 1px solid var(--color-border); }
.leaderboard-shell header > span { color: var(--color-muted-text); font-family: inherit; font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; }
.eyebrow { display: inline-flex; align-items: center; gap: 8px; color: var(--color-primary); font-size: 13px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
h2 { margin: 7px 0 0; color: var(--color-foreground); font-size: 28px; }
.table-scroll { max-height: 760px; overflow: auto; }
table { width: 100%; min-width: 1120px; border-collapse: collapse; font-family: inherit; font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums; }
table.table--combined { min-width: 1760px; }
th, td { height: 78px; padding: 10px 18px; border-bottom: 1px solid var(--color-border); text-align: right; white-space: nowrap; }
th { position: sticky; top: 0; z-index: 2; height: 58px; color: var(--color-muted-text); background: color-mix(in srgb, var(--color-surface) 88%, var(--color-muted)); }
th button { display: inline-flex; align-items: center; gap: 7px; border: 0; padding: 10px 0; color: inherit; background: transparent; cursor: pointer; font: inherit; font-size: 12px; font-weight: 900; text-transform: uppercase; }
th button.active { color: var(--color-primary); }
.rank-column { width: 64px; color: var(--color-muted-text); text-align: center; }
.player-column { position: sticky; left: 0; z-index: 1; min-width: 310px; text-align: left; background: var(--color-surface); }
th.player-column { z-index: 3; background: color-mix(in srgb, var(--color-surface) 88%, var(--color-muted)); }
.player-column a { display: flex; align-items: center; gap: 11px; color: var(--color-text); text-decoration: none; }
.player-column span { display: grid; gap: 3px; }
.player-column strong { font-family: "Fira Sans", sans-serif; font-size: 16px; }
.player-column small { color: var(--color-muted-text); font-size: 11px; }
tbody tr:hover td { background: color-mix(in srgb, var(--color-primary) 6%, var(--color-surface)); }
.sorted-metric { color: var(--color-primary); font-weight: 800; }
.empty { margin: 0; padding: 38px; color: var(--color-muted-text); text-align: center; }
@media (max-width: 680px) { .leaderboard-shell > header { align-items: flex-start; padding: 17px; } .leaderboard-shell header > span { max-width: 90px; text-align: right; } th, td { padding-inline: 10px; } .player-column { min-width: 195px; } }
</style>
