<template>
  <section class="team-panel leaderboard-panel">
    <header class="team-panel__header">
      <div>
        <span><Trophy :size="16" aria-hidden="true" /> Team leaders</span>
        <h2>Performance board</h2>
      </div>
      <div class="team-panel__tools">
        <NuxtLink to="/leaderboards">All leaderboards <ArrowUpRight :size="15" /></NuxtLink>
        <LeaderboardDisplayControls v-model:display-mode="displayMode" v-model:heatmap-enabled="heatmapEnabled" />
      </div>
    </header>

    <TabsRoot class="leader-tabs" default-value="pitching">
      <TabsList class="leader-tabs__list" aria-label="Team leaderboard category">
        <TabsTrigger value="pitching">Pitching</TabsTrigger>
        <TabsTrigger value="batting">Batting</TabsTrigger>
      </TabsList>

      <TabsContent value="pitching">
        <div class="leader-table">
          <div class="leader-table__head leader-table__head--pitching"><span>Player</span><span>G</span><span>IP</span><span>ERA</span><span>WHIP</span><span>K</span><span>K%</span><span>BB%</span></div>
          <NuxtLink v-for="(row, index) in pitching" :key="row.player_id" :to="pitcherLink(row)">
            <span class="leader-table__player">
              <em>{{ index + 1 }}</em>
              <MlbPlayerHeadshot :player-id="row.player_id" :name="row.name" :size="34" :source-width="160" decorative shape="circle" />
              <strong>{{ row.name }}</strong>
            </span>
            <span>{{ row.games }}</span><span>{{ formatNumber(row.ip, 1) }}</span><span :style="metricStyle(pitchingPercentiles, row.player_id, 'ERA')">{{ shown(pitchingPercentiles, row.player_id, 'ERA', formatNumber(row.era, 2)) }}</span><span :style="metricStyle(pitchingPercentiles, row.player_id, 'WHIP')">{{ shown(pitchingPercentiles, row.player_id, 'WHIP', formatNumber(row.whip, 2)) }}</span><span>{{ row.strikeouts ?? '-' }}</span><span :style="metricStyle(pitchingPercentiles, row.player_id, 'K%')">{{ shown(pitchingPercentiles, row.player_id, 'K%', formatPercent(row.strikeout_rate)) }}</span><span :style="metricStyle(pitchingPercentiles, row.player_id, 'BB%')">{{ shown(pitchingPercentiles, row.player_id, 'BB%', formatPercent(row.walk_rate)) }}</span>
          </NuxtLink>
        </div>
      </TabsContent>

      <TabsContent value="batting">
        <div class="leader-table">
          <div class="leader-table__head leader-table__head--batting"><span>Player</span><span>PA</span><span>AVG</span><span>OBP</span><span>SLG</span><span>OPS</span><span>wOBA</span><span>HR</span></div>
          <NuxtLink v-for="(row, index) in batting" :key="row.player_id" :to="batterLink(row)">
            <span class="leader-table__player">
              <em>{{ index + 1 }}</em>
              <MlbPlayerHeadshot :player-id="row.player_id" :name="row.name" :size="34" :source-width="160" decorative shape="circle" />
              <strong>{{ row.name }}</strong>
            </span>
            <span>{{ row.plate_appearances ?? '-' }}</span><span :style="metricStyle(battingPercentiles, row.player_id, 'AVG')">{{ shown(battingPercentiles, row.player_id, 'AVG', formatRate(row.avg)) }}</span><span :style="metricStyle(battingPercentiles, row.player_id, 'OBP')">{{ shown(battingPercentiles, row.player_id, 'OBP', formatRate(row.obp)) }}</span><span :style="metricStyle(battingPercentiles, row.player_id, 'SLG')">{{ shown(battingPercentiles, row.player_id, 'SLG', formatRate(row.slg)) }}</span><span :style="metricStyle(battingPercentiles, row.player_id, 'OPS')">{{ shown(battingPercentiles, row.player_id, 'OPS', formatRate(row.ops)) }}</span><span :style="metricStyle(battingPercentiles, row.player_id, 'wOBA')">{{ shown(battingPercentiles, row.player_id, 'wOBA', formatRate(row.woba)) }}</span><span>{{ row.home_runs ?? '-' }}</span>
          </NuxtLink>
        </div>
      </TabsContent>
    </TabsRoot>
    <p class="pr-note">League PR uses all same-season pitchers with at least 20 IP or hitters with at least 100 PA. Team rows below the gate show —; counts and workload are not ranked.</p>
  </section>
</template>

<script setup lang="ts">
import { ArrowUpRight, Trophy } from '@lucide/vue'
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import type { BatterLeaderboardRow, PitcherLeaderboardRow } from '~/types/api'
import { buildLeaderboardPercentiles, leaderboardHeatStyle, leaderboardMetricValue, type LeaderboardDisplayMode } from '~/utils/leaderboardDisplay'

const props = defineProps<{
  pitching: PitcherLeaderboardRow[]
  batting: BatterLeaderboardRow[]
  teamId: string
  year: number
}>()
const api = useApi()
const displayMode = ref<LeaderboardDisplayMode>('actual')
const heatmapEnabled = ref(true)

const { data: leaguePitchingRows } = await useAsyncData(
  () => `team-panel-pitcher-pr-${props.year}`,
  () => api.pitcherLeaderboard({ year: props.year, role: 'All' }),
  { watch: [() => props.year], default: () => [] }
)
const { data: leagueBattingRows } = await useAsyncData(
  () => `team-panel-batter-pr-${props.year}`,
  () => api.batterLeaderboard({ year: props.year }),
  { watch: [() => props.year], default: () => [] }
)
const pitchingPercentiles = computed(() => buildLeaderboardPercentiles(
  leaguePitchingRows.value.filter(row => Number(row.ip || 0) >= 20),
  row => String(row.player_id),
  {
    ERA: { value: row => row.era, direction: 'lower' }, WHIP: { value: row => row.whip, direction: 'lower' },
    'K%': { value: row => row.strikeout_rate, direction: 'higher' }, 'BB%': { value: row => row.walk_rate, direction: 'lower' }
  }
))
const battingPercentiles = computed(() => buildLeaderboardPercentiles(
  leagueBattingRows.value.filter(row => Number(row.plate_appearances || 0) >= 100),
  row => String(row.player_id),
  {
    AVG: { value: row => row.avg, direction: 'higher' }, OBP: { value: row => row.obp, direction: 'higher' },
    SLG: { value: row => row.slg, direction: 'higher' }, OPS: { value: row => row.ops, direction: 'higher' },
    wOBA: { value: row => row.woba, direction: 'higher' }
  }
))

function shown(map: Map<string, Record<string, number>>, playerId: number, label: string, actual: string | number) {
  return leaderboardMetricValue(displayMode.value, map.get(String(playerId)) || {}, label, actual)
}

function metricStyle(map: Map<string, Record<string, number>>, playerId: number, label: string) {
  return leaderboardHeatStyle(map.get(String(playerId))?.[label], heatmapEnabled.value)
}

function pitcherLink(row: PitcherLeaderboardRow) {
  return { path: '/pitcher-personal', query: { year: props.year, role: row.role, team: props.teamId, pitcher_id: row.player_id } }
}

function batterLink(row: BatterLeaderboardRow) {
  return { path: '/batter-personal', query: { year: props.year, team: props.teamId, batter_id: row.player_id } }
}

function formatNumber(value: number | null, digits: number) {
  return value === null ? '-' : value.toFixed(digits)
}

function formatRate(value: number | null) {
  return value === null ? '-' : value.toFixed(3).replace(/^0/, '')
}

function formatPercent(value: number | null) {
  return value === null ? '-' : `${(Math.abs(value) <= 1 ? value * 100 : value).toFixed(1)}%`
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
.team-panel__tools { display: flex; align-items: end; justify-content: flex-end; gap: 14px; flex-wrap: wrap; }
.pr-note { margin: 12px 0 0; color: var(--color-muted-text); font-size: 11px; line-height: 1.5; }
@media (max-width: 760px) { .team-panel__header { flex-direction: column; } .team-panel__tools { justify-content: flex-start; } }

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
  overflow-x: auto;
}

.leader-table__head,
.leader-table > a {
  display: grid;
  min-width: 820px;
  grid-template-columns: minmax(190px, 1fr) repeat(7, minmax(54px, 72px));
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

</style>
