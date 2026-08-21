<template>
  <section class="transactions-panel">
    <header class="panel-header">
      <div>
        <span class="eyebrow"><Activity :size="16" /> Roster intelligence</span>
        <h2>Recent transactions</h2>
        <p v-if="payload">MLB Stats API · {{ formatDate(payload.period_start) }}–{{ formatDate(payload.period_end) }} · Updated {{ formatTimestamp(payload.fetched_at) }}</p>
      </div>
      <div class="view-controls">
        <div role="group" aria-label="Transaction view">
          <button type="button" :aria-pressed="viewMode === 'list'" @click="viewMode = 'list'"><List :size="16" /> List</button>
          <button type="button" :aria-pressed="viewMode === 'calendar'" @click="viewMode = 'calendar'"><CalendarDays :size="16" /> Calendar</button>
        </div>
      </div>
    </header>

    <div v-if="loading && !payload" class="empty">Loading official roster moves…</div>
    <div v-else-if="errorMessage && !rows.length" class="empty error">{{ errorMessage }}</div>
    <template v-else>
      <div class="summary">
        <button v-for="item in summary" :key="item.category" type="button" :aria-pressed="activeCategory === item.category" @click="selectCategory(item.category)">
          <strong>{{ item.count }}</strong><span>{{ item.label }}</span>
        </button>
      </div>
      <p v-if="errorMessage && rows.length" class="inline-error" role="alert">{{ errorMessage }}</p>

      <div v-if="viewMode === 'calendar'" class="calendar">
        <div class="calendar-toolbar">
          <button type="button" aria-label="Previous month" @click="moveMonth(-1)"><ChevronLeft :size="18" /></button>
          <strong>{{ monthLabel }}</strong>
          <button type="button" aria-label="Next month" @click="moveMonth(1)"><ChevronRight :size="18" /></button>
        </div>
        <div class="weekdays" aria-hidden="true"><span v-for="day in weekdays" :key="day">{{ day }}</span></div>
        <div class="calendar-grid">
          <button
            v-for="day in calendarDays"
            :key="day.key"
            type="button"
            :disabled="!day.inMonth"
            :class="{ outside: !day.inMonth, selected: selectedDate === day.date, 'has-events': day.rows.length }"
            :aria-label="day.inMonth ? `${day.date}: ${day.rows.length} transactions` : undefined"
            @click="day.inMonth && selectDate(day.date)"
          >
            <span>{{ day.day || '' }}</span>
            <strong v-if="day.rows.length">{{ day.rows.length }}</strong>
            <span v-if="day.rows.length" class="dots" aria-hidden="true">
              <i v-for="category in day.categories" :key="category" :data-category="category" />
            </span>
          </button>
        </div>
        <div class="legend">
          <span v-for="category in legendCategories" :key="category"><i :data-category="category" />{{ category }}</span>
        </div>
        <h3 class="selection">{{ selectedDate ? formatFullDate(selectedDate) : 'Select a date' }} <small>{{ selectedDateRows.length }} moves</small></h3>
      </div>

      <div v-if="visibleRows.length" class="transaction-list">
        <article v-for="row in visibleRows" :key="row.transaction_id">
          <time :datetime="row.date">{{ formatDate(row.date) }}</time>
          <MlbPlayerHeadshot v-if="row.player_id" :player-id="row.player_id" :name="row.player_name" :size="46" :source-width="160" decorative />
          <div v-else class="avatar"><UserRound :size="21" /></div>
          <div class="transaction-copy">
            <span class="category" :data-category="row.category">{{ row.category }}</span>
            <h3>
              <NuxtLink v-if="playerLink(row)" :to="playerLink(row)!">{{ row.player_name }}</NuxtLink>
              <template v-else>{{ row.player_name }}</template>
            </h3>
            <p>{{ row.description }}</p>
          </div>
        </article>
      </div>
      <p v-else class="empty">{{ viewMode === 'calendar' ? 'No transactions on this date.' : 'No matching transactions in this period.' }}</p>

      <button v-if="viewMode === 'list' && filteredRows.length > pageSize" class="more" type="button" @click="expanded = !expanded">
        {{ expanded ? 'Show latest 12' : `Show all ${filteredRows.length}` }}
      </button>
    </template>
  </section>
</template>

<script setup lang="ts">
import { Activity, CalendarDays, ChevronLeft, ChevronRight, List, UserRound } from '@lucide/vue'
import type { TeamRosterPlayer, TeamTransactionRow, TeamTransactionsResponse } from '~/types/api'

interface CalendarDay { key: string; date: string; day: number; inMonth: boolean; rows: TeamTransactionRow[]; categories: string[] }

const props = defineProps<{ teamId: string; year: number; roster: TeamRosterPlayer[] }>()
const api = useApi()
const payload = ref<TeamTransactionsResponse | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const activeCategory = ref('All')
const expanded = ref(false)
const viewMode = ref<'list' | 'calendar'>('list')
const monthCursor = ref(new Date(props.year, 0, 1))
const selectedDate = ref('')
const pageSize = 12
const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const legendCategories = ['Injury', 'DFA', 'Activated', 'Called up', 'Optioned', 'Acquired', 'Departed', 'Roster move']

const rosterById = computed(() => new Map(props.roster.map(player => [player.player_id, player])))
const rosterByName = computed(() => new Map(props.roster.map(player => [normalizeName(player.name), player])))

const rows = computed(() => payload.value?.transactions || [])
const summary = computed(() => [
  { category: 'All', label: 'All moves', count: rows.value.length },
  { category: 'Injury', label: 'Placed on IL', count: countCategory('Injury') },
  { category: 'Activated', label: 'Activated', count: countCategory('Activated') },
  { category: 'Called up', label: 'Called up', count: countCategory('Called up') },
  { category: 'Optioned', label: 'Optioned', count: countCategory('Optioned') }
])
const filteredRows = computed(() => activeCategory.value === 'All' ? rows.value : rows.value.filter(row => row.category === activeCategory.value))
const selectedDateRows = computed(() => filteredRows.value.filter(row => row.date === selectedDate.value))
const visibleRows = computed(() => viewMode.value === 'calendar'
  ? selectedDateRows.value
  : (expanded.value ? filteredRows.value : filteredRows.value.slice(0, pageSize)))
const monthLabel = computed(() => new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' }).format(monthCursor.value))
const calendarDays = computed<CalendarDay[]>(() => {
  const year = monthCursor.value.getFullYear()
  const month = monthCursor.value.getMonth()
  const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  return Array.from({ length: 42 }, (_, index) => {
    const day = index - firstWeekday + 1
    const inMonth = day >= 1 && day <= daysInMonth
    const date = inMonth ? isoDate(year, month, day) : ''
    const dayRows = inMonth ? filteredRows.value.filter(row => row.date === date) : []
    return { key: `${year}-${month}-${index}`, date, day: inMonth ? day : 0, inMonth, rows: dayRows, categories: [...new Set(dayRows.map(row => row.category))].slice(0, 4) }
  })
})

watch(() => props.teamId, () => {
  payload.value = null
  activeCategory.value = 'All'
  expanded.value = false
  selectedDate.value = ''
  void loadTransactions()
}, { immediate: true })

async function loadTransactions() {
  loading.value = true
  errorMessage.value = ''
  try {
    payload.value = await api.teamTransactions({ year: props.year, teamId: props.teamId, days: 60, limit: 100 })
    const warning = payload.value.meta.warnings?.[0]
    if (warning) errorMessage.value = warning
    const latestDate = payload.value.transactions[0]?.date || payload.value.period_end || `${props.year}-01-01`
    selectedDate.value = latestDate
    const [selectedYear, selectedMonth] = latestDate.split('-').map(Number)
    monthCursor.value = new Date(selectedYear, selectedMonth - 1, 1)
  } catch {
    errorMessage.value = 'Official transaction data is temporarily unavailable.'
  } finally {
    loading.value = false
  }
}

function selectCategory(category: string) { activeCategory.value = category; expanded.value = false }
function selectDate(date: string) { selectedDate.value = date }
function moveMonth(offset: number) { monthCursor.value = new Date(monthCursor.value.getFullYear(), monthCursor.value.getMonth() + offset, 1); selectedDate.value = '' }
function countCategory(category: string) { return rows.value.filter(row => row.category === category).length }
function playerLink(row: TeamTransactionRow) {
  const player = (row.player_id ? rosterById.value.get(row.player_id) : undefined)
    || rosterByName.value.get(normalizeName(row.player_name))
  if (!player) return null
  if (player.group === 'Pitcher') {
    return { path: '/pitcher-personal', query: { year: props.year, role: player.role || 'All', team: props.teamId, pitcher_id: player.player_id } }
  }
  if (player.group === 'Batter') {
    return { path: '/batter-personal', query: { year: props.year, team: props.teamId, batter_id: player.player_id } }
  }
  return null
}
function normalizeName(value: string) { return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '') }
function isoDate(year: number, month: number, day: number) { return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}` }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(`${value}T00:00:00`)) : '—' }
function formatTimestamp(value: string | null) { return value ? new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : 'cache' }
function formatFullDate(value: string) { return new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'long', day: 'numeric' }).format(new Date(`${value}T00:00:00`)) }
</script>

<style scoped>
.transactions-panel { border: 1px solid var(--team-panel-border); border-radius: 16px; padding: 22px; background: var(--team-panel-bg); box-shadow: var(--shadow-sm); }
.panel-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 16px; }
.eyebrow { display: inline-flex; align-items: center; gap: 6px; color: var(--team-accent); font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.panel-header h2 { margin: 5px 0 0; color: var(--color-text); font-size: 21px; }
.panel-header p { margin: 5px 0 0; color: var(--color-muted-text); font-size: 10px; }
.view-controls, .view-controls > div { display: flex; align-items: center; gap: 4px; }
.view-controls > div { border: 1px solid var(--team-panel-border); border-radius: 9px; padding: 3px; background: var(--color-background); }
.view-controls button { min-height: 34px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; border: 0; border-radius: 7px; padding: 6px 10px; color: var(--color-muted-text); background: transparent; font-size: 10px; font-weight: 850; cursor: pointer; }
.view-controls button[aria-pressed="true"] { color: #fff; background: var(--team-primary); }
.summary { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; margin-bottom: 14px; }
.summary button { min-height: 66px; display: grid; justify-items: start; border: 1px solid var(--team-panel-border); border-radius: 10px; padding: 10px 12px; color: var(--color-muted-text); background: var(--color-background); cursor: pointer; }
.summary button[aria-pressed="true"] { border-color: var(--team-primary); color: #fff; background: color-mix(in srgb, var(--team-primary) 72%, #111827); }
.summary strong { font: 900 20px "Fira Code", monospace; } .summary span { font-size: 10px; font-weight: 800; }
.inline-error { margin: -3px 0 14px; color: var(--color-destructive); font-size: 10px; }
.calendar { margin-bottom: 14px; border: 1px solid var(--team-panel-border); border-radius: 12px; padding: 14px; background: var(--color-background); }
.calendar-toolbar { display: grid; grid-template-columns: 36px 1fr 36px; align-items: center; margin-bottom: 12px; }
.calendar-toolbar strong { color: var(--color-text); font-size: 16px; text-align: center; }
.calendar-toolbar button { width: 34px; height: 34px; display: grid; place-items: center; border: 1px solid var(--team-panel-border); border-radius: 8px; color: var(--color-text); background: var(--color-surface); cursor: pointer; }
.weekdays, .calendar-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 5px; }
.weekdays { margin-bottom: 5px; } .weekdays span { color: var(--color-muted-text); font-size: 9px; font-weight: 850; text-align: center; text-transform: uppercase; }
.calendar-grid > button { position: relative; min-height: 76px; display: flex; flex-direction: column; align-items: flex-start; border: 1px solid var(--team-panel-border); border-radius: 9px; padding: 8px; color: var(--color-muted-text); background: var(--color-surface); cursor: pointer; }
.calendar-grid > button.has-events { color: var(--color-text); } .calendar-grid > button.selected { border-color: var(--team-primary); box-shadow: inset 0 0 0 1px var(--team-primary); background: color-mix(in srgb, var(--team-primary) 12%, var(--color-surface)); }
.calendar-grid > button.outside { visibility: hidden; }
.calendar-grid > button > strong { position: absolute; top: 7px; right: 8px; color: var(--team-accent); font: 800 10px "Fira Code", monospace; }
.dots { display: flex; flex-wrap: wrap; gap: 4px; margin-top: auto; }
.dots i, .legend i { width: 7px; height: 7px; border-radius: 50%; background: #64748b; }
i[data-category="Injury"], i[data-category="DFA"], i[data-category="Departed"] { background: #e3544d; }
i[data-category="Activated"], i[data-category="Called up"], i[data-category="Acquired"] { background: #4db96a; }
i[data-category="Optioned"] { background: #e59a35; }
.legend { display: flex; flex-wrap: wrap; gap: 10px 14px; margin-top: 11px; color: var(--color-muted-text); font-size: 9px; }
.legend span { display: inline-flex; align-items: center; gap: 5px; }
.selection { display: flex; justify-content: space-between; gap: 12px; margin: 14px 0 0; border-top: 1px solid var(--team-panel-border); padding-top: 13px; color: var(--color-text); font-size: 15px; }
.selection small { color: var(--color-muted-text); font: 700 10px "Fira Code", monospace; }
.transaction-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.transaction-list article { position: relative; min-width: 0; display: grid; grid-template-columns: 46px minmax(0, 1fr); gap: 11px; border: 1px solid var(--team-panel-border); border-radius: 11px; padding: 12px; background: var(--color-surface); }
.transaction-list time { position: absolute; top: 11px; right: 12px; color: var(--color-muted-text); font: 700 9px "Fira Code", monospace; }
.avatar { width: 46px; height: 46px; display: grid; place-items: center; border-radius: 50%; color: var(--color-muted-text); background: var(--color-muted); }
.category { display: inline-flex; border-radius: 999px; padding: 3px 7px; color: #d7e5ff; background: #263755; font-size: 8px; font-weight: 900; text-transform: uppercase; }
.category[data-category="Injury"], .category[data-category="DFA"], .category[data-category="Departed"] { color: #ffd9d5; background: #6b2522; }
.category[data-category="Activated"], .category[data-category="Called up"], .category[data-category="Acquired"] { color: #dff8e2; background: #245b32; }
.category[data-category="Optioned"] { color: #ffe8c5; background: #704817; }
.transaction-copy h3 { margin: 6px 56px 0 0; overflow: hidden; color: var(--color-text); font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.transaction-copy h3 a { color: inherit; font-weight: 850; text-decoration: none; }
.transaction-copy h3 a:hover, .transaction-copy h3 a:focus-visible { color: var(--team-accent); text-decoration: underline; outline: none; }
.transaction-copy p { display: -webkit-box; overflow: hidden; margin: 5px 0 0; color: var(--color-muted-text); font-size: 11px; line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.more { width: 100%; min-height: 40px; margin-top: 10px; border: 1px solid var(--team-panel-border); border-radius: 9px; color: var(--color-text); background: var(--color-background); font-weight: 800; cursor: pointer; }
.empty { margin: 0; padding: 28px 4px; color: var(--color-muted-text); text-align: center; } .error { color: var(--color-destructive); }
@media (max-width: 880px) { .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } .transaction-list { grid-template-columns: 1fr; } }
@media (max-width: 620px) { .panel-header { flex-direction: column; } .calendar-grid > button { min-height: 54px; padding: 6px; } .legend { display: none; } }
</style>
