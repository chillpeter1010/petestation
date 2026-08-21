<template>
  <section class="team-panel roster-panel">
    <header class="team-panel__header">
      <div>
        <span><Users :size="16" aria-hidden="true" /> Player directory</span>
        <h2>Team roster</h2>
      </div>
      <span class="roster-panel__count">{{ filteredRows.length }} players</span>
    </header>

    <div class="roster-panel__controls">
      <label>
        <Search :size="16" aria-hidden="true" />
        <span class="sr-only">Search team roster</span>
        <input v-model="search" type="search" placeholder="Search this roster" autocomplete="off">
      </label>
      <div role="group" aria-label="Roster group">
        <button v-for="option in filters" :key="option" type="button" :aria-pressed="group === option" @click="group = option">
          {{ option }}
        </button>
      </div>
    </div>

    <div class="roster-grid">
      <NuxtLink v-for="player in filteredRows" :key="`${player.group}-${player.player_id}`" :to="playerLink(player)">
        <MlbPlayerHeadshot :player-id="player.player_id" :name="player.name" :size="42" :source-width="160" decorative />
        <span>
          <strong>{{ player.name }}</strong>
          <small>{{ player.role }} · {{ player.games }} G<span v-if="player.starts"> · {{ player.starts }} GS</span></small>
        </span>
        <ChevronRight :size="16" aria-hidden="true" />
      </NuxtLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ChevronRight, Search, Users } from '@lucide/vue'
import { refDebounced } from '@vueuse/core'
import type { TeamRosterPlayer } from '~/types/api'

const props = defineProps<{ rows: TeamRosterPlayer[]; teamId: string; year: number }>()
const filters = ['All', 'Pitchers', 'Batters'] as const
const search = ref('')
const debouncedSearch = refDebounced(search, 120)
const group = ref<typeof filters[number]>('All')

const filteredRows = computed(() => {
  const query = debouncedSearch.value.trim().toLocaleLowerCase()
  return props.rows.filter((player) => {
    const groupMatch = group.value === 'All'
      || (group.value === 'Pitchers' && player.group === 'Pitcher')
      || (group.value === 'Batters' && player.group === 'Batter')
    return groupMatch && (!query || `${player.name} ${player.role}`.toLocaleLowerCase().includes(query))
  })
})

function playerLink(player: TeamRosterPlayer) {
  if (player.group === 'Pitcher') {
    return { path: '/pitcher-personal', query: { year: props.year, role: player.role, team: props.teamId, pitcher_id: player.player_id } }
  }
  return { path: '/batter-personal', query: { year: props.year, team: props.teamId, batter_id: player.player_id } }
}

</script>

<style scoped>
.team-panel {
  border: 1px solid var(--team-panel-border);
  border-radius: 16px;
  padding: 22px;
  background: var(--team-panel-bg);
  box-shadow: var(--shadow-sm);
}

.team-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.team-panel__header > div > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--team-accent);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.team-panel__header h2 {
  margin: 5px 0 0;
  color: var(--color-text);
  font-size: 21px;
}

.roster-panel__count {
  color: var(--color-muted-text);
  font-family: "Fira Code", monospace;
  font-size: 11px;
}

.roster-panel__controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.roster-panel__controls label {
  min-height: 42px;
  width: min(100%, 340px);
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--team-panel-border);
  border-radius: 10px;
  padding: 0 12px;
  color: var(--color-muted-text);
  background: var(--color-background);
}

.roster-panel__controls input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  color: var(--color-text);
  background: transparent;
}

.roster-panel__controls > div {
  display: inline-flex;
  gap: 4px;
  border-radius: 10px;
  padding: 4px;
  background: var(--color-muted);
}

.roster-panel__controls button {
  min-height: 34px;
  border: 0;
  border-radius: 7px;
  padding: 6px 12px;
  color: var(--color-muted-text);
  background: transparent;
  cursor: pointer;
  font-size: 11px;
  font-weight: 800;
}

.roster-panel__controls button[aria-pressed="true"] {
  color: #ffffff;
  background: var(--team-primary);
}

.roster-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.roster-grid > a {
  min-height: 68px;
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--team-panel-border);
  border-radius: 11px;
  padding: 10px;
  color: inherit;
  text-decoration: none;
  transition: border-color 160ms ease, background-color 160ms ease;
}

.roster-grid > a:hover,
.roster-grid > a:focus-visible {
  border-color: var(--team-primary);
  background: color-mix(in srgb, var(--team-primary) 9%, transparent);
  outline: none;
}

.roster-grid strong,
.roster-grid small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.roster-grid strong {
  color: var(--color-text);
  font-size: 13px;
}

.roster-grid small {
  margin-top: 4px;
  color: var(--color-muted-text);
  font-size: 10px;
}

.roster-grid svg {
  color: var(--color-muted-text);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

@media (max-width: 900px) {
  .roster-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 620px) {
  .roster-panel__controls {
    align-items: stretch;
    flex-direction: column;
  }

  .roster-panel__controls label {
    width: 100%;
  }

  .roster-grid {
    grid-template-columns: 1fr;
  }
}
</style>
