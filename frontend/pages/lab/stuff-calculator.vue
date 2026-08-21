<template>
  <main class="calculator-page">
    <ComparisonPageHeader
      eyebrow="Pitcher Lab · Simulator"
      title="Stuff+ Pitch Designer"
      description="A Lance-style interactive pitch-design workflow scored by the same Peter production model used across the site."
      back-to="/lab"
      back-label="Pitcher Lab"
    />

    <section class="calculator-shell">
      <form class="control-panel" @submit.prevent="calculate">
        <header>
          <div><span>Pitch design inputs</span><h2>Shape the pitch</h2></div>
          <button type="button" @click="resetInputs">Reset</button>
        </header>

        <div class="select-row">
          <label>Pitch type
            <select v-model="input.pitch_type">
              <option v-for="pitch in pitchTypes" :key="pitch.value" :value="pitch.value">{{ pitch.label }}</option>
            </select>
          </label>
          <label>Pitcher hand
            <select v-model="input.pitcher_hand"><option value="R">Right</option><option value="L">Left</option></select>
          </label>
          <label>Sample pitches
            <input v-model.number="input.pitches" type="number" min="1" max="1000" step="1">
          </label>
        </div>

        <div class="control-grid">
          <label v-for="control in controls" :key="control.key">
            <span><b>{{ control.label }}</b><output>{{ formatInput(control.key, control.digits) }} {{ control.unit }}</output></span>
            <input
              v-model.number="input[control.key]"
              type="range"
              :min="control.min"
              :max="control.max"
              :step="control.step"
            >
          </label>
        </div>

        <details>
          <summary>Primary fastball reference</summary>
          <p>Secondary pitches are compared with this reference fastball, matching the current model's feature engineering.</p>
          <div class="reference-grid">
            <label>Velocity <input v-model.number="input.primary_fastball_speed" type="number" min="55" max="110" step="0.1"></label>
            <label>IVB <input v-model.number="input.primary_fastball_ivb" type="number" min="-35" max="35" step="0.1"></label>
            <label>HB <input v-model.number="input.primary_fastball_hb" type="number" min="-35" max="35" step="0.1"></label>
          </div>
        </details>

        <button class="calculate-button" type="submit" :disabled="pending">
          {{ pending ? 'Scoring…' : 'Calculate Stuff+' }}
        </button>
      </form>

      <aside class="result-panel" aria-live="polite">
        <div v-if="result" class="result-card" :class="tone">
          <span>Peter Stuff+</span>
          <strong>{{ result.stuff_plus.toFixed(1) }}</strong>
          <b>{{ result.grade }}</b>
          <div class="score-track"><i :style="{ width: scoreWidth }" /></div>
          <dl>
            <div><dt>Raw Stuff+</dt><dd>{{ result.raw_stuff_plus.toFixed(1) }}</dd></div>
            <div><dt>Reliability</dt><dd>{{ Math.round(result.reliability * 100) }}%</dd></div>
            <div><dt>Pitch scale</dt><dd>{{ scaleLabel }}</dd></div>
            <div><dt>Contexts</dt><dd>{{ result.contexts_evaluated }}</dd></div>
          </dl>
        </div>
        <div v-else class="empty-result">
          <span>Model output</span>
          <strong>—</strong>
          <p>Adjust the pitch and calculate its current Peter Stuff+ score.</p>
        </div>
        <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>

        <section v-if="result" class="derived-panel">
          <header><span>Model-ready traits</span><strong>{{ result.pitch_family }}</strong></header>
          <div><span>Velo vs fastball</span><b>{{ signed(result.derived_features.velo_diff_from_fastball) }}</b></div>
          <div><span>IVB vs fastball</span><b>{{ signed(result.derived_features.ivb_diff_from_fastball) }}</b></div>
          <div><span>HB vs fastball</span><b>{{ signed(result.derived_features.hb_diff_from_fastball) }}</b></div>
          <small>{{ result.model_version }}</small>
        </section>
      </aside>
    </section>

    <section class="method-strip">
      <article><span>1</span><div><strong>Lance-style controls</strong><p>Explore one hypothetical pitch by changing its velocity, movement, release and spin traits.</p></div></article>
      <article><span>2</span><div><strong>Shared league test</strong><p>The shape is evaluated across the model's fixed batter-side, count and zone contexts.</p></div></article>
      <article><span>3</span><div><strong>Pitch-specific scale</strong><p>The expected value is standardized against the same pitch type, then sample reliability is applied.</p></div></article>
    </section>
  </main>
</template>

<script setup lang="ts">
import type { StuffCalculatorInput, StuffCalculatorResponse } from '~/types/api'
import { stuffGradeTone } from '~/utils/stuffGrades'

const api = useApi()

const defaults: StuffCalculatorInput = {
  pitch_type: 'FF', pitcher_hand: 'R', pitches: 50,
  release_speed: 94, ivb: 15, hb: 7, spin_rate: 2300, spin_axis: 190,
  extension: 6.3, release_pos_x: -1.8, release_pos_z: 5.8, arm_angle: 45,
  primary_fastball_speed: 94, primary_fastball_ivb: 15, primary_fastball_hb: 7
}

const input = reactive<StuffCalculatorInput>({ ...defaults })
const result = ref<StuffCalculatorResponse | null>(null)
const pending = ref(false)
const errorMessage = ref('')

const pitchTypes = [
  { value: 'FF', label: '4-Seam' }, { value: 'SI', label: 'Sinker' },
  { value: 'FC', label: 'Cutter' }, { value: 'SL', label: 'Slider' },
  { value: 'ST', label: 'Sweeper' }, { value: 'CU', label: 'Curveball' },
  { value: 'KC', label: 'Knuckle Curve' }, { value: 'CH', label: 'Changeup' },
  { value: 'FS', label: 'Splitter' }
]

type NumericKey = Exclude<keyof StuffCalculatorInput, 'pitch_type' | 'pitcher_hand'>
const controls: { key: NumericKey; label: string; unit: string; min: number; max: number; step: number; digits: number }[] = [
  { key: 'release_speed', label: 'Velocity', unit: 'mph', min: 60, max: 105, step: 0.1, digits: 1 },
  { key: 'ivb', label: 'Induced vertical break', unit: 'in', min: -30, max: 30, step: 0.1, digits: 1 },
  { key: 'hb', label: 'Horizontal break', unit: 'in', min: -30, max: 30, step: 0.1, digits: 1 },
  { key: 'spin_rate', label: 'Spin rate', unit: 'rpm', min: 800, max: 3600, step: 10, digits: 0 },
  { key: 'spin_axis', label: 'Spin axis', unit: '°', min: 0, max: 360, step: 1, digits: 0 },
  { key: 'extension', label: 'Extension', unit: 'ft', min: 4, max: 8, step: 0.1, digits: 1 },
  { key: 'release_pos_x', label: 'Release side', unit: 'ft', min: -4, max: 4, step: 0.1, digits: 1 },
  { key: 'release_pos_z', label: 'Release height', unit: 'ft', min: 3, max: 8, step: 0.1, digits: 1 },
  { key: 'arm_angle', label: 'Arm angle', unit: '°', min: 0, max: 80, step: 1, digits: 0 }
]

const tone = computed(() => `tone-${stuffGradeTone(result.value?.stuff_plus)}`)
const scoreWidth = computed(() => `${Math.max(4, Math.min(100, ((result.value?.stuff_plus || 70) - 60) / 0.8))}%`)
const scaleLabel = computed(() => result.value?.scale_source.replace('pitch_type:', '') || '—')

onMounted(calculate)

function formatInput(key: NumericKey, digits: number) {
  return Number(input[key]).toFixed(digits)
}

function signed(value: unknown) {
  const number = Number(value)
  return Number.isFinite(number) ? `${number > 0 ? '+' : ''}${number.toFixed(1)}` : '—'
}

function resetInputs() {
  Object.assign(input, defaults)
  calculate()
}

async function calculate() {
  pending.value = true
  errorMessage.value = ''
  try {
    result.value = await api.stuffCalculator({ ...input })
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to score this pitch.'
  } finally {
    pending.value = false
  }
}
</script>

<style scoped>
.calculator-page { display: grid; gap: 18px; }
.calculator-shell { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(330px, .75fr); gap: 16px; align-items: start; }
.control-panel, .result-panel, .method-strip { border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); box-shadow: var(--shadow-sm); }
.control-panel { display: grid; gap: 20px; padding: 22px; }
.control-panel header, .derived-panel header { display: flex; justify-content: space-between; align-items: center; gap: 14px; }
.control-panel header span, .derived-panel header span { color: var(--color-primary); font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
.control-panel h2 { margin: 4px 0 0; font-size: 26px; }
.control-panel button { border: 1px solid var(--color-border); border-radius: 9px; padding: 9px 13px; color: var(--color-foreground); background: var(--color-surface-soft); font-weight: 800; cursor: pointer; }
.select-row, .reference-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
label { display: grid; gap: 7px; color: var(--color-muted-text); font-size: 12px; font-weight: 850; }
select, input[type='number'] { min-height: 43px; border: 1px solid var(--color-border); border-radius: 8px; padding: 0 11px; color: var(--color-foreground); background: var(--color-background); font: inherit; }
.control-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 28px; }
.control-grid label > span { display: flex; justify-content: space-between; gap: 12px; }
.control-grid output { color: var(--color-foreground); font-family: var(--font-mono); }
input[type='range'] { width: 100%; accent-color: var(--color-primary); }
details { border: 1px solid var(--color-border); border-radius: 10px; padding: 13px; background: var(--color-background); }
summary { color: var(--color-foreground); font-weight: 900; cursor: pointer; }
details p { color: var(--color-muted-text); font-size: 12px; }
.control-panel .calculate-button { min-height: 50px; border-color: var(--color-primary); color: var(--color-on-primary); background: var(--color-primary); font-size: 15px; }
.result-panel { overflow: hidden; }
.result-card, .empty-result { min-height: 330px; display: grid; align-content: center; justify-items: center; gap: 9px; padding: 28px; background: radial-gradient(circle at 50% 18%, color-mix(in srgb, var(--color-primary) 20%, transparent), transparent 48%); }
.result-card > span, .empty-result > span { color: var(--color-muted-text); font-size: 12px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; }
.result-card > strong, .empty-result > strong { font: 800 clamp(64px, 7vw, 104px)/1 var(--font-mono); }
.result-card > b { border-radius: 10px; padding: 7px 14px; color: var(--color-background); background: var(--color-primary); font-size: 24px; }
.score-track { width: 100%; height: 7px; overflow: hidden; border-radius: 999px; background: var(--color-background); }
.score-track i { display: block; height: 100%; border-radius: inherit; background: var(--color-primary); }
.result-card dl { width: 100%; display: grid; grid-template-columns: 1fr 1fr; gap: 1px; margin: 10px 0 0; overflow: hidden; border-radius: 8px; background: var(--color-border); }
.result-card dl div { display: grid; gap: 4px; padding: 12px; background: var(--color-surface); }
dt { color: var(--color-muted-text); font-size: 10px; font-weight: 900; text-transform: uppercase; } dd { margin: 0; font: 800 15px var(--font-mono); }
.empty-result p { max-width: 250px; margin: 0; color: var(--color-muted-text); text-align: center; }
.error-message { margin: 0; padding: 12px 18px; color: #ff8d82; background: rgba(190, 55, 45, .12); }
.derived-panel { display: grid; gap: 0; border-top: 1px solid var(--color-border); padding: 18px; }
.derived-panel > div { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--color-border); color: var(--color-muted-text); }
.derived-panel b { color: var(--color-foreground); font-family: var(--font-mono); }.derived-panel small { margin-top: 13px; color: var(--color-muted-text); }
.method-strip { display: grid; grid-template-columns: repeat(3, 1fr); overflow: hidden; }
.method-strip article { display: flex; gap: 13px; padding: 18px; border-right: 1px solid var(--color-border); }.method-strip article:last-child { border: 0; }
.method-strip article > span { color: var(--color-primary); font: 900 28px var(--font-mono); }.method-strip strong { font-size: 15px; }.method-strip p { margin: 5px 0 0; color: var(--color-muted-text); font-size: 12px; line-height: 1.5; }
@media (max-width: 980px) { .calculator-shell { grid-template-columns: 1fr; }.method-strip { grid-template-columns: 1fr; }.method-strip article { border-right: 0; border-bottom: 1px solid var(--color-border); } }
@media (max-width: 640px) { .select-row, .reference-grid, .control-grid { grid-template-columns: 1fr; }.control-panel { padding: 16px; } }
</style>
