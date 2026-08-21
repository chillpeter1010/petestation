<template>
  <main class="leaderboard-page">
    <ComparisonPageHeader
      eyebrow="Leaderboards"
      title="Pitcher Rankings"
      description="Basic pitcher stats with team and role filters, linked into Pitcher Personal."
      back-to="/"
      back-label="Home"
    />

    <section class="filter-panel">
      <label>
        Year
        <select v-model.number="year">
          <option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <fieldset class="role-filter">
        <legend>Role</legend>
        <div class="role-checkbox-row">
          <label class="checkbox-pill">
            <input v-model="includeStarters" type="checkbox">
            <span>Starter</span>
          </label>
          <label class="checkbox-pill">
            <input v-model="includeRelievers" type="checkbox">
            <span>Reliever</span>
          </label>
        </div>
      </fieldset>
      <label>
        Team
        <select v-model="team">
          <option value="All">All</option>
          <option v-for="option in teamOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <label class="search-label">
        Search
        <input v-model.trim="searchText" type="search" placeholder="Pitcher, team, role...">
      </label>
    </section>

    <p v-if="pending" class="empty-state">Loading pitcher stats...</p>
    <p v-else-if="error" class="empty-state">Could not load pitcher stats.</p>
    <DataTable
      v-else
      class="leaderboard-table"
      title="Pitcher Basic Stats"
      :table="leaderboardTable"
      :max-rows="500"
      link-column="Pitcher"
      :link-to="leaderboardPlayerLink"
    />
  </main>
</template>

<script setup lang="ts">
import type { PitcherLeaderboardRow, TablePayload } from '~/types/api'

const api = useApi()

const year = ref(2026)
const includeStarters = ref(true)
const includeRelievers = ref(true)
const team = ref('All')
const searchText = ref('')
const yearOptions = [2026, 2025, 2024, 2023, 2022, 2021]

const selectedRole = computed<'All' | 'SP' | 'RP'>(() => {
  if (includeStarters.value && includeRelievers.value) {
    return 'All'
  }
  if (includeStarters.value) {
    return 'SP'
  }
  if (includeRelievers.value) {
    return 'RP'
  }
  return 'All'
})

const { data: leaderboardRows, pending, error } = await useAsyncData(
  () => `leaderboard-basic-${year.value}-${selectedRole.value}`,
  () => api.pitcherLeaderboard({ year: year.value, role: selectedRole.value }),
  { watch: [year, selectedRole], default: () => [] }
)

const teamOptions = computed(() => [...new Set(leaderboardRows.value.map((pitcher) => pitcher.team).filter(Boolean))].sort())

const filteredPitchers = computed(() => {
  const query = searchText.value.toLowerCase()
  return leaderboardRows.value.filter((pitcher) => {
    const teamMatch = team.value === 'All' || pitcher.team === team.value
    const queryMatch = !query || [pitcher.name, pitcher.team, pitcher.role].some((value) => String(value).toLowerCase().includes(query))
    return teamMatch && queryMatch
  })
})

const leaderboardTable = computed<TablePayload>(() => ({
  columns: [
    { key: 'Pitcher', label: 'Pitcher' },
    { key: 'Team', label: 'Team' },
    { key: 'Role', label: 'Role' },
    { key: 'G', label: 'G' },
    { key: 'GS', label: 'GS' },
    { key: 'Avg GS', label: 'Avg GS' },
    { key: 'GR', label: 'GR' },
    { key: 'IP', label: 'IP' },
    { key: 'ERA', label: 'ERA' },
    { key: 'WHIP', label: 'WHIP' },
    { key: 'H', label: 'H' },
    { key: 'R', label: 'R' },
    { key: 'ER', label: 'ER' },
    { key: 'BB', label: 'BB' },
    { key: 'SO', label: 'SO' },
    { key: 'HR', label: 'HR' },
    { key: 'NP', label: 'NP' },
    { key: 'K%', label: 'K%' },
    { key: 'BB%', label: 'BB%' }
  ],
  rows: filteredPitchers.value.map((pitcher) => ({
    Pitcher: pitcher.name,
    Team: pitcher.team || '-',
    Role: pitcher.role,
    G: pitcher.games,
    GS: pitcher.starts,
    'Avg GS': formatNumber(pitcher.avg_game_score, 1),
    GR: pitcher.relief_games,
    IP: formatNumber(pitcher.ip, 1),
    ERA: formatNumber(pitcher.era, 2),
    WHIP: formatNumber(pitcher.whip, 3),
    H: formatInteger(pitcher.hits),
    R: formatInteger(pitcher.runs),
    ER: formatInteger(pitcher.earned_runs),
    BB: formatInteger(pitcher.walks),
    SO: formatInteger(pitcher.strikeouts),
    HR: formatInteger(pitcher.home_runs),
    NP: formatInteger(pitcher.pitches),
    'K%': formatPercent(pitcher.strikeout_rate),
    'BB%': formatPercent(pitcher.walk_rate),
    player_id: pitcher.player_id,
    _role: playerRole(pitcher)
  }))
}))

watch([year, selectedRole], () => {
  team.value = 'All'
})

watch([includeStarters, includeRelievers], ([hasStarters, hasRelievers]) => {
  if (!hasStarters && !hasRelievers) {
    includeStarters.value = true
    includeRelievers.value = true
  }
})

function playerRole(pitcher: PitcherLeaderboardRow) {
  if (pitcher.role === 'RP') {
    return 'RP'
  }
  return pitcher.starts > 0 ? 'SP' : 'RP'
}

function leaderboardPlayerLink(row: Record<string, unknown>) {
  const pitcherId = Number(row.player_id)
  if (!Number.isFinite(pitcherId) || pitcherId <= 0) {
    return undefined
  }
  return {
    path: '/pitcher-personal',
    query: {
      year: year.value,
      role: String(row._role || row.Role || 'SP'),
      team: String(row.Team || ''),
      pitcher_id: pitcherId
    }
  }
}

function formatInteger(value: number | null) {
  if (value === null || value === undefined) {
    return '-'
  }
  return Math.round(value).toLocaleString()
}

function formatNumber(value: number | null, digits: number) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-'
  }
  return value.toFixed(digits)
}

function formatPercent(value: number | null) {
  if (value === null || value === undefined) {
    return '-'
  }
  return `${(value * 100).toFixed(1)}%`
}
</script>

<style scoped>
.leaderboard-page {
  max-width: 1320px;
  margin: 0 auto;
  padding: 104px 20px 56px;
}

.filter-panel,
.leaderboard-table {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.filter-panel {
  display: grid;
  grid-template-columns: 150px 230px 180px minmax(260px, 1fr);
  gap: 14px;
  margin-top: 18px;
  padding: 16px;
}

label,
.role-filter {
  display: grid;
  gap: 8px;
  color: var(--color-foreground);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.role-filter {
  border: 0;
  margin: 0;
  padding: 0;
  align-self: end;
}

.role-filter legend {
  padding: 0;
}

.role-checkbox-row {
  display: flex;
  gap: 8px;
  min-width: 0;
}

.checkbox-pill {
  display: flex;
  min-width: 0;
  height: 44px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 12px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text);
  cursor: pointer;
  font-size: 13px;
  font-weight: 900;
  text-transform: none;
}

.checkbox-pill input {
  width: 15px;
  height: 15px;
  min-width: 15px;
  padding: 0;
  accent-color: var(--color-primary);
}

select,
input {
  min-width: 0;
  height: 44px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 0 12px;
  color: var(--color-text);
  background: var(--color-surface);
  font: inherit;
  font-size: 14px;
  font-weight: 800;
  text-transform: none;
}

.leaderboard-table {
  margin-top: 16px;
}

.leaderboard-table header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border);
}

h2 {
  margin: 0;
  color: var(--color-foreground);
}

.leaderboard-table header span,
.empty-state {
  color: var(--color-muted-text);
}

.table-scroll {
  max-height: 680px;
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  padding: 10px 14px;
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
}

td {
  color: var(--color-text);
}

.numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.player-link {
  border: 0;
  padding: 0;
  color: var(--color-primary);
  background: transparent;
  cursor: pointer;
  font-weight: 900;
  font: inherit;
  text-decoration: none;
}

.player-link:hover {
  text-decoration: underline;
}

.empty-state {
  margin: 0;
  padding: 18px 16px;
}

@media (max-width: 860px) {
  .filter-panel {
    grid-template-columns: 1fr;
  }
}
</style>
