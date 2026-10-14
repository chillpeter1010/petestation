<template>
  <section class="stamina-timeline" :class="{ compact, 'is-three-signal': threeSignal }">
    <header class="timeline-header">
      <div>
        <span>{{ threeSignal ? 'Observed three-signal stamina view' : 'Observed Game Stamina+' }}</span>
        <h3>{{ displayName }} · {{ scope }}</h3>
        <p v-if="threeSignal">Three aligned measurements, not one composite score.</p>
      </div>
      <label>Scope<select v-model="scope"><option v-for="option in scopes" :key="option" :value="option">{{ option }}</option></select></label>
    </header>

    <div v-if="threeSignal" class="interpretation-strip" role="note">
      <strong>Read disagreements, do not average them.</strong>
      <span>Quality tracks Stuff+ retention; Physical tracks public movement/mechanics stability; Command tracks Location+ retention.</span>
    </div>

    <p v-if="loading" class="timeline-state">Loading game-by-game stamina signals…</p>
    <div v-else-if="!metricPanels.some(panel => panel.rows.length)" class="timeline-state">
      <p>No eligible {{ scope }} game states for this pitcher.</p>
      <p v-for="message in errors" :key="message" class="error">{{ message }}</p>
    </div>
    <template v-else>
      <div class="signal-grid" :class="{ 'is-single': !threeSignal }">
        <article v-for="panel in metricPanels" :key="panel.key" class="signal-card" :class="`is-${panel.key}`">
          <header><div><span>{{ panel.eyebrow }}</span><h4>{{ panel.title }}</h4></div><strong>{{ fixed(panel.seasonMean, 1) }}</strong></header>
          <p>{{ panel.note }}</p>
          <div v-if="panel.rows.length" class="chart-wrap">
            <svg viewBox="0 0 760 218" role="img" :aria-label="`${displayName} ${panel.title} timeline`">
              <line x1="48" x2="738" :y1="chartY(100)" :y2="chartY(100)" class="average-line" />
              <path :d="seriesPath(panel.rows, false)" class="game-line" />
              <path :d="seriesPath(panel.rows, true)" class="trend-line" />
              <g v-for="row in panel.rows" :key="`${panel.key}-${row.game_pk}`" class="game-point" :class="{ selected: row.game_pk === selectedGamePk }" role="button" tabindex="0" :aria-label="`${formatDate(row.game_date)}, ${panel.title} ${fixed(row.score, 1)}`" @click="selectedGamePk = row.game_pk" @keydown.enter.prevent="selectedGamePk = row.game_pk" @keydown.space.prevent="selectedGamePk = row.game_pk">
                <circle :cx="chartX(row.game_pk)" :cy="chartY(row.score)" :r="row.game_pk === selectedGamePk ? 6 : 4.5" class="game-dot" />
                <title>{{ formatDate(row.game_date) }} · {{ fixed(row.score, 1) }} · Rel {{ fixed(row.reliability, 3) }}</title>
              </g>
              <text x="8" :y="chartY(120) + 4">120</text><text x="8" :y="chartY(100) + 4">100</text><text x="14" :y="chartY(80) + 4">80</text>
              <text v-if="masterGames.length" x="48" y="213">{{ formatDate(masterGames[0].game_date) }}</text>
              <text v-if="masterGames.length > 1" x="738" y="213" text-anchor="end">{{ formatDate(masterGames.at(-1)?.game_date || '') }}</text>
            </svg>
            <div class="chart-key"><span class="game-key">Game</span><span class="trend-key">5-start trend</span></div>
          </div>
          <p v-else class="panel-empty">{{ panel.unavailable }}</p>
        </article>
      </div>

      <article v-if="selectedGame" class="selected-game">
        <header><div><span>Selected start</span><h4>{{ formatDate(selectedGame.game_date) }} · Start {{ selectedGame.start }}</h4></div><p>Click the same x-position in any chart to compare that outing.</p></header>
        <div class="selected-grid">
          <div v-for="panel in metricPanels" :key="`selected-${panel.key}`">
            <span>{{ panel.title }}</span><strong>{{ fixed(selectedPoint(panel.rows)?.score, 1) }}</strong>
            <small v-if="selectedPoint(panel.rows)">80% {{ fixed(selectedPoint(panel.rows)?.ci_low, 1) }}–{{ fixed(selectedPoint(panel.rows)?.ci_high, 1) }} · Rel {{ fixed(selectedPoint(panel.rows)?.reliability, 3) }}</small>
            <small v-else>Unavailable for this start</small>
          </div>
        </div>
      </article>

      <div class="timeline-table-wrap"><table>
        <thead><tr><th>Date</th><th>Start</th><th>Quality</th><th>Q Rel</th><th v-if="threeSignal">Physical</th><th v-if="threeSignal">P Rel</th><th v-if="threeSignal">Command</th><th v-if="threeSignal">C Rel</th><th>Observed pitches</th></tr></thead>
        <tbody><tr v-for="game in masterGames" :key="`table-${game.game_pk}`" :class="{ selected: game.game_pk === selectedGamePk }" @click="selectedGamePk = game.game_pk">
          <td>{{ formatDate(game.game_date) }}</td><td>{{ game.start }}</td><td><strong>{{ fixed(pointFor('quality', game.game_pk)?.score, 1) }}</strong></td><td>{{ fixed(pointFor('quality', game.game_pk)?.reliability, 3) }}</td>
          <td v-if="threeSignal"><strong>{{ fixed(pointFor('physical', game.game_pk)?.score, 1) }}</strong></td><td v-if="threeSignal">{{ fixed(pointFor('physical', game.game_pk)?.reliability, 3) }}</td>
          <td v-if="threeSignal"><strong>{{ fixed(pointFor('command', game.game_pk)?.score, 1) }}</strong></td><td v-if="threeSignal">{{ fixed(pointFor('command', game.game_pk)?.reliability, 3) }}</td>
          <td>{{ pointFor('quality', game.game_pk)?.pitches ?? pointFor('physical', game.game_pk)?.pitches ?? pointFor('command', game.game_pk)?.pitches ?? '—' }}</td>
        </tr></tbody>
      </table></div>
      <div v-if="errors.length" class="partial-errors"><p v-for="message in errors" :key="message">{{ message }}</p></div>
    </template>
  </section>
</template>

<script setup lang="ts">
import type { StaminaCommandRetentionResponse, StaminaGameStatesResponse, StaminaPhysicalStabilityResponse } from '~/types/api'

type Scope = 'Overall' | 'Fastball' | 'Breaking' | 'Offspeed'
type MetricKey = 'quality' | 'physical' | 'command'
interface MetricPoint { game_pk: number; game_date: string; start: number; score: number; ci_low: number; ci_high: number; reliability: number; pitches: number; rolling: number }

const props = withDefaults(defineProps<{ response?: StaminaGameStatesResponse | null; physicalResponse?: StaminaPhysicalStabilityResponse | null; commandResponse?: StaminaCommandRetentionResponse | null; loading?: boolean; error?: string; errors?: string[]; compact?: boolean; threeSignal?: boolean }>(), {
  response: null, physicalResponse: null, commandResponse: null, loading: false, error: '', errors: () => [], compact: false, threeSignal: false
})
const scopes = ['Overall', 'Fastball', 'Breaking', 'Offspeed'] as const
const scope = ref<Scope>('Overall')
const selectedGamePk = ref(0)
const displayName = computed(() => formatPitcherName(props.response?.pitcher_name || props.physicalResponse?.pitcher_name || props.commandResponse?.pitcher_name || 'Pitcher'))
const errors = computed(() => [props.error, ...props.errors].filter(Boolean))

function addRolling(rows: Omit<MetricPoint, 'rolling'>[]): MetricPoint[] {
  return rows.map((row, index) => ({ ...row, rolling: rows.slice(Math.max(0, index - 4), index + 1).reduce((sum, value) => sum + value.score, 0) / Math.min(index + 1, 5) }))
}
const qualityRows = computed<MetricPoint[]>(() => addRolling((props.response?.states || []).filter(row => row.scope === scope.value && row.eligible && row.stamina_plus !== null && row.stamina_plus !== undefined).slice().sort(sortGames).map(row => ({ game_pk: row.game_pk, game_date: row.game_date, start: row.season_start_number, score: Number(row.stamina_plus), ci_low: Number(row.ci_low), ci_high: Number(row.ci_high), reliability: Number(row.reliability), pitches: Number(row.pitches) }))))
const physicalRows = computed<MetricPoint[]>(() => addRolling((props.physicalResponse?.games || []).filter(row => row.eligible).slice().sort(sortGames).map(row => ({ game_pk: row.game_pk, game_date: row.game_date, start: row.season_start_number, score: row.physical_stability_plus, ci_low: row.ci_low, ci_high: row.ci_high, reliability: row.reliability, pitches: row.supported_pitches }))))
const commandRows = computed<MetricPoint[]>(() => addRolling((props.commandResponse?.games || []).filter(row => row.scope === scope.value && row.eligible).slice().sort(sortGames).map(row => ({ game_pk: row.game_pk, game_date: row.game_date, start: row.season_start_number, score: row.command_retention_plus, ci_low: row.ci_low, ci_high: row.ci_high, reliability: row.reliability, pitches: row.late_pitches }))))

const metricPanels = computed(() => {
  const panels = [{ key: 'quality' as MetricKey, eyebrow: 'Stuff+ retention', title: 'Quality Stamina+', note: 'Did pitch quality hold up relative to expectation?', unavailable: `No eligible ${scope.value} quality state.`, rows: qualityRows.value }]
  if (props.threeSignal) panels.push(
    { key: 'physical', eyebrow: 'Tracked mechanics', title: 'Physical Stability+', note: 'Did velocity, shape and release measurements remain stable?', unavailable: 'No eligible all-pitch physical state.', rows: physicalRows.value },
    { key: 'command', eyebrow: 'Location+ retention', title: 'Command Retention+', note: 'Did command hold up relative to the early-game ceiling?', unavailable: `No eligible ${scope.value} command state.`, rows: commandRows.value }
  )
  return panels.map(panel => ({ ...panel, seasonMean: panel.rows.length ? panel.rows.reduce((sum, row) => sum + row.score, 0) / panel.rows.length : null }))
})
const masterGames = computed(() => {
  const games = new Map<number, { game_pk: number; game_date: string; start: number }>()
  metricPanels.value.forEach(panel => panel.rows.forEach(row => games.set(row.game_pk, { game_pk: row.game_pk, game_date: row.game_date, start: row.start })))
  return [...games.values()].sort(sortGames)
})
const selectedGame = computed(() => masterGames.value.find(game => game.game_pk === selectedGamePk.value))
watch(masterGames, games => { if (games.length && !games.some(game => game.game_pk === selectedGamePk.value)) selectedGamePk.value = games.at(-1)?.game_pk || 0 }, { immediate: true })

function sortGames(left: { game_date: string; game_pk: number }, right: { game_date: string; game_pk: number }) { return `${left.game_date}-${left.game_pk}`.localeCompare(`${right.game_date}-${right.game_pk}`) }
function chartX(gamePk: number) { const index = masterGames.value.findIndex(game => game.game_pk === gamePk); return masterGames.value.length <= 1 ? 393 : 48 + index * (690 / (masterGames.value.length - 1)) }
function chartY(value: number) { const bounded = Math.max(70, Math.min(130, Number(value))); return 190 - ((bounded - 70) / 60) * 166 }
function seriesPath(rows: MetricPoint[], rolling: boolean) {
  const lookup = new Map(rows.map(row => [row.game_pk, row])); let started = false
  return masterGames.value.map(game => { const row = lookup.get(game.game_pk); if (!row) { started = false; return '' }; const command = started ? 'L' : 'M'; started = true; return `${command}${chartX(game.game_pk)},${chartY(rolling ? row.rolling : row.score)}` }).filter(Boolean).join(' ')
}
function rowsFor(key: MetricKey) { return key === 'quality' ? qualityRows.value : key === 'physical' ? physicalRows.value : commandRows.value }
function pointFor(key: MetricKey, gamePk: number) { return rowsFor(key).find(row => row.game_pk === gamePk) }
function selectedPoint(rows: MetricPoint[]) { return rows.find(row => row.game_pk === selectedGamePk.value) }
function fixed(value: number | null | undefined, digits: number) { return value === null || value === undefined || !Number.isFinite(Number(value)) ? '—' : Number(value).toFixed(digits) }
function formatDate(value: string) { return String(value).slice(0, 10) }
function formatPitcherName(value: string) { const [lastName, ...givenNameParts] = value.split(','); const givenName = givenNameParts.join(',').trim(); return givenName ? `${givenName} ${lastName.trim()}` : value }
</script>

<style scoped>
.stamina-timeline{display:grid;gap:16px;border:1px solid var(--color-border);border-radius:var(--radius-md);padding:18px;background:var(--color-surface)}.stamina-timeline.compact{border:0;border-radius:0;padding:18px 22px 22px}.timeline-header,.signal-card>header,.selected-game>header{display:flex;align-items:end;justify-content:space-between;gap:16px}.timeline-header span,.signal-card header span,.selected-game header span{color:var(--color-primary);font-size:11px;font-weight:900;letter-spacing:.05em;text-transform:uppercase}h3,h4{margin:4px 0 0;color:var(--color-foreground)}.timeline-header p,.signal-card>p,.selected-game header p{margin:5px 0 0;color:var(--color-muted-text);font-size:12px}label{display:grid;gap:5px;color:var(--color-muted-text);font-size:11px;font-weight:800;text-transform:uppercase}select{min-width:150px;height:38px;border:1px solid var(--color-border-strong);border-radius:var(--radius-sm);padding:0 10px;color:var(--color-text);background:var(--color-surface);font:inherit;font-size:13px;text-transform:none}.interpretation-strip{display:flex;gap:10px 18px;flex-wrap:wrap;border-left:3px solid var(--color-primary);padding:10px 12px;background:var(--color-muted);color:var(--color-muted-text);font-size:12px}.interpretation-strip strong{color:var(--color-foreground)}.signal-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.signal-grid.is-single{grid-template-columns:1fr}.signal-card{min-width:0;border:1px solid var(--color-border);padding:14px;background:color-mix(in srgb,var(--color-surface) 94%,var(--color-muted))}.signal-card>header>strong{color:var(--color-foreground);font-size:24px}.signal-card.is-quality{border-top:3px solid var(--color-primary)}.signal-card.is-physical{border-top:3px solid #57a8d8}.signal-card.is-command{border-top:3px solid var(--color-accent)}.chart-wrap{min-width:0;margin-top:8px}svg{display:block;width:100%;min-height:180px;overflow:visible}svg text{fill:var(--color-muted-text);font-size:10px}.average-line{stroke:var(--color-border-strong);stroke-dasharray:5 5}.game-line,.trend-line{fill:none;stroke-linecap:round;stroke-linejoin:round}.game-line{stroke:var(--color-primary);stroke-width:2}.is-physical .game-line{stroke:#57a8d8}.is-command .game-line{stroke:var(--color-accent)}.trend-line{stroke:color-mix(in srgb,var(--color-foreground) 72%,transparent);stroke-width:3}.game-dot{fill:var(--color-primary);stroke:var(--color-surface);stroke-width:2;cursor:pointer}.is-physical .game-dot{fill:#57a8d8}.is-command .game-dot{fill:var(--color-accent)}.game-point:focus{outline:none}.game-point:focus .game-dot,.game-point.selected .game-dot{stroke:var(--color-foreground);stroke-width:3}.chart-key{display:flex;gap:15px;color:var(--color-muted-text);font-size:11px}.chart-key span::before{display:inline-block;width:16px;height:3px;margin-right:6px;vertical-align:middle;background:var(--color-primary);content:''}.chart-key .trend-key::before{background:var(--color-foreground)}.panel-empty{min-height:190px;display:grid;place-items:center;text-align:center}.selected-game{border:1px solid var(--color-border);padding:14px;background:var(--color-muted)}.selected-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px}.selected-grid>div{display:grid;gap:3px;border-left:2px solid var(--color-border-strong);padding-left:10px}.selected-grid span,.selected-grid small{color:var(--color-muted-text);font-size:11px}.selected-grid strong{color:var(--color-foreground);font-size:22px}.timeline-table-wrap{max-height:330px;overflow:auto;border:1px solid var(--color-border)}table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:8px 10px;border-bottom:1px solid var(--color-border);color:var(--color-text);text-align:left;white-space:nowrap}th{position:sticky;top:0;z-index:1;background:var(--color-muted);color:var(--color-foreground)}tbody tr{cursor:pointer}tbody tr:hover,tbody tr.selected{background:color-mix(in srgb,var(--color-primary) 9%,transparent)}.timeline-state{margin:0;padding:18px;color:var(--color-muted-text);text-align:center}.timeline-state p{margin:4px 0}.error,.partial-errors{color:var(--color-warning,#d89b3c)}.partial-errors{font-size:12px}.partial-errors p{margin:3px 0}@media(max-width:1100px){.signal-grid{grid-template-columns:1fr}.signal-card{padding:12px}}@media(max-width:700px){.timeline-header,.selected-game>header{align-items:stretch;flex-direction:column}select{width:100%}.selected-grid{grid-template-columns:1fr}}
</style>
