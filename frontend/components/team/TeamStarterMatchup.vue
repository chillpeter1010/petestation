<template>
  <section class="starter-matchup">
    <header class="starter-matchup__header">
      <div>
        <span><Activity :size="16" /> Rotation game lab</span>
        <h2>{{ teamId }} starter workload</h2>
        <p>Switch team games, then inspect that pitcher's recent form, season WPA and latest outing.</p>
      </div>
      <NuxtLink to="/rotation/starter">Full rotation <ArrowUpRight :size="15" /></NuxtLink>
    </header>

    <template v-if="activeGame">
      <div class="starter-matchup__carousel" aria-label="Team game selection">
        <button type="button" class="carousel-arrow" :disabled="activeGameIndex === 0" aria-label="Older team game" @click="moveGame(-1)">
          <ChevronLeft :size="22" />
        </button>
        <div class="carousel-game">
          <div class="carousel-game__context">
            <span>{{ activeGameStatus }}</span>
            <strong>{{ activeGame.game_date }} · {{ activeGame.home_away === 'Home' ? 'vs' : '@' }} {{ activeGame.opponent }}</strong>
          </div>
          <div class="carousel-game__starters">
            <button
              v-for="(starter, index) in activeGame.starters"
              :key="`${starter.team_code}-${starter.pitcher_id}`"
              type="button"
              :aria-pressed="selectedStarterIndex === index"
              @click="selectStarter(index)"
            >
              <MlbPlayerHeadshot
                :player-id="starter.pitcher_id"
                :name="starter.pitcher_name"
                :size="42"
                :source-width="160"
                :priority="index === selectedStarterIndex"
                decorative
                shape="circle"
              />
              <span>
                <small>{{ starter.team_code }} · {{ starter.role_label }}</small>
                <strong>{{ starter.pitcher_name }}</strong>
              </span>
            </button>
          </div>
        </div>
        <button type="button" class="carousel-arrow" :disabled="activeGameIndex === games.length - 1" aria-label="Newer team game" @click="moveGame(1)">
          <ChevronRight :size="22" />
        </button>
      </div>

      <div class="starter-matchup__direction"><span>Older</span><i /><span>Newer</span></div>

      <p v-if="pending" class="starter-matchup__state">Loading starter workload…</p>
      <p v-else-if="error" class="starter-matchup__state">This starter is not available in the local workload model.</p>
      <template v-else-if="response">
        <div v-if="recentGames.length" class="starter-matchup__games" aria-label="Pitcher's recent appearances, oldest to newest">
          <button
            v-for="game in recentGames"
            :key="Number(game.game_pk)"
            type="button"
            :aria-pressed="selectedGamePk === Number(game.game_pk)"
            @click="selectedGamePk = Number(game.game_pk)"
          >{{ gameLabel(game) }}</button>
        </div>

        <div class="starter-matchup__metrics">
          <article v-for="metric in fatigueMetrics" :key="metric.label"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong></article>
        </div>

        <div class="starter-matchup__analysis">
          <div class="starter-matchup__left">
            <TeamStarterWpaChart :rows="gameLog" />
            <FatigueBarChart :rows="fatigueRows" />
          </div>
          <TeamStarterOutingCard
            :report="outingReport || null"
            :loading="outingPending"
            :pitcher-name="selectedStarter?.pitcher_name || ''"
            :pitcher-id="selectedStarter?.pitcher_id || null"
            :game-pk="outingGamePk"
            :year="year"
          />
        </div>
      </template>
    </template>
    <p v-else class="starter-matchup__state">No recent or upcoming starter games are available.</p>
  </section>
</template>

<script setup lang="ts">
import { Activity, ArrowUpRight, ChevronLeft, ChevronRight } from '@lucide/vue'
import type { AnalysisResponse, TeamStarterGame } from '~/types/api'

const props = defineProps<{ games: TeamStarterGame[]; teamId: string; year: number }>()
const emit = defineEmits<{
  'video-selection': [value: { teamId: string; pitcherId: number; pitcherName: string; gamePk: number } | null]
}>()
const api = useApi()
const activeGameIndex = ref(defaultGameIndex(props.games))
const selectedStarterIndex = ref(0)
const selectedGamePk = ref<number | null>(null)
const activeGame = computed(() => props.games[activeGameIndex.value] || null)
const selectedStarter = computed(() => activeGame.value?.starters[selectedStarterIndex.value] || activeGame.value?.starters[0] || null)
const activeGameStatus = computed(() => {
  if (!activeGame.value) return ''
  if (!activeGame.value.has_pitch_data && !activeGame.value.is_upcoming) return 'Completed · awaiting pitch data'
  return activeGame.value.is_upcoming ? activeGame.value.status : 'Completed'
})
const { data, pending, error } = await useAsyncData(
  `team-starter-workload-${props.teamId}-${props.year}`,
  () => selectedStarter.value
    ? api.teamStarterWorkload({
        year: props.year,
        teamId: selectedStarter.value.team_code || props.teamId,
        pitcherId: selectedStarter.value.pitcher_id,
        gamePk: selectedGamePk.value
      })
    : Promise.resolve(null),
  { watch: [selectedStarter, selectedGamePk] }
)

const response = computed<AnalysisResponse | null>(() => data.value || null)
const gameLog = computed(() => Array.isArray(response.value?.charts.game_log) ? response.value.charts.game_log as Record<string, unknown>[] : [])
const recentGames = computed(() => gameLog.value.slice(-3))
const fatigueRows = computed(() => response.value?.tables.fatigue_by_inning?.rows || [])
const selectedGame = computed(() => recentGames.value.find(row => Number(row.game_pk) === selectedGamePk.value) || recentGames.value.at(-1))
const previousAppearance = computed(() => {
  if (!gameLog.value.length) return null
  const activePk = Number(activeGame.value?.game_pk)
  const activeIndex = gameLog.value.findIndex(row => Number(row.game_pk) === activePk)
  if (activeIndex > 0) return gameLog.value[activeIndex - 1]
  const activeDate = activeGame.value?.game_date || ''
  return [...gameLog.value]
    .reverse()
    .find(row => String(row.game_date || '').slice(0, 10) < activeDate) || null
})
const outingGamePk = computed(() => Number(previousAppearance.value?.game_pk) || null)
const { data: outingReport, pending: outingPending } = await useAsyncData(
  `team-starter-outing-${props.teamId}-${props.year}`,
  () => selectedStarter.value?.pitcher_id && outingGamePk.value
    ? api.personalOutingReport({ year: props.year, pitcherId: selectedStarter.value.pitcher_id, gamePk: outingGamePk.value })
    : Promise.resolve(null),
  { watch: [selectedStarter, outingGamePk] }
)

const fatigueMetrics = computed(() => {
  const finalRow = fatigueRows.value.at(-1)
  return [
    { label: 'Pregame readiness', value: formatNumber(finalRow?.['Pregame Readiness'] ?? 100) },
    { label: 'Final fatigue', value: formatNumber(finalRow?.['Fatigue Score']) },
    { label: 'Pitches', value: formatNumber(finalRow?.['Cumulative Pitches'] ?? selectedGame.value?.pitches) },
    { label: 'Innings tracked', value: fatigueRows.value.length.toLocaleString() }
  ]
})

watch(() => props.games.length, () => { activeGameIndex.value = defaultGameIndex(props.games) })
watch([recentGames, selectedStarter, activeGame], ([recent, , game]) => {
  const ids = recent.map(row => Number(row.game_pk))
  const activePk = Number(game?.game_pk)
  const preferred = !game?.is_upcoming && ids.includes(activePk) ? activePk : ids.at(-1)
  if (!selectedGamePk.value || !ids.includes(selectedGamePk.value)) selectedGamePk.value = preferred || null
}, { immediate: true })
watch([previousAppearance, selectedStarter], ([appearance, starter]) => {
  const gamePk = Number(appearance?.game_pk)
  emit('video-selection', starter && gamePk
    ? { teamId: starter.team_code, pitcherId: starter.pitcher_id, pitcherName: starter.pitcher_name, gamePk }
    : null)
}, { immediate: true })

function moveGame(direction: number) {
  activeGameIndex.value = Math.min(props.games.length - 1, Math.max(0, activeGameIndex.value + direction))
  selectedStarterIndex.value = 0
  selectedGamePk.value = null
}
function selectStarter(index: number) { selectedStarterIndex.value = index; selectedGamePk.value = null }
function defaultGameIndex(games: TeamStarterGame[]) {
  const cutoff = taipeiDateOffset(-1)
  for (let index = games.length - 1; index >= 0; index -= 1) {
    if (games[index].game_date <= cutoff) return index
  }
  return Math.max(0, games.length - 1)
}
function taipeiDateOffset(dayOffset: number) {
  const taipeiParts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Taipei', year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(new Date())
  const value = (type: Intl.DateTimeFormatPartTypes) => Number(taipeiParts.find(part => part.type === type)?.value)
  const date = new Date(Date.UTC(value('year'), value('month') - 1, value('day') + dayOffset))
  return date.toISOString().slice(0, 10)
}
function gameLabel(row: Record<string, unknown>) { return `${String(row.game_date || '').slice(0, 10)} vs ${row.opponent_team || '—'} · ${formatNumber(row.pitches)} P` }
function formatNumber(value: unknown) { const number = Number(value); return Number.isFinite(number) ? Math.round(number).toString() : '—' }
</script>

<style scoped>
.starter-matchup { --color-primary: var(--team-primary); width: 100%; min-width: 0; overflow: hidden; border: 1px solid var(--team-panel-border); border-radius: 16px; padding: 22px; background: var(--team-panel-bg); box-shadow: var(--shadow-sm); }
.starter-matchup__header { display: flex; justify-content: space-between; gap: 18px; }
.starter-matchup__header span, .starter-matchup__header a { display: inline-flex; align-items: center; gap: 7px; color: var(--team-accent); font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.starter-matchup__header h2 { margin: 5px 0 0; color: var(--color-text); font-size: 23px; }
.starter-matchup__header p { margin: 6px 0 0; color: var(--color-muted-text); font-size: 12px; }
.starter-matchup__header a { color: var(--color-muted-text); letter-spacing: 0; text-decoration: none; text-transform: none; }
.starter-matchup__carousel { display: grid; grid-template-columns: 42px minmax(0, 1fr) 42px; align-items: stretch; gap: 10px; margin-top: 20px; }
.carousel-arrow { display: grid; place-items: center; border: 1px solid var(--team-panel-border); border-radius: 10px; color: var(--color-text); background: var(--color-surface); cursor: pointer; }
.carousel-arrow:disabled { opacity: .28; cursor: default; }
.carousel-game { min-width: 0; display: flex; align-items: center; justify-content: space-between; gap: 18px; border: 1px solid var(--team-panel-border); border-radius: 12px; padding: 10px 12px; background: var(--color-surface); }
.carousel-game__context { min-width: 0; flex: 1 1 auto; }
.carousel-game__context span { display: block; color: var(--team-accent); font-size: 9px; font-weight: 900; text-transform: uppercase; }
.carousel-game__context strong { display: block; margin-top: 4px; color: var(--color-text); font-size: 12px; }
.carousel-game__starters { min-width: 0; flex: 0 1 394px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; }
.carousel-game__starters button { width: 100%; min-width: 0; display: grid; grid-template-columns: 42px minmax(0, 1fr); align-items: center; gap: 9px; border: 1px solid var(--team-panel-border); border-radius: 9px; padding: 7px 10px; color: var(--color-text); background: transparent; text-align: left; cursor: pointer; }
.carousel-game__starters button > span { min-width: 0; display: grid; gap: 3px; }
.carousel-game__starters small { color: var(--team-accent); font-size: 8px; font-weight: 900; text-transform: uppercase; }
.carousel-game__starters strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.carousel-game__starters button[aria-pressed="true"] { border-color: var(--team-primary); color: #fff; background: var(--team-primary); }
.carousel-game__starters button[aria-pressed="true"] small { color: #fff; }
.starter-matchup__direction { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 8px; margin: 7px 52px 0; color: var(--color-muted-text); font-size: 8px; font-weight: 900; text-transform: uppercase; }
.starter-matchup__direction i { height: 1px; background: var(--team-panel-border); }
.starter-matchup__games { display: flex; gap: 8px; overflow-x: auto; margin-top: 17px; }
.starter-matchup__games button { min-height: 40px; border: 1px solid var(--team-panel-border); border-radius: 9px; padding: 8px 12px; color: var(--color-muted-text); background: var(--color-surface); font-size: 10px; font-weight: 800; white-space: nowrap; cursor: pointer; }
.starter-matchup__games button[aria-pressed="true"] { border-color: var(--team-primary); color: #fff; background: var(--team-primary); }
.starter-matchup__metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 9px; margin: 12px 0; }
.starter-matchup__metrics article { border: 1px solid var(--team-panel-border); border-radius: 11px; padding: 13px; background: var(--color-surface); }
.starter-matchup__metrics span { display: block; color: var(--color-muted-text); font-size: 9px; font-weight: 900; text-transform: uppercase; }
.starter-matchup__metrics strong { display: block; margin-top: 7px; color: var(--color-text); font: 900 22px "Fira Code", monospace; }
.starter-matchup__analysis { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: stretch; gap: 12px; }
.starter-matchup__left { min-width: 0; display: grid; align-content: start; gap: 12px; }
.starter-matchup__state { margin: 20px 0 0; color: var(--color-muted-text); }
@media (max-width: 980px) { .starter-matchup__analysis { grid-template-columns: 1fr; } }
@media (max-width: 720px) { .carousel-game { align-items: stretch; flex-direction: column; } .carousel-game__starters { flex: none; grid-template-columns: 1fr; } }
@media (max-width: 620px) { .starter-matchup__header { flex-direction: column; } .starter-matchup__metrics { grid-template-columns: 1fr 1fr; } }
</style>
