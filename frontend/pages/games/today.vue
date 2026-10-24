<template>
  <main class="games-page">
    <header class="games-header">
      <div>
        <span class="eyebrow">Petehub Game Center</span>
        <h1>Games</h1>
        <p>Scoreboard, plate-appearance feed, box score, and pitching lines from the current Statcast snapshot.</p>
      </div>
      <div class="header-links">
        <NuxtLink v-if="teamFilter" class="pill-link secondary" :to="`/teams/${teamFilter}`">{{ teamFilter }} dashboard</NuxtLink>
        <NuxtLink class="pill-link" to="/">Home</NuxtLink>
      </div>
    </header>

    <section class="games-controls">
      <label>Year<select v-model.number="year" @change="changeYear"><option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option></select></label>
      <label class="date-control">Date<div class="date-picker"><button type="button" class="date-step" aria-label="Previous day" @click="shiftDate(-1)">&lt;</button><input v-model="selectedDate" type="date" @change="loadGames"><button type="button" class="date-step" aria-label="Next day" @click="shiftDate(1)">&gt;</button></div></label>
      <button type="button" @click="loadGames">Load games</button>
      <div class="scope-summary">
        <strong>{{ teamFilter ? `${teamFilter} games` : 'All MLB games' }}</strong>
        <span>{{ games.length }} on {{ selectedDate || latestGameDate || '—' }}</span>
        <NuxtLink v-if="teamFilter" :to="{ path: '/games/today', query: { year } }">Clear team filter</NuxtLink>
      </div>
    </section>

    <section class="games-list" aria-label="Games">
      <button v-for="game in games" :key="gameKey(game)" type="button" :class="{ active: Number(game.game_pk) === selectedGamePk }" @click="selectGame(Number(game.game_pk))">
        <span class="game-card-status">Final</span>
        <strong>{{ game.away_team }} <b>{{ scoreValue(game.away_score) ?? '—' }}</b></strong>
        <strong>{{ game.home_team }} <b>{{ scoreValue(game.home_score) ?? '—' }}</b></strong>
      </button>
    </section>

    <section v-if="selectedGame && scoreboard" class="game-detail">
      <header class="score-hero">
        <div class="score-team"><MlbTeamLogo :team="String(selectedGame.away_team || '')" :size="72" decorative /><div><span>Away</span><strong>{{ selectedGame.away_team }}</strong></div><b>{{ scoreboard.away.runs }}</b></div>
        <div class="game-state"><span>{{ selectedGame.status || 'Snapshot' }}</span><strong>{{ selectedGame.game_date }}</strong><small>Game {{ selectedGame.game_pk }}</small></div>
        <div class="score-team score-team--home"><b>{{ scoreboard.home.runs }}</b><div><span>Home</span><strong>{{ selectedGame.home_team }}</strong></div><MlbTeamLogo :team="String(selectedGame.home_team || '')" :size="72" decorative /></div>
      </header>

      <div class="line-score-wrap">
        <table class="line-score">
          <thead><tr><th>Team</th><th v-for="inning in scoreboard.innings" :key="inning.inning">{{ inning.inning }}</th><th>R</th><th>H</th><th>E</th></tr></thead>
          <tbody>
            <tr><th>{{ scoreboard.away.team }}</th><td v-for="inning in scoreboard.innings" :key="`a-${inning.inning}`">{{ inning.away ?? '—' }}</td><td><b>{{ scoreboard.away.runs }}</b></td><td>{{ scoreboard.away.hits }}</td><td>{{ scoreboard.away.errors }}</td></tr>
            <tr><th>{{ scoreboard.home.team }}</th><td v-for="inning in scoreboard.innings" :key="`h-${inning.inning}`">{{ inning.home ?? '—' }}</td><td><b>{{ scoreboard.home.runs }}</b></td><td>{{ scoreboard.home.hits }}</td><td>{{ scoreboard.home.errors }}</td></tr>
          </tbody>
        </table>
      </div>

      <nav class="game-tabs" aria-label="Gameday sections" role="tablist"><button v-for="tab in tabs" :key="tab.value" type="button" role="tab" :aria-selected="activeTab === tab.value" :class="{ active: activeTab === tab.value }" @click="activeTab = tab.value">{{ tab.label }}</button></nav>

      <section v-if="activeTab === 'feed'" class="feed-layout">
        <article v-if="selectedPlay" class="plate-appearance-card">
          <header><div><span>{{ halfLabel(selectedPlay.inning_half) }} {{ selectedPlay.inning }} · {{ selectedPlay.outs_before }} out{{ selectedPlay.outs_before === 1 ? '' : 's' }}</span><h2 class="matchup-title"><NuxtLink class="matchup-player" :to="playBatterLink(selectedPlay)"><MlbPlayerHeadshot :player-id="selectedPlay.batter_id" :name="selectedPlay.batter_name" :size="38" :source-width="160" shape="circle" decorative /><b>{{ selectedPlay.batter_name }}</b></NuxtLink><em>vs</em><NuxtLink class="matchup-player" :to="playPitcherLink(selectedPlay)"><MlbPlayerHeadshot :player-id="selectedPlay.pitcher_id" :name="selectedPlay.pitcher_name" :size="38" :source-width="160" shape="circle" decorative /><b>{{ selectedPlay.pitcher_name }}</b></NuxtLink></h2></div><strong>{{ selectedPlay.away_score }}–{{ selectedPlay.home_score }}</strong></header>
          <p>{{ selectedPlay.description }}</p>
          <div class="pitch-visual">
            <StrikeZoneScatter class="game-zone-chart" title="Pitch locations" :points="locatedPitches" :total-pitches="selectedPlay.pitches.length" :selected-key="selectedGamePitchKey" compact :point-scale="1.25" @select-point="selectGamePitch" />
            <ol class="pitch-list"><li v-for="pitch in selectedPlay.pitches" :key="pitch.pitch_number"><i :style="{ background: getPitchColor(pitch.pitch_name) }" /><span><b>{{ pitch.pitch_number }}. {{ pitch.pitch_name }}</b><small>{{ humanizePitchResult(pitch.description) }} · {{ pitch.release_speed ?? '—' }} mph</small></span></li></ol>
          </div>
        </article>
        <aside class="play-feed">
          <header><div><span class="eyebrow">Play feed</span><h2>{{ plays.length }} plate appearances</h2></div><small>Newest first</small></header>
          <button v-for="play in plays" :key="play.at_bat_number" type="button" :class="{ active: play.at_bat_number === selectedAtBat }" @click="selectedAtBat = play.at_bat_number"><span>{{ halfLabel(play.inning_half) }} {{ play.inning }}</span><strong>{{ play.event }}</strong><small>{{ play.description }}</small><b>{{ play.away_score }}–{{ play.home_score }}</b></button>
        </aside>
      </section>

      <section v-else-if="activeTab === 'box'" class="team-grid batting-grid">
        <article v-for="team in battingTeams" :key="team.team" class="team-card">
          <header><h2>{{ team.team }} batting</h2><span>{{ team.home_away }}</span></header>
          <div class="table-wrap"><table class="stats-table"><thead><tr><th>Player</th><th>PA</th><th>AB</th><th>H</th><th>HR</th><th>BB</th><th>SO</th><th>HH</th><th>AVG</th></tr></thead><tbody><tr v-for="hitter in team.hitters" :key="hitter.player_id"><td><NuxtLink class="player-cell" :to="batterLink(hitter)"><MlbPlayerHeadshot :player-id="hitter.player_id" :name="hitter.name" :size="38" :source-width="160" shape="circle" decorative /><span>{{ hitter.name }}</span></NuxtLink></td><td>{{ hitter.pa }}</td><td>{{ hitter.ab }}</td><td>{{ hitter.hits }}</td><td>{{ hitter.home_runs }}</td><td>{{ hitter.walks }}</td><td>{{ hitter.strikeouts }}</td><td>{{ hitter.hard_hits }}</td><td>{{ formatAverage(hitter.average) }}</td></tr></tbody></table></div>
        </article>
      </section>

      <section v-else class="team-grid">
        <article v-for="team in gameTeams" :key="String(team.team)" class="team-card">
          <header><h2>{{ team.team }} pitching</h2><span>{{ team.home_away }}</span></header>
          <div class="table-wrap"><table class="stats-table pitching-table"><thead><tr><th>Name</th><th>IP</th><th>H</th><th>R</th><th>ER</th><th>BB</th><th>SO</th><th>HR</th><th>NP</th><th>ERA</th><th>Mix</th><th>HH</th><th>Report</th></tr></thead><tbody><tr v-for="pitcher in team.pitchers" :key="`${team.team}-${pitcher.pitcher_id}`"><td><NuxtLink class="player-cell" :to="pitcherLink(pitcher)"><MlbPlayerHeadshot :player-id="pitcher.pitcher_id" :name="pitcher.name" :size="38" :source-width="160" shape="circle" decorative /><span>{{ pitcher.name }}</span></NuxtLink></td><td>{{ pitcher.ip }}</td><td>{{ pitcher.hits }}</td><td>{{ pitcher.runs }}</td><td>{{ pitcher.earned_runs }}</td><td>{{ pitcher.walks }}</td><td>{{ pitcher.strikeouts }}</td><td>{{ pitcher.home_runs }}</td><td>{{ pitcher.pitches }}</td><td>{{ pitcher.era }}</td><td><span class="mini-pie" :style="{ background: pitchMixGradient(pitcher.pitch_mix) }" /></td><td>{{ pitcher.hard_hits || '—' }}</td><td><NuxtLink class="report-link" :to="reportLink(pitcher)">Report</NuxtLink></td></tr></tbody></table></div>
        </article>
      </section>

      <p class="snapshot-note"><b>Data note:</b> this is a Petehub Statcast snapshot, not a second-by-second live MLB feed. In-progress games advance when the local update pipeline ingests newer pitches.</p>
    </section>
    <section v-else class="empty-detail">No games are available for this date and scope.</section>
    <Teleport to="body">
      <div v-if="gameVideoOpen" class="game-video-backdrop" @click.self="gameVideoOpen = false">
        <section class="game-video-modal" role="dialog" aria-modal="true" aria-label="Selected pitch video">
          <header><div><span class="eyebrow">Selected pitch</span><h2>{{ selectedGamePitchLabel }}</h2></div><button type="button" aria-label="Close video" @click="gameVideoOpen = false">×</button></header>
          <iframe :src="selectedGamePitchVideoUrl" title="Selected pitch video" />
          <footer><a :href="selectedGamePitchVideoUrl" target="_blank" rel="noreferrer">Open in Baseball Savant</a></footer>
        </section>
      </div>
    </Teleport>
  </main>
</template>

<script setup lang="ts">
import { getPitchColor } from '~/utils/pitchColors'

type GameRow = { game_pk?: number | string; game_date?: string; away_team?: string; home_team?: string; total_pitches?: number | string; away_score?: number | string | null; home_score?: number | string | null; status?: string }
type PitchMixSlice = { pitch: string; pitches: number; color: string }
type PitcherLine = { pitcher_id: number; name: string; team: string; role: string; ip: string; hits: number; runs: number; earned_runs: number; walks: number; strikeouts: number; home_runs: number; pitches: number; era: string; hard_hits: number; pitch_mix: PitchMixSlice[] }
type TeamPitching = { team: string; home_away: string; pitchers: PitcherLine[] }
type InningScore = { inning: number; away: number | null; home: number | null }
type ScoreTeam = { team: string; runs: number; hits: number; errors: number }
type Scoreboard = { innings: InningScore[]; away: ScoreTeam; home: ScoreTeam }
type BatterLine = { player_id: number; name: string; team: string; pa: number; ab: number; hits: number; home_runs: number; walks: number; strikeouts: number; hard_hits: number; average: number | null }
type BattingTeam = { team: string; home_away: string; hitters: BatterLine[] }
type PlayPitch = Record<string, unknown> & { game_date?: string | null; game_pk: number; at_bat_number: number; pitch_number: number; pitch_name: string; description: string; release_speed: number | null; plate_x: number | null; plate_z: number | null; balls: number; strikes: number; play_id?: string | null; video_url?: string | null }
type PlayRow = { at_bat_number: number; inning: number; inning_half: string; outs_before: number; batter_id: number; batter_name: string; pitcher_id: number; pitcher_name: string; event: string; description: string; away_score: number; home_score: number; pitches: PlayPitch[] }
type GameDetail = { game: GameRow; teams: TeamPitching[]; scoreboard: Scoreboard; batting: BattingTeam[]; plays: PlayRow[] }
type TabValue = 'feed' | 'box' | 'pitching'

const api = useApi()
const route = useRoute()
const router = useRouter()
const yearOptions = [2026, 2025, 2024, 2023, 2022, 2021]
const requestedYear = Number(route.query.year)
const year = ref(yearOptions.includes(requestedYear) ? requestedYear : 2026)
const teamFilter = computed(() => String(route.query.team || '').trim().toUpperCase())
const selectedDate = ref(String(route.query.date || ''))
const games = ref<GameRow[]>([])
const latestGameDate = ref('')
const selectedGamePk = ref<number | null>(null)
const gameDetail = ref<GameDetail | null>(null)
const activeTab = ref<TabValue>('feed')
const selectedAtBat = ref<number | null>(null)
const selectedGamePitch = ref<Record<string, unknown> | null>(null)
const gameVideoOpen = ref(false)
const tabs: Array<{ value: TabValue; label: string }> = [{ value: 'feed', label: 'Feed' }, { value: 'box', label: 'Box Score' }, { value: 'pitching', label: 'Pitching' }]

const selectedGame = computed(() => gameDetail.value?.game || games.value.find(game => Number(game.game_pk) === selectedGamePk.value) || null)
const gameTeams = computed(() => gameDetail.value?.teams || [])
const scoreboard = computed(() => gameDetail.value?.scoreboard || null)
const battingTeams = computed(() => gameDetail.value?.batting || [])
const plays = computed(() => gameDetail.value?.plays || [])
const selectedPlay = computed(() => plays.value.find(play => play.at_bat_number === selectedAtBat.value) || plays.value[0] || null)
const locatedPitches = computed(() => (selectedPlay.value?.pitches || []).filter(pitch => pitch.plate_x !== null && pitch.plate_z !== null))
const selectedGamePitchKey = computed(() => selectedGamePitch.value ? pitchPointKey(selectedGamePitch.value) : null)
const selectedGamePitchVideoUrl = computed(() => pitchVideoUrl(selectedGamePitch.value))
const selectedGamePitchLabel = computed(() => {
  const pitch = selectedGamePitch.value
  if (!pitch) return ''
  const speed = Number(pitch.release_speed)
  const speedLabel = Number.isFinite(speed) ? `${speed.toFixed(1)} mph` : 'Velo unavailable'
  return `${pitch.pitch_name || 'Pitch'} · ${speedLabel} · ${humanizePitchResult(String(pitch.description || ''))}`
})

await loadGames()

async function loadGames() {
  const response = await api.gamesList({ year: year.value, date: selectedDate.value || undefined, team: teamFilter.value || undefined, limit: 120 })
  games.value = (response.games as GameRow[] | undefined) || []
  latestGameDate.value = String(response.latest_game_date || '')
  if (!selectedDate.value && latestGameDate.value) {
    selectedDate.value = latestGameDate.value
    const dated = await api.gamesList({ year: year.value, date: selectedDate.value, team: teamFilter.value || undefined, limit: 120 })
    games.value = (dated.games as GameRow[] | undefined) || []
  }
  await router.replace({ query: { year: year.value, date: selectedDate.value || undefined, team: teamFilter.value || undefined } })
  if (games.value.length) await selectGame(Number(games.value[0].game_pk))
  else { selectedGamePk.value = null; gameDetail.value = null; selectedAtBat.value = null }
}

async function selectGame(gamePk: number) { selectedGamePk.value = gamePk; gameDetail.value = await api.gamePitching({ year: year.value, gamePk }) as unknown as GameDetail; selectedAtBat.value = gameDetail.value.plays[0]?.at_bat_number || null; selectedGamePitch.value = null; gameVideoOpen.value = false }
async function changeYear() { selectedDate.value = ''; await loadGames() }
async function shiftDate(days: number) { selectedDate.value = offsetIsoDate(selectedDate.value || latestGameDate.value || todayIsoDate(), days); await loadGames() }
function gameKey(game: GameRow) { return String(game.game_pk || `${game.game_date}-${game.away_team}-${game.home_team}`) }
function scoreValue(value: unknown) { const parsed = Number(value); return Number.isFinite(parsed) ? String(parsed) : null }
function halfLabel(value: string) { return value === 'Top' ? 'Top' : 'Bottom' }
function formatAverage(value: number | null) { return value === null ? '—' : value.toFixed(3).replace(/^0/, '') }
function offsetIsoDate(value: string, days: number) { const [y, m, d] = value.split('-').map(Number); const date = new Date(y, (m || 1) - 1, d || 1); date.setDate(date.getDate() + days); return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-') }
function todayIsoDate() { const date = new Date(); return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-') }
function pitcherLink(pitcher: PitcherLine) { return { path: '/pitcher-personal', query: { year: year.value, role: pitcher.role || 'SP', team: pitcher.team, pitcher_id: pitcher.pitcher_id } } }
function reportLink(pitcher: PitcherLine) { return { path: '/pitcher-personal', query: { year: year.value, role: pitcher.role || 'SP', team: pitcher.team, pitcher_id: pitcher.pitcher_id, tab: 'outing', game_pk: selectedGamePk.value } } }
function batterLink(hitter: BatterLine) { return { path: '/batter-personal', query: { year: year.value, batter_id: hitter.player_id, team: hitter.team } } }
function playBatterLink(play: PlayRow) { return { path: '/batter-personal', query: { year: year.value, batter_id: play.batter_id, team: play.inning_half === 'Top' ? selectedGame.value?.away_team : selectedGame.value?.home_team } } }
function playPitcherLink(play: PlayRow) { return { path: '/pitcher-personal', query: { year: year.value, pitcher_id: play.pitcher_id, team: play.inning_half === 'Top' ? selectedGame.value?.home_team : selectedGame.value?.away_team } } }
function humanizePitchResult(value: string) { return value.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase()) || '—' }
function pitchPointKey(point: Record<string, unknown>) { return [point.game_pk, point.at_bat_number, point.pitch_number, point.plate_x, point.plate_z, point.pitch_name].map(value => String(value ?? '')).join('|') }
function pitchVideoUrl(pitch: Record<string, unknown> | null) { if (!pitch) return ''; const direct = String(pitch.video_url || '').trim(); if (direct && !['none', 'nan', 'null'].includes(direct.toLowerCase())) return direct; const playId = String(pitch.play_id || '').trim(); return playId && !['none', 'nan', 'null'].includes(playId.toLowerCase()) ? `https://baseballsavant.mlb.com/sporty-videos?playId=${encodeURIComponent(playId)}` : '' }
function selectGamePitch(pitch: Record<string, unknown>) { selectedGamePitch.value = pitch; if (pitchVideoUrl(pitch)) gameVideoOpen.value = true }
function pitchMixGradient(mix: PitchMixSlice[] = []) { const total = mix.reduce((sum, row) => sum + Number(row.pitches || 0), 0); if (!total) return getPitchColor('Unknown'); let start = 0; const stops = mix.map(row => { const end = start + (Number(row.pitches || 0) / total) * 100; const stop = `${getPitchColor(row.pitch)} ${start.toFixed(2)}% ${end.toFixed(2)}%`; start = end; return stop }); return `conic-gradient(${stops.join(', ')})` }

watch(selectedAtBat, () => { selectedGamePitch.value = null; gameVideoOpen.value = false })
</script>

<style scoped>
.games-page{min-height:100vh;padding:24px clamp(16px,3vw,42px) 48px;color:var(--color-foreground);background:radial-gradient(circle at top right,color-mix(in srgb,var(--color-primary) 20%,transparent),transparent 32rem),var(--color-background)}
.games-header,.games-controls,.games-list,.game-detail,.empty-detail{max-width:1440px;margin-inline:auto}.games-header{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:24px;border:1px solid var(--color-border);border-radius:var(--radius-md);padding:20px;background:var(--color-surface)}
.eyebrow{color:var(--color-primary);font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}h1,h2,p{margin:0}h1{margin-top:4px;font-size:clamp(34px,4vw,58px)}.games-header p,.snapshot-note{color:var(--color-muted-text)}.header-links{display:flex;gap:8px}.pill-link,.games-controls>button,.report-link{border:1px solid var(--color-primary);border-radius:999px;padding:9px 14px;color:#111;background:var(--color-primary);font-weight:900;text-decoration:none}.pill-link.secondary{color:var(--color-primary);background:transparent}
.games-controls{display:grid;grid-template-columns:120px minmax(250px,330px) 130px minmax(0,1fr);align-items:end;gap:12px;margin-top:16px;border:1px solid var(--color-border);border-radius:var(--radius-md);padding:16px;background:var(--color-surface)}.games-controls label{display:grid;gap:6px;color:var(--color-muted-text);font-size:11px;font-weight:900;text-transform:uppercase}.games-controls select,.games-controls input{width:100%;min-height:42px;box-sizing:border-box;border:1px solid var(--color-border);border-radius:var(--radius-sm);padding:8px 10px;color:var(--color-foreground);background:var(--color-background);font-weight:800}.date-picker{display:grid;grid-template-columns:42px minmax(0,1fr) 42px;gap:8px}.date-step{min-height:42px;border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-foreground);background:var(--color-background);font-size:20px;cursor:pointer}.scope-summary{display:grid;justify-items:end;gap:2px}.scope-summary span,.scope-summary a{color:var(--color-muted-text);font-size:12px}.scope-summary a{color:var(--color-primary)}
.games-list{display:flex;gap:10px;overflow-x:auto;margin-top:14px;padding-bottom:4px}.games-list button{min-width:174px;display:grid;grid-template-columns:1fr auto;gap:5px 14px;border:1px solid var(--color-border);border-radius:10px;padding:11px 13px;color:var(--color-foreground);background:var(--color-surface);cursor:pointer;text-align:left}.games-list button.active{border-color:var(--color-primary);box-shadow:inset 0 0 0 1px var(--color-primary)}.games-list strong{display:flex;grid-column:1/-1;justify-content:space-between}.game-card-status{grid-column:1/-1;color:var(--color-primary);font-size:10px;font-weight:900;text-transform:uppercase}
.game-detail{margin-top:18px}.score-hero{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:22px;border:1px solid var(--color-border);border-radius:16px 16px 0 0;padding:22px;background:var(--color-surface)}.score-team{display:flex;align-items:center;gap:14px}.score-team--home{justify-content:flex-end}.score-team div{display:grid;gap:2px}.score-team span,.game-state span,.game-state small{color:var(--color-muted-text);font-size:11px;font-weight:800;text-transform:uppercase}.score-team strong{font-size:22px}.score-team>b{margin-left:auto;font-size:50px}.score-team--home>b{margin:0}.game-state{display:grid;justify-items:center;gap:3px}.game-state span{color:var(--color-primary)}
.line-score-wrap{overflow-x:auto;border-inline:1px solid var(--color-border);background:var(--color-surface)}.line-score{width:100%;min-width:760px;border-collapse:collapse}.line-score th,.line-score td{padding:10px;border-bottom:1px solid var(--color-border);text-align:center}.line-score th:first-child{text-align:left}.line-score thead{color:var(--color-muted-text);font-size:11px;text-transform:uppercase}
.game-tabs{display:flex;gap:4px;overflow-x:auto;border:1px solid var(--color-border);border-top:0;border-radius:0 0 14px 14px;padding:7px;background:var(--color-surface)}.game-tabs button{min-height:38px;border:0;border-radius:8px;padding:7px 18px;color:var(--color-muted-text);background:transparent;font:inherit;font-weight:850;cursor:pointer}.game-tabs button.active{color:var(--color-on-primary);background:var(--color-primary)}
.feed-layout{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(330px,.75fr);gap:16px;margin-top:16px}.plate-appearance-card,.play-feed,.team-card{border:1px solid var(--color-border);border-radius:14px;background:var(--color-surface)}.plate-appearance-card{padding:20px}.plate-appearance-card>header,.play-feed>header,.team-card>header{display:flex;align-items:center;justify-content:space-between;gap:12px}.plate-appearance-card>header>div>span{color:var(--color-primary);font-size:11px;font-weight:900;text-transform:uppercase}.plate-appearance-card h2{margin-top:4px}.plate-appearance-card>header>strong{font-size:28px}.plate-appearance-card>p{margin-top:10px;color:var(--color-muted-text)}.matchup-title{display:flex;flex-wrap:wrap;align-items:center;gap:8px 10px}.matchup-title em{color:var(--color-muted-text);font-size:14px;font-style:normal}.matchup-player{display:inline-flex;align-items:center;gap:8px;color:var(--color-foreground);text-decoration:none}.matchup-player:hover{color:var(--color-primary)}.pitch-visual{display:grid;grid-template-columns:minmax(300px,1fr) minmax(260px,.82fr);gap:28px;align-items:start;margin-top:22px}.game-zone-chart{width:100%;min-width:0}.pitch-list{max-height:470px;display:grid;gap:8px;overflow:auto;margin:0;padding:0;list-style:none}.pitch-list li{display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--color-border);padding:8px 0}.pitch-list i{width:10px;height:10px;border-radius:50%}.pitch-list span{display:grid}.pitch-list small{color:var(--color-muted-text)}
.play-feed{max-height:620px;overflow:auto}.play-feed>header{position:sticky;z-index:2;top:0;padding:14px;background:var(--color-surface);border-bottom:1px solid var(--color-border)}.play-feed>header small{color:var(--color-muted-text)}.play-feed button{position:relative;width:100%;display:grid;gap:3px;border:0;border-bottom:1px solid var(--color-border);padding:13px 52px 13px 14px;color:var(--color-foreground);background:transparent;cursor:pointer;text-align:left}.play-feed button:hover,.play-feed button.active{background:color-mix(in srgb,var(--color-primary) 11%,transparent)}.play-feed button>span,.play-feed button>small{color:var(--color-muted-text);font-size:11px}.play-feed button>b{position:absolute;top:14px;right:14px}
.team-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:16px}.team-card{overflow:hidden}.team-card>header{padding:13px 15px;color:#fff;background:color-mix(in srgb,var(--color-primary) 72%,#502010)}.team-card>header span{font-size:11px;font-weight:900;text-transform:uppercase}.table-wrap{overflow:auto}.stats-table{width:100%;min-width:650px;border-collapse:collapse}.pitching-table{min-width:860px}.stats-table th,.stats-table td{padding:10px;border-bottom:1px solid var(--color-border);text-align:center;white-space:nowrap}.stats-table th:first-child,.stats-table td:first-child{text-align:left}.stats-table th{color:var(--color-muted-text);font-size:11px;text-transform:uppercase}.stats-table a{color:var(--color-foreground);font-weight:850;text-decoration:none}.stats-table a:hover{color:var(--color-primary)}.player-cell{display:inline-flex;align-items:center;gap:9px}.mini-pie{display:inline-block;width:30px;height:30px;border:1px solid #0005;border-radius:50%}.report-link{display:inline-block;padding:5px 9px!important;font-size:11px}.snapshot-note{margin-top:16px;border-left:3px solid var(--color-primary);padding:10px 13px;font-size:12px}.empty-detail{margin-top:18px;border:1px dashed var(--color-border);border-radius:var(--radius-md);padding:24px;color:var(--color-muted-text);background:var(--color-surface)}
.game-video-backdrop{position:fixed;z-index:1000;inset:0;display:grid;place-items:center;padding:24px;background:rgba(2,6,23,.82);backdrop-filter:blur(6px)}.game-video-modal{width:min(920px,96vw);overflow:hidden;border:1px solid var(--color-primary);border-radius:16px;background:var(--color-surface);box-shadow:0 28px 90px #000b}.game-video-modal header,.game-video-modal footer{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 18px}.game-video-modal header{border-bottom:1px solid var(--color-border)}.game-video-modal header button{width:38px;height:38px;border:1px solid var(--color-border);border-radius:50%;color:var(--color-foreground);background:transparent;font-size:24px;cursor:pointer}.game-video-modal iframe{display:block;width:100%;height:min(68vh,620px);border:0;background:#000}.game-video-modal footer{border-top:1px solid var(--color-border)}.game-video-modal footer a{color:var(--color-primary);font-weight:850}
@media(max-width:980px){.games-header,.games-controls,.team-grid,.feed-layout{grid-template-columns:1fr}.scope-summary{justify-items:start}.pitch-visual{grid-template-columns:1fr 1fr}}
@media(max-width:700px){.games-page{padding-inline:12px}.games-header{align-items:start;grid-template-columns:1fr}.header-links{flex-wrap:wrap}.score-hero{grid-template-columns:1fr}.score-team--home{flex-direction:row-reverse;justify-content:flex-start}.score-team--home>b{margin-left:auto;order:-1}.game-state{grid-row:1}.pitch-visual{grid-template-columns:1fr}.strike-zone{margin:auto}.game-tabs button{flex:1}}
</style>
