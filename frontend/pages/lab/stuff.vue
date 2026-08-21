<template>
  <main class="stuff-lab">
    <ComparisonPageHeader
      eyebrow="Pitcher Lab · Stuff"
      title="Stuff Lab"
      description="Pete Stuff+ predicts calibrated pitch-result probabilities, converts them to expected run value, and compares each pitch with its own pitch-type baseline over one shared league context."
      back-to="/lab"
      back-label="Pitcher Lab"
    />

    <section class="control-deck" aria-label="Stuff Lab pitcher filters">
      <div class="control-deck__identity">
        <MlbPlayerHeadshot :player-id="pitcherId" :name="selectedPitcher?.name || 'Pitcher'" :size="76" />
        <div>
          <span>Active pitcher</span>
          <strong>{{ selectedPitcher?.name || 'Select a pitcher' }}</strong>
          <small>{{ selectedPitcher ? `${selectedPitcher.team} · ${selectedPitcher.role}` : 'Season arsenal' }}</small>
        </div>
      </div>
      <label>
        Season
        <input v-model.number="year" type="number" min="2021" max="2030">
      </label>
      <label>
        Role
        <select v-model="role">
          <option value="All">All pitchers</option>
          <option value="SP">Starters</option>
          <option value="RP">Relievers</option>
        </select>
      </label>
      <label>
        Team
        <select v-model="team">
          <option value="All">All teams</option>
          <option v-for="option in teamOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <label class="pitcher-select">
        Pitcher
        <select v-model.number="pitcherId" :disabled="optionsPending || !filteredPitchers.length">
          <option v-for="pitcher in filteredPitchers" :key="pitcher.value" :value="pitcher.value">
            {{ pitcher.name }} · {{ pitcher.team }}
          </option>
        </select>
      </label>
    </section>

    <p v-if="errorMessage" class="state-panel state-panel--error">{{ errorMessage }}</p>
    <p v-else-if="pending" class="state-panel">Loading arsenal and model scores…</p>

    <template v-if="response && pitchRows.length">
      <section class="metric-strip" aria-label="Stuff Lab summary">
        <article v-for="metric in primaryMetrics" :key="metric.key">
          <span>{{ metric.label }}</span>
          <strong>{{ formatMetric(metric.value) }}</strong>
          <small>{{ metricNote(metric.key) }}</small>
        </article>
      </section>

      <section class="arsenal-workbench">
        <nav class="pitch-rail" aria-label="Pitch type selection">
          <button
            v-for="row in pitchRows"
            :key="String(row.Pitch)"
            type="button"
            :class="{ active: selectedPitch === row.Pitch }"
            :aria-pressed="selectedPitch === row.Pitch"
            @click="selectedPitch = String(row.Pitch)"
          >
            <i :style="{ background: getPitchColor(String(row.Pitch)) }" />
            <span><strong>{{ row.Pitch }}</strong><small>{{ formatNumber(row.usage_pct, 1) }}% usage</small></span>
            <b>{{ formatNumber(row.stuff_plus, 0) }}</b>
          </button>
        </nav>

        <article class="shape-panel">
          <header>
            <div>
              <span>Movement map</span>
              <h2>Arsenal shape</h2>
            </div>
            <small>Catcher view · inches</small>
          </header>
          <svg viewBox="0 0 620 430" role="img" aria-label="Pitch movement profile">
            <g class="grid-lines">
              <line v-for="x in [-18, -12, -6, 0, 6, 12, 18]" :key="`x-${x}`" :x1="plotX(x)" y1="35" :x2="plotX(x)" y2="385" />
              <line v-for="y in [-6, 0, 6, 12, 18]" :key="`y-${y}`" x1="48" :y1="plotY(y)" x2="584" :y2="plotY(y)" />
            </g>
            <line class="zero-line" :x1="plotX(0)" y1="35" :x2="plotX(0)" y2="385" />
            <line class="zero-line" x1="48" :y1="plotY(0)" x2="584" :y2="plotY(0)" />
            <g
              v-for="row in pitchRows"
              :key="`point-${row.Pitch}`"
              class="pitch-point"
              :class="{ selected: selectedPitch === row.Pitch }"
              role="button"
              tabindex="0"
              @click="selectedPitch = String(row.Pitch)"
              @keydown.enter="selectedPitch = String(row.Pitch)"
            >
              <circle :cx="plotX(numberValue(row.hb))" :cy="plotY(numberValue(row.ivb))" :r="selectedPitch === row.Pitch ? 17 : 12" :fill="getPitchColor(String(row.Pitch))" />
              <text :x="plotX(numberValue(row.hb))" :y="plotY(numberValue(row.ivb)) - 21">{{ shortPitch(String(row.Pitch)) }}</text>
            </g>
            <text class="axis-label" x="316" y="418">← glove side · horizontal break · arm side →</text>
            <text class="axis-label" transform="translate(16 250) rotate(-90)">induced vertical break</text>
          </svg>
        </article>

        <aside v-if="activePitch" class="pitch-inspector" :style="{ '--pitch-color': getPitchColor(String(activePitch.Pitch)) }">
          <header>
            <div><span>{{ activePitch.pitch_family }}</span><h2>{{ activePitch.Pitch }}</h2></div>
            <strong>{{ formatNumber(activePitch.stuff_plus, 0) }}<small>Stuff+</small></strong>
          </header>
          <div class="grade-track"><i :style="{ width: gradeWidth(activePitch.stuff_plus) }" /></div>
          <div class="trait-grid">
            <div><span>Velocity</span><strong>{{ formatNumber(activePitch.release_speed, 1) }}</strong><small>mph</small></div>
            <div><span>IVB</span><strong>{{ signed(activePitch.ivb) }}</strong><small>in</small></div>
            <div><span>HB</span><strong>{{ signed(activePitch.hb) }}</strong><small>in</small></div>
            <div><span>Spin</span><strong>{{ formatNumber(activePitch.release_spin_rate, 0) }}</strong><small>rpm</small></div>
            <div><span>Extension</span><strong>{{ formatNumber(activePitch.release_extension, 1) }}</strong><small>ft</small></div>
            <div><span>Sample</span><strong>{{ formatNumber(activePitch.pitches, 0) }}</strong><small>pitches</small></div>
          </div>
          <section class="platoon-shape">
            <h3>Observed shape proxy</h3>
            <div><span>vs RHH</span><strong>{{ formatNumber(activePitch.shape_vs_r, 0) }}</strong></div>
            <div><span>vs LHH</span><strong>{{ formatNumber(activePitch.shape_vs_l, 0) }}</strong></div>
            <p>These two values describe the shapes actually observed to each batter side; they are not yet separate trained Stuff+ models.</p>
          </section>
          <footer>{{ activePitch.score_source }}</footer>
        </aside>
      </section>

      <section class="arsenal-table-panel">
        <header>
          <div><span>Full arsenal</span><h2>Pitch quality matrix</h2></div>
          <strong>{{ pitchRows.length }} pitch types</strong>
        </header>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Pitch</th><th>Family</th><th>Usage</th><th>Pete Stuff+</th><th>Raw</th><th>Reliability</th><th>Shape proxy</th><th>Velo</th><th>IVB</th><th>HB</th><th>Spin</th><th>Extension</th></tr></thead>
            <tbody>
              <tr v-for="row in pitchRows" :key="`table-${row.Pitch}`" @click="selectedPitch = String(row.Pitch)">
                <td><i :style="{ background: getPitchColor(String(row.Pitch)) }" />{{ row.Pitch }}</td>
                <td>{{ row.pitch_family }}</td><td>{{ formatNumber(row.usage_pct, 1) }}%</td><td class="plus">{{ formatNumber(row.stuff_plus, 1) }}</td>
                <td>{{ formatNumber(row.raw_stuff_plus, 1) }}</td><td>{{ formatPercent(row.reliability) }}</td><td>{{ formatNumber(row.shape_proxy, 1) }}</td><td>{{ formatNumber(row.release_speed, 1) }}</td><td>{{ signed(row.ivb) }}</td><td>{{ signed(row.hb) }}</td>
                <td>{{ formatNumber(row.release_spin_rate, 0) }}</td><td>{{ formatNumber(row.release_extension, 1) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="response.meta.warnings?.length" class="method-note">
        <strong>Model status</strong>
        <p v-for="warning in response.meta.warnings" :key="warning">{{ warning }}</p>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import type { AnalysisResponse, MetricItem, PitcherOption } from '~/types/api'
import { getPitchColor } from '~/utils/pitchColors'

const api = useApi()
const route = useRoute()
const router = useRouter()
const year = ref(Number(route.query.year) || 2026)
const role = ref('All')
const team = ref('All')
const pitcherId = ref(Number(route.query.pitcherId) || 650644)
const pitchers = ref<PitcherOption[]>([])
const response = ref<AnalysisResponse | null>(null)
const selectedPitch = ref('')
const optionsPending = ref(false)
const pending = ref(false)
const errorMessage = ref('')
let requestToken = 0

const teamOptions = computed(() => [...new Set(pitchers.value.map((row) => row.team).filter(Boolean))].sort())
const filteredPitchers = computed(() => pitchers.value.filter((row) => (role.value === 'All' || row.role === role.value) && (team.value === 'All' || row.team === team.value)))
const selectedPitcher = computed(() => pitchers.value.find((row) => row.value === pitcherId.value) || null)
const pitchRows = computed<Record<string, unknown>[]>(() => response.value?.tables.stuff_scores?.rows || [])
const activePitch = computed(() => pitchRows.value.find((row) => row.Pitch === selectedPitch.value) || pitchRows.value[0] || null)
const primaryMetrics = computed<MetricItem[]>(() => (response.value?.summary || []).filter((row) => ['stuff_plus', 'best_pitch', 'source_pitches', 'pitch_types'].includes(row.key)))

watch([role, team], () => {
  if (!filteredPitchers.value.some((row) => row.value === pitcherId.value)) pitcherId.value = filteredPitchers.value[0]?.value || 0
})
watch(year, loadPitchers)
watch(pitcherId, async (value) => {
  if (!value) return
  await router.replace({ query: { ...route.query, year: String(year.value), pitcherId: String(value) } })
  await runLab()
})

onMounted(loadPitchers)

async function loadPitchers() {
  optionsPending.value = true
  errorMessage.value = ''
  try {
    const [starters, relievers] = await Promise.all([api.pitchers({ year: year.value, role: 'SP' }), api.pitchers({ year: year.value, role: 'RP' })])
    const unique = new Map<number, PitcherOption>()
    for (const row of [...starters, ...relievers]) if (!unique.has(row.value) || row.role === 'SP') unique.set(row.value, row)
    pitchers.value = [...unique.values()].sort((a, b) => a.name.localeCompare(b.name))
    if (!pitchers.value.some((row) => row.value === pitcherId.value)) pitcherId.value = pitchers.value[0]?.value || 0
    else await runLab()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load pitcher options.'
  } finally {
    optionsPending.value = false
  }
}

async function runLab() {
  const token = ++requestToken
  pending.value = true
  errorMessage.value = ''
  try {
    const payload = await api.stuffScore({ year: year.value, pitcherId: pitcherId.value, modelMode: 'pete' })
    if (token !== requestToken) return
    response.value = payload
    const rows = payload.tables.stuff_scores?.rows || []
    selectedPitch.value = rows.some((row) => row.Pitch === selectedPitch.value) ? selectedPitch.value : String(rows[0]?.Pitch || '')
  } catch (error) {
    if (token === requestToken) {
      response.value = null
      errorMessage.value = error instanceof Error ? error.message : 'Stuff Lab API failed.'
    }
  } finally {
    if (token === requestToken) pending.value = false
  }
}

function numberValue(value: unknown) { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : 0 }
function formatNumber(value: unknown, digits = 1) { const parsed = Number(value); return Number.isFinite(parsed) ? parsed.toFixed(digits) : '—' }
function formatMetric(value: unknown) { return typeof value === 'number' ? formatNumber(value, Number.isInteger(value) ? 0 : 1) : String(value ?? '—') }
function signed(value: unknown) { const parsed = Number(value); return Number.isFinite(parsed) ? `${parsed > 0 ? '+' : ''}${parsed.toFixed(1)}` : '—' }
function formatPercent(value: unknown) { const parsed = Number(value); return Number.isFinite(parsed) ? `${(parsed * 100).toFixed(0)}%` : '—' }
function metricNote(key: string) { return ({ stuff_plus: 'pitch-count weighted', best_pitch: 'highest modeled grade', source_pitches: 'live shape sample', pitch_types: 'tracked arsenal' } as Record<string, string>)[key] || '' }
function gradeWidth(value: unknown) { return `${Math.max(4, Math.min(100, (numberValue(value) - 60) / 0.8))}%` }
function plotX(value: number) { return 48 + ((Math.max(-24, Math.min(24, value)) + 24) / 48) * 536 }
function plotY(value: number) { return 385 - ((Math.max(-9, Math.min(24, value)) + 9) / 33) * 350 }
function shortPitch(pitch: string) { return ({ 'Four-Seam': 'FF', '4-Seam': 'FF', Sinker: 'SI', Cutter: 'FC', Slider: 'SL', Sweeper: 'ST', Curveball: 'CU', 'Knuckle Curve': 'KC', Changeup: 'CH', Splitter: 'FS' } as Record<string, string>)[pitch] || pitch.slice(0, 2).toUpperCase() }
</script>

<style scoped>
.stuff-lab { display: grid; gap: 18px; }
.control-deck { display: grid; grid-template-columns: minmax(280px, 1.5fr) 110px 150px 150px minmax(240px, 1fr); align-items: end; gap: 12px; border: 1px solid var(--color-border); border-radius: 18px; padding: 16px; background: var(--color-surface); box-shadow: var(--shadow-sm); }
.control-deck__identity { display: flex; align-items: center; gap: 14px; min-width: 0; }
.control-deck__identity div { display: grid; gap: 3px; min-width: 0; }
.control-deck__identity span, .shape-panel header span, .pitch-inspector header span, .arsenal-table-panel header span { color: var(--color-accent); font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
.control-deck__identity strong { overflow: hidden; color: var(--color-text); font-size: 20px; text-overflow: ellipsis; white-space: nowrap; }
.control-deck__identity small { color: var(--color-muted-text); }
.control-deck label { display: grid; gap: 6px; color: var(--color-muted-text); font-size: 11px; font-weight: 850; text-transform: uppercase; }
.control-deck input, .control-deck select { width: 100%; min-width: 0; height: 42px; border: 1px solid var(--color-border-strong); border-radius: 10px; padding: 0 11px; color: var(--color-text); background: var(--color-background); font: 700 13px inherit; }
.state-panel { margin: 0; border: 1px solid var(--color-border); border-radius: 14px; padding: 18px; color: var(--color-muted-text); background: var(--color-surface); }
.state-panel--error { color: #ff8a8a; }
.metric-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.metric-strip article { display: grid; gap: 4px; min-height: 118px; border: 1px solid var(--color-border); border-radius: 16px; padding: 17px 19px; background: linear-gradient(145deg, color-mix(in srgb, var(--color-accent) 8%, var(--color-surface)), var(--color-surface) 58%); }
.metric-strip span { color: var(--color-muted-text); font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.metric-strip strong { color: var(--color-text); font: 900 29px "Fira Code", monospace; }
.metric-strip small { color: var(--color-muted-text); font-size: 11px; }
.arsenal-workbench { display: grid; grid-template-columns: 220px minmax(420px, 1fr) minmax(320px, .72fr); gap: 14px; align-items: stretch; }
.pitch-rail { display: flex; flex-direction: column; gap: 7px; }
.pitch-rail button { display: grid; grid-template-columns: 9px minmax(0, 1fr) auto; align-items: center; gap: 10px; min-height: 62px; border: 1px solid var(--color-border); border-radius: 13px; padding: 9px 11px; text-align: left; color: var(--color-text); background: var(--color-surface); cursor: pointer; transition: border-color .15s ease, transform .15s ease; }
.pitch-rail button:hover { transform: translateX(2px); border-color: var(--color-border-strong); }
.pitch-rail button.active { border-color: color-mix(in srgb, var(--color-accent) 78%, transparent); background: color-mix(in srgb, var(--color-accent) 9%, var(--color-surface)); }
.pitch-rail i, tbody td i { width: 9px; height: 9px; border-radius: 50%; }
.pitch-rail button span { display: grid; gap: 3px; min-width: 0; }
.pitch-rail strong { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.pitch-rail small { color: var(--color-muted-text); font-size: 10px; }
.pitch-rail b { font: 900 18px "Fira Code", monospace; }
.shape-panel, .pitch-inspector, .arsenal-table-panel { overflow: hidden; border: 1px solid var(--color-border); border-radius: 18px; background: var(--color-surface); }
.shape-panel header, .arsenal-table-panel > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--color-border); padding: 15px 18px; }
.shape-panel h2, .pitch-inspector h2, .arsenal-table-panel h2 { margin: 3px 0 0; color: var(--color-text); font-size: 21px; }
.shape-panel header small { color: var(--color-muted-text); }
.shape-panel svg { width: 100%; height: 470px; display: block; background: radial-gradient(circle at 50% 45%, color-mix(in srgb, var(--color-accent) 5%, transparent), transparent 55%); }
.grid-lines line { stroke: color-mix(in srgb, var(--color-border-strong) 72%, transparent); stroke-width: 1; }
.zero-line { stroke: color-mix(in srgb, var(--color-muted-text) 65%, transparent); stroke-width: 1.5; }
.pitch-point { cursor: pointer; outline: none; }
.pitch-point circle { stroke: #fff; stroke-width: 2; opacity: .84; transition: r .15s ease, opacity .15s ease; }
.pitch-point.selected circle, .pitch-point:hover circle { opacity: 1; filter: drop-shadow(0 0 10px currentColor); }
.pitch-point text { fill: var(--color-text); font: 900 12px "Fira Code", monospace; text-anchor: middle; paint-order: stroke; stroke: var(--color-background); stroke-width: 4px; }
.axis-label { fill: var(--color-muted-text); font: 700 10px "Fira Code", monospace; text-anchor: middle; }
.pitch-inspector { display: flex; flex-direction: column; border-color: color-mix(in srgb, var(--pitch-color) 45%, var(--color-border)); }
.pitch-inspector > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 19px; background: linear-gradient(135deg, color-mix(in srgb, var(--pitch-color) 15%, transparent), transparent 65%); }
.pitch-inspector > header > strong { display: grid; color: var(--pitch-color); font: 900 38px "Fira Code", monospace; text-align: right; }
.pitch-inspector > header small { color: var(--color-muted-text); font: 800 10px inherit; text-transform: uppercase; }
.grade-track { height: 7px; margin: 0 19px 18px; overflow: hidden; border-radius: 99px; background: var(--color-muted); }
.grade-track i { height: 100%; display: block; border-radius: inherit; background: var(--pitch-color); }
.trait-grid { display: grid; grid-template-columns: repeat(2, 1fr); border-top: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); }
.trait-grid div { display: grid; grid-template-columns: 1fr auto; align-items: baseline; gap: 3px 8px; min-height: 88px; padding: 14px 17px; border-right: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); }
.trait-grid div:nth-child(even) { border-right: 0; }
.trait-grid span { grid-column: 1 / -1; color: var(--color-muted-text); font-size: 10px; font-weight: 850; text-transform: uppercase; }
.trait-grid strong { color: var(--color-text); font: 900 21px "Fira Code", monospace; }
.trait-grid small { color: var(--color-muted-text); font-size: 10px; }
.platoon-shape { padding: 17px; }
.platoon-shape h3 { margin: 0 0 11px; font-size: 13px; }
.platoon-shape div { display: flex; justify-content: space-between; border-top: 1px solid var(--color-border); padding: 9px 0; }
.platoon-shape div span { color: var(--color-muted-text); }
.platoon-shape div strong { font: 900 17px "Fira Code", monospace; }
.platoon-shape p { margin: 8px 0 0; color: var(--color-muted-text); font-size: 10px; line-height: 1.45; }
.pitch-inspector footer { margin-top: auto; border-top: 1px solid var(--color-border); padding: 13px 17px; color: var(--color-muted-text); font-size: 10px; }
.arsenal-table-panel > header strong { color: var(--color-muted-text); font-size: 12px; }
.table-scroll { width: 100%; overflow-x: auto; }
table { width: 100%; min-width: 920px; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--color-border); padding: 13px 16px; text-align: right; white-space: nowrap; }
th { color: var(--color-muted-text); font-size: 10px; text-transform: uppercase; }
td { color: var(--color-muted-text); font: 700 12px "Fira Code", monospace; }
th:first-child, th:nth-child(2), td:first-child, td:nth-child(2) { text-align: left; }
tbody tr { cursor: pointer; }
tbody tr:hover { background: color-mix(in srgb, var(--color-accent) 6%, transparent); }
tbody td:first-child { display: flex; align-items: center; gap: 9px; color: var(--color-text); font-family: inherit; font-weight: 850; }
td.plus { color: var(--color-accent); font-size: 14px; font-weight: 900; }
.method-note { border: 1px solid color-mix(in srgb, var(--color-accent) 25%, var(--color-border)); border-radius: 14px; padding: 15px 17px; background: color-mix(in srgb, var(--color-accent) 5%, var(--color-surface)); }
.method-note strong { color: var(--color-accent); }
.method-note p { margin: 6px 0 0; color: var(--color-muted-text); font-size: 12px; }
@media (max-width: 1180px) { .control-deck { grid-template-columns: 1fr 120px 150px; } .control-deck__identity, .pitcher-select { grid-column: span 2; } .arsenal-workbench { grid-template-columns: 190px 1fr; } .pitch-inspector { grid-column: 1 / -1; } .trait-grid { grid-template-columns: repeat(3, 1fr); } .trait-grid div:nth-child(even) { border-right: 1px solid var(--color-border); } }
@media (max-width: 760px) { .control-deck, .metric-strip, .arsenal-workbench { grid-template-columns: 1fr; } .control-deck__identity, .pitcher-select, .pitch-inspector { grid-column: auto; } .pitch-rail { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); } .shape-panel svg { height: auto; } .trait-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
