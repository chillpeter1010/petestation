<template>
  <section class="season-context" aria-label="Team season status">
    <article class="season-context__record">
      <div class="season-context__label"><ChartNoAxesColumnIncreasing :size="16" /> Season record</div>
      <template v-if="record">
        <div class="season-context__record-line">
          <strong>{{ record.wins }}–{{ record.losses }}</strong>
          <span>{{ record.winning_percentage }}</span>
        </div>
        <p>{{ divisionLabel }}</p>
        <div class="season-context__chips">
          <span v-if="record.streak">{{ record.streak }}</span>
          <span v-if="record.games_back !== null">{{ record.games_back }} GB</span>
        </div>
      </template>
      <p v-else class="season-context__muted">Live standings are temporarily unavailable.</p>
    </article>

    <article class="season-context__next">
      <div class="season-context__label"><CalendarClock :size="16" /> Next game</div>
      <template v-if="nextGame">
        <div class="season-context__matchup">
          <span>{{ nextGame.home_away === 'Home' ? 'vs' : '@' }}</span>
          <strong>{{ nextGame.opponent_code || nextGame.opponent_name }}</strong>
          <time :datetime="nextGame.game_datetime">{{ formatGameTime(nextGame.game_datetime) }}</time>
        </div>
        <p>{{ nextGame.venue || nextGame.status }}</p>
        <div class="season-context__probables">
          <span>Probables</span>
          <strong>{{ nextGame.team_probable_pitcher || 'TBD' }}</strong>
          <span>vs</span>
          <strong>{{ nextGame.opponent_probable_pitcher || 'TBD' }}</strong>
        </div>
      </template>
      <p v-else class="season-context__muted">No upcoming game is currently listed.</p>
    </article>
  </section>
</template>

<script setup lang="ts">
import { CalendarClock, ChartNoAxesColumnIncreasing } from '@lucide/vue'
import type { TeamNextGame, TeamSeasonRecord } from '~/types/api'

const props = defineProps<{
  record: TeamSeasonRecord | null
  nextGame: TeamNextGame | null
}>()

const divisionLabel = computed(() => {
  if (!props.record) return ''
  const rank = props.record.division_rank ? `#${props.record.division_rank}` : '—'
  return `${rank} · ${props.record.division_name || 'Division'}`
})

function formatGameTime(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
  }).format(new Date(value))
}
</script>

<style scoped>
.season-context { display: grid; grid-template-columns: minmax(0, .75fr) minmax(0, 1.25fr); gap: 18px; }
.season-context article { min-height: 174px; border: 1px solid var(--team-panel-border); border-radius: 16px; padding: 22px; background: var(--team-panel-bg); box-shadow: var(--shadow-sm); }
.season-context__label { display: flex; align-items: center; gap: 8px; color: var(--color-muted-text); font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.season-context__label svg { color: var(--team-accent); }
.season-context__record-line { display: flex; align-items: baseline; gap: 12px; margin-top: 20px; }
.season-context__record-line strong { color: var(--color-text); font-family: "Fira Code", monospace; font-size: 36px; line-height: 1; }
.season-context__record-line span { color: var(--team-accent); font-weight: 900; }
.season-context p { margin: 8px 0 0; color: var(--color-muted-text); font-size: 12px; }
.season-context__chips { display: flex; gap: 7px; margin-top: 14px; }
.season-context__chips span { border-radius: 999px; padding: 4px 9px; color: var(--color-text); background: color-mix(in srgb, var(--team-primary) 14%, var(--color-muted)); font: 800 11px "Fira Code", monospace; }
.season-context__matchup { display: grid; grid-template-columns: auto auto 1fr; align-items: baseline; gap: 9px; margin-top: 20px; }
.season-context__matchup span { color: var(--color-muted-text); font-weight: 800; }
.season-context__matchup strong { color: var(--team-accent); font: 900 30px "Fira Code", monospace; }
.season-context__matchup time { justify-self: end; color: var(--color-text); font-size: 17px; font-weight: 900; }
.season-context__probables { display: flex; flex-wrap: wrap; gap: 6px 9px; margin-top: 16px; color: var(--color-muted-text); font-size: 12px; }
.season-context__probables strong { color: var(--color-text); }
.season-context__muted { margin-top: 28px !important; }
@media (max-width: 760px) { .season-context { grid-template-columns: 1fr; } .season-context__matchup { grid-template-columns: auto auto; } .season-context__matchup time { grid-column: 1 / -1; justify-self: start; } }
</style>
