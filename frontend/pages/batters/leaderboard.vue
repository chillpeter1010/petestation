<template>
  <main class="batter-page">
    <BatterStationHero :hitters="leaderboardRows.length" :leaders="heroLeaders" />

    <section class="workspace">
      <header class="workspace__heading">
        <div><span><TableProperties :size="16" aria-hidden="true" /> League leaderboard</span><h2>Find the shape of production</h2></div>
        <p>Switch the lens without carrying a 23-column table across the screen.</p>
      </header>

      <section class="filter-bar" aria-label="Batter leaderboard filters">
        <label><span>Season</span><select v-model.number="year"><option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option></select></label>
        <label><span>Team</span><select v-model="team"><option value="All">All teams</option><option v-for="option in teamOptions" :key="option" :value="option">{{ option }}</option></select></label>
        <label><span>Minimum PA</span><select v-model.number="minimumPa"><option :value="0">No minimum</option><option :value="25">25 PA</option><option :value="50">50 PA</option><option :value="100">100 PA</option><option :value="200">200 PA</option><option :value="300">300 PA</option></select></label>
        <label class="search-field"><span>Player search</span><div><Search :size="17" aria-hidden="true" /><input v-model.trim="searchText" type="search" placeholder="Search hitter or team" /></div></label>
      </section>

      <nav class="view-tabs" aria-label="Leaderboard data view">
        <button v-for="item in views" :key="item.key" type="button" :class="{ active: view === item.key }" @click="view = item.key"><component :is="item.icon" :size="16" aria-hidden="true" /><span><strong>{{ item.label }}</strong><small>{{ item.description }}</small></span></button>
      </nav>

      <div v-if="pending" class="skeleton-table" aria-label="Loading batter leaderboard"><span v-for="item in 8" :key="item" /></div>
      <p v-else-if="error" class="state-card">Unable to load the batter leaderboard.</p>
      <BatterLeaderboardTable v-else :rows="filteredBatters" :view="view" :year="year" />
    </section>
  </main>
</template>

<script setup lang="ts">
import { Crosshair, Search, TableProperties, TrendingUp } from '@lucide/vue'
import type { BatterLeaderboardRow } from '~/types/api'

const api = useApi()
const year = ref(2026)
const team = ref('All')
const minimumPa = ref(100)
const searchText = ref('')
const view = ref<'standard' | 'contact'>('standard')
const yearOptions = [2026, 2025, 2024, 2023, 2022, 2021]
const views = [
  { key: 'standard' as const, label: 'Production & discipline', description: 'Results, walks, strikeouts & whiffs', icon: TrendingUp },
  { key: 'contact' as const, label: 'Contact', description: 'Expected & batted ball', icon: Crosshair }
]

const { data: leaderboardRows, pending, error } = await useAsyncData(
  () => `batter-leaderboard-${year.value}`,
  () => api.batterLeaderboard({ year: year.value }),
  { watch: [year], default: () => [] }
)

watch(year, () => { team.value = 'All'; searchText.value = '' })

const teamOptions = computed(() => Array.from(new Set(leaderboardRows.value.map(row => row.team).filter(value => value && value !== '-'))).sort())
const filteredBatters = computed(() => {
  const needle = searchText.value.toLowerCase()
  return leaderboardRows.value.filter(row => (team.value === 'All' || row.team === team.value) && (row.plate_appearances || 0) >= minimumPa.value && (!needle || `${row.name} ${row.team}`.toLowerCase().includes(needle)))
})

const heroLeaders = computed(() => [
  leaderFor('OPS leader', 'ops', value => formatRate(value)),
  leaderFor('Expected leader', 'xwoba', value => formatRate(value)),
  leaderFor('Home run leader', 'home_runs', value => String(Math.round(value)))
].filter((item): item is NonNullable<typeof item> => Boolean(item)))

function leaderFor(label: string, key: keyof BatterLeaderboardRow, formatter: (value: number) => string) {
  const row = leaderboardRows.value.filter(item => (item.plate_appearances || 0) >= 100 && typeof item[key] === 'number').slice().sort((a, b) => Number(b[key]) - Number(a[key]))[0]
  if (!row) return null
  return { label, name: row.name, team: row.team, value: formatter(Number(row[key])), playerId: row.player_id, to: { path: '/batter-personal', query: { year: year.value, team: row.team, batter_id: row.player_id } } }
}
function formatRate(value: number) { return value.toFixed(3) }
</script>

<style scoped>
.batter-page { min-height: 100vh; padding: 76px clamp(16px, 3vw, 46px) 64px; color: var(--color-text); }
.workspace { display: grid; gap: 16px; margin-top: 24px; }
.workspace__heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; padding: 10px 2px; }
.workspace__heading span { display: inline-flex; align-items: center; gap: 7px; color: var(--color-primary); font-size: 11px; font-weight: 900; letter-spacing: .09em; text-transform: uppercase; }
.workspace__heading h2 { margin: 5px 0 0; color: var(--color-foreground); font-size: clamp(25px, 3vw, 36px); letter-spacing: -.01em; }
.workspace__heading p { max-width: 480px; margin: 0; color: var(--color-muted-text); font-size: 13px; text-align: right; }
.filter-bar { display: grid; grid-template-columns: 140px 180px 170px minmax(240px, 1fr); gap: 12px; border: 1px solid var(--color-border); border-radius: 15px; padding: 14px; background: color-mix(in srgb, var(--color-surface) 95%, transparent); box-shadow: var(--shadow-sm); }
label { display: grid; gap: 6px; }
label > span { color: var(--color-muted-text); font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
select, input { width: 100%; min-height: 44px; border: 1px solid var(--color-border); border-radius: 8px; padding: 0 12px; color: var(--color-text); background: var(--color-background); font-weight: 700; }
.search-field > div { position: relative; }
.search-field svg { position: absolute; top: 13px; left: 12px; color: var(--color-muted-text); pointer-events: none; }
.search-field input { padding-left: 38px; }
.view-tabs { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.view-tabs button { display: flex; align-items: center; gap: 11px; min-height: 62px; border: 1px solid var(--color-border); border-radius: 12px; padding: 10px 15px; color: var(--color-muted-text); background: var(--color-surface); cursor: pointer; text-align: left; transition: border-color 180ms ease, background 180ms ease; }
.view-tabs button > span { display: grid; gap: 2px; }
.view-tabs strong { color: var(--color-foreground); font-size: 17px; }
.view-tabs small { font-size: 14px; }
.view-tabs button.active { border-color: var(--color-primary); color: #111; background: color-mix(in srgb, var(--color-primary) 16%, var(--color-surface)); }
.view-tabs button.active svg { color: var(--color-primary); }
.state-card { margin: 0; border: 1px solid var(--color-border); border-radius: 15px; padding: 32px; color: var(--color-muted-text); background: var(--color-surface); }
.skeleton-table { display: grid; gap: 1px; overflow: hidden; border: 1px solid var(--color-border); border-radius: 16px; background: var(--color-border); }
.skeleton-table span { height: 58px; background: linear-gradient(90deg, var(--color-surface), var(--color-muted), var(--color-surface)); background-size: 200% 100%; animation: shimmer 1.4s infinite; }
@keyframes shimmer { to { background-position: -200% 0; } }
@media (max-width: 850px) { .filter-bar { grid-template-columns: repeat(2, minmax(0, 1fr)); } .search-field { grid-column: 1 / -1; } }
@media (max-width: 640px) { .batter-page { padding-top: 24px; } .workspace__heading { align-items: flex-start; flex-direction: column; } .workspace__heading p { text-align: left; } .filter-bar, .view-tabs { grid-template-columns: 1fr; } .search-field { grid-column: auto; } }
@media (prefers-reduced-motion: reduce) { .view-tabs button { transition: none; } .skeleton-table span { animation: none; } }
</style>
