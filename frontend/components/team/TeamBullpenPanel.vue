<template>
  <section class="bullpen-board">
    <header class="bullpen-board__header">
      <div>
        <span><Gauge :size="16" aria-hidden="true" /> Bullpen availability</span>
        <h2>{{ year }} {{ teamId }} bullpen · {{ dataDate }}</h2>
        <p>Active-roster relievers only. Starters, injured-list players and optioned players are excluded.</p>
      </div>
      <strong>{{ rows.length }} relievers</strong>
    </header>

    <div class="bullpen-board__legend" aria-label="Chart legend">
      <span><i class="legend-recent" /> Last three days</span>
      <span><i class="legend-day" /> Latest game day</span>
      <span><i class="legend-line" /> 45-pitch workload line</span>
    </div>

    <div v-if="rows.length" class="bullpen-chart" role="list" aria-label="Reliever pitch workload chart">
      <NuxtLink v-for="row in rows" :key="row.player_id" :to="playerLink(row.player_id)" role="listitem">
        <span class="bullpen-chart__hand">{{ handLabel(row.throws) }}</span>
        <strong class="bullpen-chart__total">{{ row.pitches_last_3 }}</strong>
        <span class="bullpen-chart__plot" :style="{ '--workload-line': `${barHeight(45)}%` }">
          <i class="bullpen-chart__recent" :style="{ height: `${barHeight(row.pitches_last_3)}%` }" />
          <i v-if="row.pitches_yesterday" class="bullpen-chart__day" :style="{ height: `${barHeight(row.pitches_yesterday)}%` }">
            <b>{{ row.pitches_yesterday }}</b>
          </i>
        </span>
        <span class="bullpen-chart__name">{{ row.name }}</span>
        <span class="bullpen-chart__status" :data-status="row.status">{{ row.status }}</span>
      </NuxtLink>
    </div>
    <p v-else class="bullpen-board__empty">No active reliever workload is available.</p>
  </section>
</template>

<script setup lang="ts">
import { Gauge } from '@lucide/vue'
import type { TeamBullpenRow } from '~/types/api'

const props = defineProps<{ rows: TeamBullpenRow[]; teamId: string; year: number }>()
const chartMaximum = computed(() => Math.max(45, ...props.rows.map(row => row.pitches_last_3), ...props.rows.map(row => row.pitches_yesterday)))
const dataDate = computed(() => props.rows.map(row => row.last_game).filter(Boolean).sort().at(-1) || '—')

function playerLink(playerId: number) {
  return { path: '/pitcher-personal', query: { year: props.year, role: 'RP', team: props.teamId, pitcher_id: playerId } }
}
function barHeight(value: number) { return Math.min(100, Math.max(0, value / chartMaximum.value * 100)) }
function handLabel(value: string | null) { return value === 'L' ? 'LEFTY' : value === 'R' ? 'RIGHTY' : 'PITCHER' }
</script>

<style scoped>
.bullpen-board { overflow: hidden; border: 1px solid var(--team-panel-border); border-radius: 16px; background: var(--team-panel-bg); box-shadow: var(--shadow-sm); }
.bullpen-board__header { display: flex; justify-content: space-between; gap: 24px; border-bottom: 1px solid var(--team-panel-border); padding: 22px 24px; }
.bullpen-board__header span { display: inline-flex; align-items: center; gap: 7px; color: var(--team-accent); font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.bullpen-board__header h2 { margin: 5px 0 0; color: var(--color-text); font-size: 22px; }
.bullpen-board__header p { margin: 6px 0 0; color: var(--color-muted-text); font-size: 12px; }
.bullpen-board__header > strong { flex: 0 0 auto; color: var(--color-muted-text); font: 500 14px "Fira Code", monospace; }
.bullpen-board__legend { display: flex; flex-wrap: wrap; gap: 18px; padding: 16px 24px 0; color: var(--color-muted-text); font-size: 11px; font-weight: 800; }
.bullpen-board__legend span { display: inline-flex; align-items: center; gap: 7px; }
.bullpen-board__legend i { width: 20px; height: 9px; border-radius: 999px; }
.legend-recent { background: color-mix(in srgb, var(--team-primary) 68%, #4f8b3a); }
.legend-day { border: 1px solid #d6d3c8; background: #f2f0e8; }
.legend-line { background: #9ca3a7; }
.bullpen-chart { min-width: 900px; display: grid; grid-template-columns: repeat(auto-fit, minmax(94px, 1fr)); gap: 10px; overflow-x: auto; padding: 28px 24px 24px; }
.bullpen-chart > a { min-width: 94px; display: grid; grid-template-rows: 18px 28px 230px 38px 22px; justify-items: center; color: inherit; text-decoration: none; }
.bullpen-chart > a:focus-visible { border-radius: 8px; outline: 2px solid var(--team-primary); outline-offset: 3px; }
.bullpen-chart__hand { color: var(--color-muted-text); font-size: 9px; font-weight: 900; }
.bullpen-chart__total { color: var(--color-text); font: 900 16px "Fira Code", monospace; }
.bullpen-chart__plot { position: relative; width: 40px; height: 220px; align-self: end; overflow: hidden; border-radius: 8px 8px 0 0; background: linear-gradient(to top, #9ca3a7 0 var(--workload-line), color-mix(in srgb, #9ca3a7 22%, transparent) var(--workload-line) 100%); }
.bullpen-chart__recent, .bullpen-chart__day { position: absolute; right: 0; bottom: 0; left: 0; border-radius: 8px 8px 0 0; }
.bullpen-chart__recent { background: color-mix(in srgb, var(--team-primary) 68%, #4f8b3a); }
.bullpen-chart__day { right: 6px; left: 6px; border: 1px solid color-mix(in srgb, var(--team-primary) 50%, #f2f0e8); background: #f2f0e8; }
.bullpen-chart__day b { position: absolute; top: -5px; left: 50%; color: color-mix(in srgb, var(--team-primary) 78%, #7f1d1d); font: 900 11px "Fira Code", monospace; transform: translate(-50%, -100%); }
.bullpen-chart__name { max-width: 92px; align-self: start; margin-top: 8px; color: var(--color-text); font-size: 11px; font-weight: 900; line-height: 1.15; text-align: center; }
.bullpen-chart__status { align-self: end; border-radius: 999px; padding: 3px 7px; color: #166534; background: #dcfce7; font-size: 8px; font-weight: 900; text-transform: uppercase; }
.bullpen-chart__status[data-status="Monitor"] { color: #92400e; background: #fef3c7; }
.bullpen-chart__status[data-status="Rest"] { color: #991b1b; background: #fee2e2; }
.bullpen-board__empty { padding: 20px 24px; color: var(--color-muted-text); }
@media (max-width: 760px) { .bullpen-board { overflow-x: auto; } .bullpen-board__header { min-width: 720px; } }
</style>
