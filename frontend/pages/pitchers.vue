<template>
  <main class="petehub-home">
    <header class="top-bar">
      <NuxtLink class="brand-lockup" to="/" aria-label="Petehub home">
        <span>Pete</span><strong>hub</strong>
      </NuxtLink>
      <nav class="top-nav" aria-label="Primary">
        <NuxtLink to="/">Home</NuxtLink>
        <NuxtLink to="/comparison">Comparison</NuxtLink>
        <NuxtLink to="/rotation">Rotation</NuxtLink>
        <NuxtLink to="/lab">Lab</NuxtLink>
        <NuxtLink to="/leaderboards">Leaderboards</NuxtLink>
        <NuxtLink to="/games">Games</NuxtLink>
      </nav>
    </header>

    <section class="home-hero">
      <span class="eyebrow">2026 Baseball Search</span>
      <p>
        Search players, open team rosters, and jump into analysis without losing context.
      </p>
    </section>

    <section class="search-panel">
      <div class="search-heading">
        <div>
          <h2>Search Petehub</h2>
          <p>{{ allPitchers.length.toLocaleString() }} pitchers indexed for {{ year }}.</p>
        </div>
        <div class="search-controls">
          <label>
            Team
            <select v-model="selectedTeam" aria-label="Team shortcut">
              <option value="">All</option>
              <option v-for="team in teamOptions" :key="team" :value="team">{{ team }}</option>
            </select>
          </label>
          <label>
            Role
            <select v-model="selectedRole" aria-label="Role filter">
              <option value="All">All</option>
              <option value="SP">SP</option>
              <option value="RP">RP</option>
            </select>
          </label>
        </div>
      </div>

      <label class="search-box">
        <span>Search Player</span>
        <input v-model.trim="searchText" type="search" placeholder="Aaron Civale, ATH, SP..." autofocus>
      </label>

      <div class="result-list">
        <NuxtLink
          v-for="pitcher in visiblePitchers"
          :key="`${pitcher.role}-${pitcher.value}`"
          class="result-row"
          :to="playerLink(pitcher)"
        >
          <span>
            <strong>{{ pitcher.name }}</strong>
            <small>{{ pitcher.team }} - {{ pitcher.role }}</small>
          </span>
          <span class="row-meta">{{ appearanceMeta(pitcher) }}</span>
        </NuxtLink>
        <p v-if="!visiblePitchers.length" class="empty-state">No matching players.</p>
      </div>
    </section>

    <section class="portal-grid">
      <NuxtLink class="portal-card link-card" to="/leaderboards">
        <div>
          <h2>Leaderboards</h2>
          <p>Rank pitchers by stuff, discipline, usage, and run value.</p>
        </div>
        <span>Open</span>
      </NuxtLink>

      <NuxtLink class="portal-card link-card" to="/games">
        <div>
          <h2>Today's Games</h2>
          <p>Browse games, open pitching lines, and jump into outing reports.</p>
        </div>
        <span>Open</span>
      </NuxtLink>

      <NuxtLink class="portal-card link-card" to="/comparison">
        <div>
          <h2>Comparison</h2>
          <p>Compare two pitchers or prepare period-based player splits.</p>
        </div>
        <span>Open</span>
      </NuxtLink>

      <NuxtLink class="portal-card link-card" to="/rotation">
        <div>
          <h2>Rotation</h2>
          <p>Open starter rotation and bullpen role workflows.</p>
        </div>
        <span>Open</span>
      </NuxtLink>

      <NuxtLink class="portal-card link-card shortcut-card" to="/lab">
        <div>
          <h2>Lab</h2>
          <p>Prototype fatigue, stuff, and location models before they graduate into product pages.</p>
        </div>
        <span>Open</span>
      </NuxtLink>
    </section>

  </main>
</template>

<script setup lang="ts">
import type { PitcherOption } from '~/types/api'

const api = useApi()
const year = 2026
const searchText = ref('')
const selectedRole = ref<'All' | 'SP' | 'RP'>('All')
const selectedTeam = ref('')

const { data: starters } = await useAsyncData('home-sp-pitchers', () => api.pitchers({ year, role: 'SP' }), { default: () => [] })
const { data: relievers } = await useAsyncData('home-rp-pitchers', () => api.pitchers({ year, role: 'RP' }), { default: () => [] })

const allPitchers = computed<PitcherOption[]>(() => {
  const seen = new Set<string>()
  return [...starters.value, ...relievers.value]
    .filter((pitcher) => {
      const key = `${pitcher.role}-${pitcher.value}`
      if (seen.has(key)) {
        return false
      }
      seen.add(key)
      return true
    })
    .sort((a, b) => a.name.localeCompare(b.name))
})

const filteredPitchers = computed(() => {
  const query = searchText.value.toLowerCase()
  return allPitchers.value.filter((pitcher) => {
    const roleMatch = selectedRole.value === 'All' || pitcher.role === selectedRole.value
    const teamMatch = !selectedTeam.value || pitcher.team === selectedTeam.value
    const queryMatch = !query || [pitcher.name, pitcher.team, pitcher.role].some((value) => String(value).toLowerCase().includes(query))
    return roleMatch && teamMatch && queryMatch
  })
})

const visiblePitchers = computed(() => filteredPitchers.value.slice(0, 8))
const teamOptions = computed(() => [...new Set(allPitchers.value.map((pitcher) => pitcher.team).filter(Boolean))].sort())

function playerLink(pitcher: PitcherOption) {
  return {
    path: '/pitcher-personal',
    query: {
      year,
      role: pitcher.role,
      team: pitcher.team,
      pitcher_id: pitcher.value
    }
  }
}

function appearanceMeta(pitcher: PitcherOption) {
  const gs = Number(pitcher.starts || 0)
  const gr = Number(pitcher.relief_games || 0)
  const games = Number(pitcher.games || 0)
  if (pitcher.role === 'RP') {
    return `${games || gr} G`
  }
  if (gs && gr) {
    return `${gs} GS / ${gr} GR`
  }
  if (gs) {
    return `${gs} GS`
  }
  if (games) {
    return `${games} G`
  }
  return `${gr} GR`
}

</script>

<style>
.petehub-home {
  --hub-orange: #ff9900;
  --hub-orange-dark: #d47c00;
  --hub-panel: #171717;
  --hub-panel-soft: #222222;
  --hub-line: #343434;
  --hub-text: #f5f5f5;
  --hub-muted: #a7a7a7;
  min-height: 100vh;
  margin: 0;
  padding: 26px clamp(18px, 4vw, 52px) 56px;
  color: var(--hub-text);
  background:
    radial-gradient(circle at top right, rgba(255, 153, 0, 0.22), transparent 32rem),
    linear-gradient(180deg, #111111 0%, #050505 100%);
}

.petehub-home .top-bar,
.petehub-home .home-hero,
.petehub-home .search-panel,
.petehub-home .portal-grid {
  max-width: 1320px;
  margin-inline: auto;
}

.petehub-home .top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 36px;
}

.petehub-home .brand-lockup {
  display: inline-flex;
  align-items: center;
  color: var(--hub-text);
  font-size: clamp(30px, 4vw, 48px);
  font-weight: 900;
  letter-spacing: -1px;
  text-decoration: none;
}

.petehub-home .brand-lockup strong {
  margin-left: 4px;
  border-radius: 6px;
  padding: 1px 8px 4px;
  color: #111111;
  background: var(--hub-orange);
}

.petehub-home .top-nav {
  display: flex;
  gap: 10px;
}

.petehub-home .top-nav a {
  border: 1px solid var(--hub-line);
  border-radius: 999px;
  padding: 8px 13px;
  color: var(--hub-muted);
  background: rgba(255, 255, 255, 0.03);
  font-weight: 800;
  text-decoration: none;
}

.petehub-home .top-nav a:hover {
  color: var(--hub-text);
  border-color: var(--hub-orange);
}

.petehub-home .home-hero {
  margin-bottom: 18px;
  padding: 10px 0;
  animation: petehub-fade-up 420ms ease-out both;
}

.petehub-home .eyebrow {
  color: var(--hub-orange);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.petehub-home h2,
.petehub-home p {
  margin: 0;
}

.petehub-home .home-hero p,
.petehub-home .search-heading p,
.petehub-home .portal-card p {
  margin-top: 8px;
  color: var(--hub-muted);
}

.petehub-home .search-panel,
.petehub-home .portal-card {
  border: 1px solid var(--hub-line);
  border-radius: 8px;
  background: rgba(23, 23, 23, 0.96);
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.34);
}

.petehub-home .search-panel {
  display: grid;
  gap: 14px;
  padding: 18px;
  animation: petehub-fade-up 520ms 80ms ease-out both;
}

.petehub-home .search-heading {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 14px;
}

.petehub-home .search-controls {
  display: flex;
  align-items: end;
  justify-content: flex-end;
  gap: 10px;
}

.petehub-home .search-controls label {
  display: grid;
  gap: 6px;
  color: var(--hub-muted);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.petehub-home .search-controls select {
  min-width: 92px;
}

.petehub-home h2 {
  color: var(--hub-text);
  font-size: 18px;
}

.petehub-home select,
.petehub-home input {
  border: 1px solid var(--hub-line);
  border-radius: 6px;
  background: #0d0d0d;
  color: var(--hub-text);
}

.petehub-home select {
  min-height: 38px;
  padding: 8px 10px;
  font-weight: 700;
}

.petehub-home .search-box,
.petehub-home .team-select {
  display: grid;
  gap: 7px;
  color: var(--hub-muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.petehub-home .search-box input {
  width: 100%;
  min-height: 50px;
  border-color: var(--hub-orange-dark);
  padding: 10px 13px;
  font-size: 16px;
  text-transform: none;
}

.petehub-home .result-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.petehub-home .result-row,
.petehub-home .link-card {
  color: inherit;
  text-decoration: none;
}

.petehub-home .result-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid var(--hub-line);
  border-radius: 6px;
  padding: 11px 12px;
  background: var(--hub-panel-soft);
  transition: transform 140ms ease, border-color 140ms ease, background-color 140ms ease;
}

.petehub-home .result-row:hover,
.petehub-home .link-card:hover {
  border-color: var(--hub-orange);
  background: #262626;
}

.petehub-home .result-row:hover {
  transform: translateY(-2px);
}

.petehub-home .result-row strong {
  display: block;
  color: var(--hub-text);
  font-size: 14px;
}

.petehub-home .result-row small,
.petehub-home .row-meta {
  color: var(--hub-muted);
  font-size: 12px;
}

.petehub-home .row-meta {
  white-space: nowrap;
}

.petehub-home .empty-state {
  grid-column: 1 / -1;
  color: var(--hub-muted);
}

.petehub-home .portal-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.petehub-home .portal-card {
  min-height: 180px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 18px;
  padding: 18px;
  animation: petehub-fade-up 560ms 140ms ease-out both;
  transition: transform 140ms ease, border-color 140ms ease, background-color 140ms ease;
}

.petehub-home .portal-card:hover {
  transform: translateY(-2px);
}

.petehub-home .shortcut-card {
  border-color: color-mix(in srgb, var(--hub-orange) 72%, var(--hub-line));
  background:
    linear-gradient(135deg, rgba(255, 153, 0, 0.14), transparent 58%),
    rgba(23, 23, 23, 0.96);
}

.petehub-home .link-card span,
.petehub-home .badge {
  width: fit-content;
  border: 1px solid var(--hub-orange);
  border-radius: 999px;
  padding: 5px 10px;
  color: #111111;
  background: var(--hub-orange);
  font-size: 12px;
  font-weight: 800;
}

.petehub-home .team-select select {
  width: 100%;
  min-height: 44px;
  padding: 9px 10px;
}

@media (max-width: 1120px) {
  .petehub-home .result-list,
  .petehub-home .portal-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .petehub-home .top-bar,
  .petehub-home .search-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .petehub-home .result-list,
  .petehub-home .portal-grid {
    grid-template-columns: 1fr;
  }
}

@keyframes petehub-fade-up {
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .petehub-home .home-hero,
  .petehub-home .search-panel,
  .petehub-home .portal-card {
    animation: none;
  }

  .petehub-home .result-row,
  .petehub-home .portal-card {
    transition: none;
  }
}
</style>
