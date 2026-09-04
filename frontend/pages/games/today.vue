<template>
  <main class="games-page">
    <header class="games-header">
      <div>
        <span class="eyebrow">Game Center</span>
        <h1>Pitching Lines</h1>
        <p>Browse every game in the current data slice, then open pitcher pages or outing reports.</p>
      </div>
      <NuxtLink class="pill-link" to="/pitchers">Pitcher Station</NuxtLink>
    </header>

    <section class="games-controls">
      <label>
        Year
        <select v-model.number="year">
          <option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <label class="date-control">
        Date
        <div class="date-picker">
          <button type="button" class="date-step" aria-label="Previous day" @click="shiftDate(-1)">&lt;</button>
          <input v-model="selectedDate" type="date" @change="loadGames">
          <button type="button" class="date-step" aria-label="Next day" @click="shiftDate(1)">&gt;</button>
        </div>
      </label>
      <button type="button" @click="loadGames">Load Games</button>
      <p>{{ games.length }} games · latest {{ latestGameDate || '-' }}</p>
    </section>

    <section class="games-list" aria-label="Games">
      <button
        v-for="game in games"
        :key="gameKey(game)"
        type="button"
        :class="{ active: Number(game.game_pk) === selectedGamePk }"
        @click="selectGame(Number(game.game_pk))"
      >
        <strong>{{ game.away_team }} @ {{ game.home_team }}</strong>
        <span>{{ game.game_date }} · {{ gameScore(game) }}</span>
      </button>
    </section>

    <section v-if="selectedGame" class="game-detail">
      <div class="detail-heading">
        <div>
          <span class="eyebrow">Game {{ selectedGame.game_pk }}</span>
          <h2>{{ selectedGame.away_team }} @ {{ selectedGame.home_team }}</h2>
        </div>
        <span>{{ selectedGame.game_date }}</span>
      </div>

      <div class="team-grid">
        <article v-for="team in gameTeams" :key="String(team.team)" class="team-card">
          <header>
            <h3>{{ team.team }}</h3>
            <span>{{ team.home_away }}</span>
          </header>
          <div class="pitching-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>IP</th>
                  <th>H</th>
                  <th>R</th>
                  <th>ER</th>
                  <th>BB</th>
                  <th>SO</th>
                  <th>HR</th>
                  <th>NP</th>
                  <th>ERA</th>
                  <th>Pitch Types</th>
                  <th>HH</th>
                  <th>Report</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="pitcher in team.pitchers" :key="`${team.team}-${pitcher.pitcher_id}-${pitcher.name}`">
                  <td>
                    <NuxtLink class="pitcher-link" :to="pitcherLink(pitcher)">
                      {{ pitcher.name }}
                    </NuxtLink>
                  </td>
                  <td>{{ pitcher.ip }}</td>
                  <td>{{ pitcher.hits }}</td>
                  <td>{{ pitcher.runs }}</td>
                  <td>{{ pitcher.earned_runs }}</td>
                  <td>{{ pitcher.walks }}</td>
                  <td>{{ pitcher.strikeouts }}</td>
                  <td>{{ pitcher.home_runs }}</td>
                  <td>{{ pitcher.pitches }}</td>
                  <td>{{ pitcher.era }}</td>
                  <td>
                    <span class="mini-pie" :style="{ background: pitchMixGradient(pitcher.pitch_mix) }" />
                  </td>
                  <td>
                    <span v-if="pitcher.hard_hits" class="hot-tag">x{{ pitcher.hard_hits }}</span>
                    <span v-else>-</span>
                  </td>
                  <td>
                    <NuxtLink class="report-link" :to="reportLink(pitcher)">Report</NuxtLink>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </div>
    </section>

    <section v-else class="empty-detail">
      Select a game to inspect pitcher lines.
    </section>
  </main>
</template>

<script setup lang="ts">
import { getPitchColor } from '~/utils/pitchColors'

type GameRow = {
  game_pk?: number | string
  game_date?: string
  away_team?: string
  home_team?: string
  total_pitches?: number | string
  away_score?: number | string | null
  home_score?: number | string | null
} & Record<string, unknown>
type PitchMixSlice = { pitch: string; pitches: number; color: string }
type PitcherLine = {
  pitcher_id: number
  name: string
  team: string
  role: string
  ip: string
  hits: number
  runs: number
  earned_runs: number
  walks: number
  strikeouts: number
  home_runs: number
  pitches: number
  era: string
  hard_hits: number
  pitch_mix: PitchMixSlice[]
}
type TeamPitching = {
  team: string
  home_away: string
  pitchers: PitcherLine[]
}

const api = useApi()
const yearOptions = [2026, 2025, 2024, 2023, 2022, 2021]
const year = ref(2026)
const selectedDate = ref('')
const games = ref<GameRow[]>([])
const latestGameDate = ref('')
const selectedGamePk = ref<number | null>(null)
const gameDetail = ref<Record<string, unknown> | null>(null)

const selectedGame = computed(() => games.value.find((game) => Number(game.game_pk) === selectedGamePk.value) || null)
const gameTeams = computed<TeamPitching[]>(() => (gameDetail.value?.teams as TeamPitching[] | undefined) || [])

await loadGames()

async function loadGames() {
  const response = await api.gamesList({ year: year.value, date: selectedDate.value || undefined, limit: 120 })
  games.value = (response.games as GameRow[] | undefined) || []
  latestGameDate.value = String(response.latest_game_date || '')
  if (!selectedDate.value && latestGameDate.value) {
    selectedDate.value = latestGameDate.value
    const datedResponse = await api.gamesList({ year: year.value, date: selectedDate.value, limit: 120 })
    games.value = (datedResponse.games as GameRow[] | undefined) || []
  }
  if (games.value.length) {
    await selectGame(Number(games.value[0].game_pk))
  } else {
    selectedGamePk.value = null
    gameDetail.value = null
  }
}

async function selectGame(gamePk: number) {
  selectedGamePk.value = gamePk
  gameDetail.value = await api.gamePitching({ year: year.value, gamePk })
}

async function shiftDate(days: number) {
  if (!selectedDate.value && latestGameDate.value) {
    selectedDate.value = latestGameDate.value
  }
  selectedDate.value = offsetIsoDate(selectedDate.value || todayIsoDate(), days)
  await loadGames()
}

function gameKey(game: GameRow) {
  return String(game.game_pk || `${game.game_date}-${game.away_team}-${game.home_team}`)
}

function gameScore(game: GameRow) {
  const awayScore = scoreValue(game.away_score)
  const homeScore = scoreValue(game.home_score)
  if (awayScore !== null && homeScore !== null) {
    return `${game.away_team} ${awayScore} - ${homeScore} ${game.home_team}`
  }
  return `${game.total_pitches || '-'} pitches`
}

function scoreValue(value: unknown) {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? String(numberValue) : null
}

function offsetIsoDate(value: string, days: number) {
  const [yearPart, monthPart, dayPart] = value.split('-').map(Number)
  const date = new Date(yearPart, (monthPart || 1) - 1, dayPart || 1)
  date.setDate(date.getDate() + days)
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0')
  ].join('-')
}

function todayIsoDate() {
  const date = new Date()
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0')
  ].join('-')
}

function pitcherLink(pitcher: PitcherLine) {
  return {
    path: '/pitcher-personal',
    query: {
      year: year.value,
      role: pitcher.role || 'SP',
      team: pitcher.team,
      pitcher_id: pitcher.pitcher_id
    }
  }
}

function reportLink(pitcher: PitcherLine) {
  return {
    path: '/pitcher-personal',
    query: {
      year: year.value,
      role: pitcher.role || 'SP',
      team: pitcher.team,
      pitcher_id: pitcher.pitcher_id,
      tab: 'outing',
      game_pk: selectedGamePk.value
    }
  }
}

function pitchMixGradient(mix: PitchMixSlice[] = []) {
  const total = mix.reduce((sum, row) => sum + Number(row.pitches || 0), 0)
  if (!total) {
    return getPitchColor('Unknown')
  }
  let start = 0
  const stops = mix.map((row) => {
    const pct = (Number(row.pitches || 0) / total) * 100
    const end = start + pct
    const stop = `${getPitchColor(row.pitch)} ${start.toFixed(2)}% ${end.toFixed(2)}%`
    start = end
    return stop
  })
  return `conic-gradient(${stops.join(', ')})`
}
</script>

<style scoped>
.games-page {
  min-height: 100vh;
  padding: 24px clamp(16px, 3vw, 42px) 48px;
  color: var(--color-foreground);
  background:
    radial-gradient(circle at top right, color-mix(in srgb, var(--color-primary) 24%, transparent), transparent 32rem),
    var(--color-background);
}

.games-header,
.games-controls,
.games-list,
.game-detail,
.empty-detail {
  max-width: 1440px;
  margin-inline: auto;
}

.games-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 18px;
  background: var(--color-surface);
}

.eyebrow {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin: 0;
}

h1 {
  margin-top: 4px;
  font-size: clamp(32px, 4vw, 58px);
}

p,
.detail-heading > span {
  color: var(--color-muted-text);
}

.pill-link,
.games-controls > button,
.report-link {
  border: 1px solid var(--color-primary);
  border-radius: 999px;
  padding: 8px 13px;
  color: #111111;
  background: var(--color-primary);
  font-weight: 900;
  text-decoration: none;
}

.games-controls {
  display: grid;
  grid-template-columns: 120px minmax(250px, 330px) 130px minmax(0, 1fr);
  gap: 12px;
  align-items: end;
  margin-top: 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px;
  background: var(--color-surface);
}

.games-controls label {
  display: grid;
  gap: 6px;
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.games-controls select,
.games-controls input {
  min-height: 42px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  color: var(--color-foreground);
  background: var(--color-background);
  font-weight: 800;
}

.date-picker {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) 42px;
  gap: 8px;
  align-items: center;
}

.date-picker input {
  width: 100%;
}

.date-step {
  min-height: 42px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-foreground);
  background: var(--color-background);
  font-size: 22px;
  font-weight: 900;
  line-height: 1;
  cursor: pointer;
}

.date-step:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.games-controls p {
  justify-self: end;
  font-weight: 800;
}

.games-list {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  margin-top: 14px;
  padding-bottom: 4px;
}

.games-list button {
  min-width: 178px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 11px 12px;
  color: var(--color-foreground);
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
}

.games-list button.active {
  border-color: var(--color-primary);
  box-shadow: inset 0 0 0 1px var(--color-primary);
}

.games-list strong,
.games-list span {
  display: block;
}

.games-list span {
  margin-top: 4px;
  color: var(--color-muted-text);
  font-size: 12px;
}

.game-detail,
.empty-detail {
  margin-top: 18px;
}

.detail-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.team-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.team-card {
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.team-card header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  color: #ffffff;
  background: #b7323b;
}

.team-card header span {
  opacity: 0.82;
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.pitching-table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 860px;
}

th,
td {
  padding: 12px 10px;
  border-bottom: 1px solid color-mix(in srgb, var(--color-border) 70%, transparent);
  text-align: center;
  white-space: nowrap;
}

th:first-child,
td:first-child {
  text-align: left;
}

tbody tr:nth-child(even) {
  background: color-mix(in srgb, var(--color-surface-muted) 42%, transparent);
}

.pitcher-link {
  color: var(--color-foreground);
  font-weight: 900;
  text-decoration: none;
}

.pitcher-link:hover {
  color: var(--color-primary);
}

.mini-pie {
  display: inline-block;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(0, 0, 0, 0.35);
  border-radius: 50%;
  vertical-align: middle;
}

.hot-tag {
  color: #ff9b43;
  font-weight: 900;
}

.report-link {
  display: inline-block;
  padding: 5px 9px;
  font-size: 12px;
}

.empty-detail {
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  padding: 24px;
  color: var(--color-muted-text);
  background: var(--color-surface);
}

@media (max-width: 980px) {
  .games-header,
  .games-controls,
  .team-grid {
    grid-template-columns: 1fr;
  }

  .games-controls p {
    justify-self: start;
  }
}
</style>
