<template>
  <section class="team-panel leaderboard-panel">
    <header class="team-panel__header">
      <div>
        <span><Trophy :size="16" aria-hidden="true" /> Team leaders</span>
        <h2>Performance board</h2>
      </div>
      <NuxtLink to="/leaderboards">All leaderboards <ArrowUpRight :size="15" /></NuxtLink>
    </header>

    <TabsRoot class="leader-tabs" default-value="pitching">
      <TabsList class="leader-tabs__list" aria-label="Team leaderboard category">
        <TabsTrigger value="pitching">Pitching</TabsTrigger>
        <TabsTrigger value="batting">Batting</TabsTrigger>
      </TabsList>

      <TabsContent value="pitching">
        <div class="leader-table">
          <div class="leader-table__head"><span>Player</span><span>IP</span><span>ERA</span><span>K</span></div>
          <NuxtLink v-for="(row, index) in pitching" :key="row.player_id" :to="pitcherLink(row)">
            <span class="leader-table__player">
              <em>{{ index + 1 }}</em>
              <MlbPlayerHeadshot :player-id="row.player_id" :name="row.name" :size="34" :source-width="160" decorative shape="circle" />
              <strong>{{ row.name }}</strong>
            </span>
            <span>{{ formatNumber(row.ip, 1) }}</span>
            <span>{{ formatNumber(row.era, 2) }}</span>
            <span>{{ row.strikeouts ?? '-' }}</span>
          </NuxtLink>
        </div>
      </TabsContent>

      <TabsContent value="batting">
        <div class="leader-table">
          <div class="leader-table__head"><span>Player</span><span>OPS</span><span>HR</span><span>wOBA</span></div>
          <NuxtLink v-for="(row, index) in batting" :key="row.player_id" :to="batterLink(row)">
            <span class="leader-table__player">
              <em>{{ index + 1 }}</em>
              <MlbPlayerHeadshot :player-id="row.player_id" :name="row.name" :size="34" :source-width="160" decorative shape="circle" />
              <strong>{{ row.name }}</strong>
            </span>
            <span>{{ formatNumber(row.ops, 3) }}</span>
            <span>{{ row.home_runs ?? '-' }}</span>
            <span>{{ formatNumber(row.woba, 3) }}</span>
          </NuxtLink>
        </div>
      </TabsContent>
    </TabsRoot>
  </section>
</template>

<script setup lang="ts">
import { ArrowUpRight, Trophy } from '@lucide/vue'
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import type { BatterLeaderboardRow, PitcherLeaderboardRow } from '~/types/api'

const props = defineProps<{
  pitching: PitcherLeaderboardRow[]
  batting: BatterLeaderboardRow[]
  teamId: string
  year: number
}>()

function pitcherLink(row: PitcherLeaderboardRow) {
  return { path: '/pitcher-personal', query: { year: props.year, role: row.role, team: props.teamId, pitcher_id: row.player_id } }
}

function batterLink(row: BatterLeaderboardRow) {
  return { path: '/batter-personal', query: { year: props.year, team: props.teamId, batter_id: row.player_id } }
}

function formatNumber(value: number | null, digits: number) {
  return value === null ? '-' : value.toFixed(digits)
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

.leader-tabs__list {
  display: inline-flex;
  gap: 4px;
  margin-bottom: 12px;
  border-radius: 10px;
  padding: 4px;
  background: var(--color-muted);
}

.leader-tabs__list button {
  min-height: 34px;
  border: 0;
  border-radius: 7px;
  padding: 6px 14px;
  color: var(--color-muted-text);
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
}

.leader-tabs__list button[data-state="active"] {
  color: #ffffff;
  background: var(--team-primary);
  box-shadow: var(--shadow-sm);
}

.leader-table {
  display: grid;
}

.leader-table__head,
.leader-table > a {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) repeat(3, 62px);
  align-items: center;
  gap: 8px;
  padding: 10px 8px;
}

.leader-table__head {
  color: var(--color-muted-text);
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.leader-table__head span:not(:first-child),
.leader-table > a > span:not(:first-child) {
  text-align: right;
}

.leader-table > a {
  min-height: 50px;
  border-top: 1px solid var(--team-panel-border);
  border-radius: 7px;
  color: var(--color-text);
  font-family: "Fira Code", monospace;
  font-size: 12px;
  text-decoration: none;
}

.leader-table > a:hover,
.leader-table > a:focus-visible {
  background: color-mix(in srgb, var(--team-primary) 10%, transparent);
  outline: none;
}

.leader-table__player {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: "Fira Sans", sans-serif;
}

.leader-table__player em {
  width: 20px;
  color: var(--color-muted-text);
  font-family: "Fira Code", monospace;
  font-size: 10px;
  font-style: normal;
}

.leader-table__player strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 520px) {
  .leader-table__head,
  .leader-table > a {
    grid-template-columns: minmax(120px, 1fr) repeat(2, 54px);
  }

  .leader-table__head span:last-child,
  .leader-table > a > span:last-child {
    display: none;
  }
}
</style>
