<template>
  <main class="batter-hub">
    <section class="hub-hero">
      <div>
        <span>Batter station · {{ year }}</span>
        <h1>Find a hitter.<br>Choose the right lens.</h1>
        <p>Search the league, open a player report, or move into production and pitch-quality research.</p>
      </div>
      <div class="hero-stat"><strong>{{ batters.length }}</strong><span>hitters indexed</span></div>
    </section>

    <section class="search-panel" aria-label="Batter search">
      <header>
        <div><span>Player search</span><h2>Open batter analysis</h2></div>
        <div class="player-controls">
          <label>Team<select v-model="team"><option value="All">All teams</option><option v-for="option in teams" :key="option" :value="option">{{ option }}</option></select></label>
          <label>Full roster<select v-model="selectedBatterId" @change="openSelectedBatter"><option value="">Choose player ({{ teamBatters.length }})</option><option v-for="batter in teamBatters" :key="batter.value" :value="String(batter.value)">{{ batter.name }} · {{ batter.plate_appearances }} PA</option></select></label>
        </div>
      </header>
      <label class="search-box"><Search :size="18" aria-hidden="true" /><input v-model.trim="query" type="search" placeholder="Search hitter or team" /></label>
      <div class="results">
        <NuxtLink v-for="batter in visibleBatters" :key="batter.value" :to="playerLink(batter)"><span><strong>{{ batter.name }}</strong><small>{{ batter.team }}</small></span><span>{{ batter.plate_appearances }} PA</span></NuxtLink>
        <p v-if="!visibleBatters.length">No matching hitters.</p>
      </div>
    </section>

    <section class="portal-grid" aria-label="Batter station destinations">
      <NuxtLink class="portal-card" to="/batters/leaderboard"><span>Production</span><h2>Leaderboards</h2><p>Rank hitters through production, contact quality, and plate discipline views.</p><strong>Open leaderboard</strong></NuxtLink>
      <NuxtLink class="portal-card comparison" to="/batters/comparison"><span>Comparison</span><h2>Batter Comparison</h2><p>Compare periods, study team batting roles, and open lineup research scenarios.</p><strong>Open comparison</strong></NuxtLink>
      <NuxtLink class="portal-card lab" to="/batters/lab"><span>Research</span><h2>Batter Lab</h2><p>Study how hitters attack pitch quality, location, and specific arsenal shapes.</p><strong>Open lab</strong></NuxtLink>
    </section>

  </main>
</template>

<script setup lang="ts">
import { Search } from '@lucide/vue'
import type { BatterOption } from '~/types/api'

const api = useApi()
const year = 2026
const query = ref('')
const team = ref('All')
const selectedBatterId = ref('')
const { data: batters } = await useAsyncData('batter-station-options', () => api.batters({ year }), { default: () => [] })
const teams = computed(() => Array.from(new Set(batters.value.map(row => row.team).filter(value => value && value !== '-'))).sort())
const teamBatters = computed(() => batters.value.filter(row => team.value === 'All' || row.team === team.value))
const visibleBatters = computed(() => {
  const needle = query.value.toLowerCase()
  return batters.value.filter(row => (team.value === 'All' || row.team === team.value) && (!needle || `${row.name} ${row.team}`.toLowerCase().includes(needle))).slice(0, 8)
})
function playerLink(batter: BatterOption) { return { path: '/batter-personal', query: { year, team: batter.team, batter_id: batter.value } } }
const router = useRouter()
watch(team, () => { selectedBatterId.value = '' })
function openSelectedBatter() {
  const batter = teamBatters.value.find(row => String(row.value) === selectedBatterId.value)
  if (batter) router.push(playerLink(batter))
}
</script>

<style scoped>
.batter-hub { max-width: 1280px; min-height: 100vh; margin: 0 auto; padding: 92px clamp(16px, 3vw, 38px) 64px; color: var(--color-text); }
.hub-hero, .search-panel, .portal-card { border: 1px solid var(--color-border); background: var(--color-surface); box-shadow: var(--shadow-sm); }
.hub-hero { display: flex; align-items: end; justify-content: space-between; gap: 32px; border-radius: 20px; padding: clamp(24px, 4vw, 46px); background: radial-gradient(circle at top right, color-mix(in srgb, var(--color-primary) 23%, transparent), transparent 34%), var(--color-surface); }
.hub-hero span, .search-panel header span, .portal-card > span { color: var(--color-primary); font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
.hub-hero h1 { margin: 10px 0 0; color: var(--color-foreground); font-size: clamp(38px, 5vw, 62px); font-weight: 750; line-height: 1.06; letter-spacing: -.012em; }
.hub-hero p, .portal-card p { max-width: 680px; color: var(--color-muted-text); line-height: 1.65; }
.hero-stat { min-width: 148px; border-left: 1px solid var(--color-border); padding-left: 24px; }
.hero-stat strong { display: block; color: var(--color-foreground); font-size: 42px; }
.hero-stat span { color: var(--color-muted-text); }
.search-panel { display: grid; gap: 14px; margin-top: 18px; border-radius: 16px; padding: 18px; }
.search-panel header { display: flex; align-items: end; justify-content: space-between; gap: 20px; }
.player-controls { display: flex; align-items: end; gap: 10px; }
.player-controls label:last-child select { min-width: min(320px, 48vw); }
.search-panel h2 { margin: 4px 0 0; color: var(--color-foreground); }
.search-panel label { display: grid; gap: 5px; color: var(--color-muted-text); font-size: 10px; font-weight: 900; text-transform: uppercase; }
select, input { min-height: 44px; border: 1px solid var(--color-border); border-radius: 9px; padding: 0 12px; color: var(--color-text); background: var(--color-background); font-weight: 700; }
.search-box { position: relative; }
.search-box svg { position: absolute; top: 14px; left: 13px; color: var(--color-muted-text); }
.search-box input { width: 100%; padding-left: 42px; }
.results { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 9px; }
.results a { display: flex; align-items: center; justify-content: space-between; gap: 12px; border: 1px solid var(--color-border); border-radius: 10px; padding: 11px 12px; color: inherit; background: var(--color-background); text-decoration: none; }
.results a:hover { border-color: var(--color-primary); }
.results strong, .results small { display: block; }
.results strong { color: var(--color-foreground); font-size: 13px; }
.results small, .results a > span:last-child, .results p { color: var(--color-muted-text); font-size: 11px; }
.portal-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 14px; }
.portal-card { min-height: 230px; border-radius: 16px; padding: 22px; color: inherit; text-decoration: none; transition: border-color 160ms ease, transform 160ms ease; }
.portal-card.comparison { border-radius: 0; }
.portal-card:hover { border-color: var(--color-primary); transform: translateY(-2px); }
.portal-card.lab { background: linear-gradient(145deg, color-mix(in srgb, var(--color-primary) 13%, transparent), transparent 58%), var(--color-surface); }
.portal-card h2 { margin: 12px 0 0; color: var(--color-foreground); font-size: 26px; }
.portal-card strong { display: inline-flex; margin-top: 20px; border-radius: 999px; padding: 8px 13px; color: var(--color-on-primary); background: var(--color-primary); font-size: 12px; }
@media (max-width: 900px) { .results { grid-template-columns: repeat(2, minmax(0, 1fr)); } .portal-grid { grid-template-columns: 1fr; } }
@media (max-width: 620px) { .batter-hub { padding-top: 28px; } .hub-hero, .search-panel header, .player-controls { align-items: stretch; flex-direction: column; } .player-controls label:last-child select { min-width: 0; width: 100%; } .hero-stat { border-left: 0; border-top: 1px solid var(--color-border); padding: 18px 0 0; } .results { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .portal-card { transition: none; } }
</style>
