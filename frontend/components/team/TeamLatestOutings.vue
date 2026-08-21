<template>
  <section class="team-panel outings-panel">
    <header class="team-panel__header">
      <div>
        <span><CalendarDays :size="16" aria-hidden="true" /> Recent starts</span>
        <h2>Latest outings</h2>
      </div>
    </header>

    <div v-if="rows.length" class="outings-list">
      <article v-for="row in rows" :key="row.game_pk">
        <div class="outings-list__date">
          <strong>{{ formatMonth(row.game_date) }}</strong>
          <span>{{ formatDay(row.game_date) }}</span>
        </div>
        <MlbPlayerHeadshot :player-id="row.pitcher_id" :name="row.pitcher_name" :size="42" :source-width="160" decorative shape="circle" />
        <div class="outings-list__identity">
          <NuxtLink class="player-link" :to="pitcherLink(row)">{{ row.pitcher_name }}</NuxtLink>
          <span>{{ row.home_away === 'home' ? 'vs' : '@' }} {{ row.opponent || '-' }} · {{ row.pitches }} pitches</span>
        </div>
        <div class="outings-list__line">
          <span><strong>{{ row.ip || '-' }}</strong> IP</span>
          <span><strong>{{ row.earned_runs }}</strong> ER</span>
          <span><strong>{{ row.strikeouts }}</strong> K</span>
          <span><strong>{{ formatScore(row.game_score) }}</strong> GS</span>
        </div>
        <NuxtLink :to="reportLink(row)" aria-label="Open outing report">
          Report <ArrowUpRight :size="14" aria-hidden="true" />
        </NuxtLink>
      </article>
    </div>
    <p v-else class="team-panel__empty">No recent starter lines are available.</p>
  </section>
</template>

<script setup lang="ts">
import { ArrowUpRight, CalendarDays } from '@lucide/vue'
import type { TeamOutingRow } from '~/types/api'

const props = defineProps<{ rows: TeamOutingRow[]; teamId: string; year: number }>()

function reportLink(row: TeamOutingRow) {
  return {
    path: '/pitcher-personal',
    query: { year: props.year, role: 'SP', team: props.teamId, pitcher_id: row.pitcher_id, tab: 'outing', game_pk: row.game_pk }
  }
}

function pitcherLink(row: TeamOutingRow) {
  return {
    path: '/pitcher-personal',
    query: { year: props.year, role: 'SP', team: props.teamId, pitcher_id: row.pitcher_id }
  }
}

function dateParts(value: string) {
  const date = new Date(`${value}T00:00:00`)
  return {
    month: new Intl.DateTimeFormat('en-US', { month: 'short' }).format(date).toUpperCase(),
    day: new Intl.DateTimeFormat('en-US', { day: '2-digit' }).format(date)
  }
}

function formatMonth(value: string) { return dateParts(value).month }
function formatDay(value: string) { return dateParts(value).day }
function formatScore(value: number | null) { return value === null ? '-' : Math.round(value) }
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
  margin-bottom: 16px;
}

.team-panel__header span {
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

.outings-list {
  display: grid;
}

.outings-list article {
  min-height: 76px;
  display: grid;
  grid-template-columns: 48px 42px minmax(170px, 1fr) minmax(220px, 1.2fr) 72px;
  align-items: center;
  gap: 14px;
  border-top: 1px solid var(--team-panel-border);
  padding: 11px 8px;
}

.outings-list__date {
  border-right: 1px solid var(--team-panel-border);
  text-align: center;
}

.outings-list__date strong,
.outings-list__date span,
.outings-list__identity strong,
.outings-list__identity span {
  display: block;
}

.outings-list__date strong {
  color: var(--team-accent);
  font-size: 9px;
}

.outings-list__date span {
  color: var(--color-text);
  font-family: "Fira Code", monospace;
  font-size: 20px;
  font-weight: 800;
}

.outings-list__identity strong {
  color: var(--color-text);
  font-size: 14px;
}

.player-link {
  display: block;
  width: fit-content;
  color: var(--color-text);
  font-size: 14px;
  font-weight: 800;
  text-decoration: none;
}

.player-link:hover,
.player-link:focus-visible {
  color: var(--team-accent);
  text-decoration: underline;
  outline: none;
}

.outings-list__identity span {
  margin-top: 4px;
  color: var(--color-muted-text);
  font-size: 11px;
}

.outings-list__line {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}

.outings-list__line span {
  color: var(--color-muted-text);
  font-size: 10px;
  text-align: center;
}

.outings-list__line strong {
  display: block;
  margin-bottom: 2px;
  color: var(--color-text);
  font-family: "Fira Code", monospace;
  font-size: 13px;
}

.outings-list article > a {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: 1px solid var(--team-panel-border);
  border-radius: 8px;
  color: var(--color-text);
  font-size: 11px;
  font-weight: 800;
  text-decoration: none;
}

.outings-list article > a:hover,
.outings-list article > a:focus-visible {
  border-color: var(--team-primary);
  color: #ffffff;
  background: var(--team-primary);
  outline: none;
}

.team-panel__empty {
  color: var(--color-muted-text);
}

@media (max-width: 760px) {
  .outings-list article {
    grid-template-columns: 48px 42px minmax(0, 1fr) 68px;
  }

  .outings-list__line {
    grid-column: 3 / -1;
    grid-row: 2;
  }
}
</style>
