<template>
  <section class="team-panel rotation-panel">
    <header class="team-panel__header">
      <div>
        <span><RotateCw :size="16" aria-hidden="true" /> Rotation</span>
        <h2>Starter workload</h2>
      </div>
      <NuxtLink to="/rotation/starter">Full rotation <ArrowUpRight :size="15" /></NuxtLink>
    </header>

    <div v-if="rows.length" class="rotation-list">
      <NuxtLink v-for="(row, index) in rows.slice(0, 6)" :key="row.player_id" :to="playerLink(row.player_id)">
        <span class="rotation-list__rank">{{ String(index + 1).padStart(2, '0') }}</span>
        <span class="rotation-list__player">
          <strong>{{ row.name }}</strong>
          <small>{{ row.starts }} GS · {{ formatValue(row.innings) }} IP</small>
        </span>
        <span class="rotation-list__metric">
          <strong>{{ formatValue(row.pitches_per_start) }}</strong>
          <small>P/GS</small>
        </span>
        <span class="rotation-list__metric">
          <strong>{{ row.qs_rate || '-' }}</strong>
          <small>QS%</small>
        </span>
      </NuxtLink>
    </div>
    <p v-else class="team-panel__empty">No starter rotation data is available for this team.</p>
  </section>
</template>

<script setup lang="ts">
import { ArrowUpRight, RotateCw } from '@lucide/vue'
import type { TeamRotationRow } from '~/types/api'

const props = defineProps<{ rows: TeamRotationRow[]; teamId: string; year: number }>()

function playerLink(playerId: number) {
  return { path: '/pitcher-personal', query: { year: props.year, role: 'SP', team: props.teamId, pitcher_id: playerId } }
}

function formatValue(value: number | null) {
  return value === null ? '-' : value.toFixed(1)
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
  margin-bottom: 18px;
}

.team-panel__header span,
.team-panel__header a {
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

.team-panel__header a {
  min-height: 36px;
  color: var(--color-muted-text);
  letter-spacing: 0;
  text-decoration: none;
  text-transform: none;
}

.rotation-list {
  display: grid;
  gap: 4px;
}

.rotation-list > a {
  min-height: 62px;
  display: grid;
  grid-template-columns: 34px minmax(130px, 1fr) 62px 62px;
  align-items: center;
  gap: 10px;
  border-radius: 10px;
  padding: 8px 10px;
  color: inherit;
  text-decoration: none;
  transition: background-color 160ms ease;
}

.rotation-list > a:hover,
.rotation-list > a:focus-visible {
  background: color-mix(in srgb, var(--team-primary) 10%, transparent);
  outline: none;
}

.rotation-list__rank {
  color: var(--color-muted-text);
  font-family: "Fira Code", monospace;
  font-size: 12px;
}

.rotation-list__player strong,
.rotation-list__player small,
.rotation-list__metric strong,
.rotation-list__metric small {
  display: block;
}

.rotation-list__player strong {
  color: var(--color-text);
  font-size: 14px;
}

.rotation-list small {
  margin-top: 3px;
  color: var(--color-muted-text);
  font-size: 11px;
}

.rotation-list__metric {
  text-align: right;
}

.rotation-list__metric strong {
  color: var(--color-text);
  font-family: "Fira Code", monospace;
  font-size: 13px;
}

.team-panel__empty {
  color: var(--color-muted-text);
}

@media (max-width: 520px) {
  .rotation-list > a {
    grid-template-columns: 28px minmax(0, 1fr) 52px;
  }

  .rotation-list__metric:last-child {
    display: none;
  }
}
</style>
