<template>
  <section class="stuff-card" :class="{ compact, 'large-text': largeText, 'with-location': showLocation }">
    <header>
      <div>
        <span>Stuff profile</span>
        <h2>{{ title }}</h2>
      </div>
      <div class="overall" :data-tone="stuffGradeTone(overallScore)">
        <strong>{{ number(overallScore, 1) }}</strong>
        <b>{{ stuffLetterGrade(overallScore) }}</b>
        <small>Stuff+</small>
      </div>
    </header>

    <div v-if="rows.length" class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Pitch</th><th>Usage</th><th>Stuff+</th><th>{{ stuffGradeLabel }}</th>
            <template v-if="showLocation"><th>Location+</th><th>L-Grade</th></template>
            <th>Velo</th><th>IVB</th><th>HB</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.Pitch)">
            <td><i :style="{ background: getPitchColor(String(row.Pitch)) }" />{{ row.Pitch }}</td>
            <td>{{ number(row.usage_pct, 1) }}%</td>
            <td class="score">{{ number(row.stuff_plus, 1) }}</td>
            <td><b class="grade" :data-tone="stuffGradeTone(row.stuff_plus)">{{ stuffLetterGrade(row.stuff_plus) }}</b></td>
            <template v-if="showLocation">
              <td class="score location-score">{{ number(locationScore(row.Pitch), 1) }}</td>
              <td><b class="grade" :data-tone="locationGradeTone(locationScore(row.Pitch))">{{ locationLetterGrade(locationScore(row.Pitch)) }}</b></td>
            </template>
            <td>{{ number(row.release_speed, 1) }}</td>
            <td>{{ signed(row.ivb) }}</td>
            <td>{{ signed(row.hb) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="empty">{{ loading ? 'Calculating Stuff profile…' : 'No Stuff score is available for this sample.' }}</p>
    <footer v-if="rows.length">
      <span>{{ totalPitches.toLocaleString() }} pitches · {{ rows.length }} pitch types</span>
      <span>{{ scoreSource }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import type { AnalysisResponse, LocationPitchTypeRow } from '~/types/api'
import { locationGradeTone, locationLetterGrade } from '~/utils/locationGrades'
import { getPitchColor } from '~/utils/pitchColors'
import { stuffGradeTone, stuffLetterGrade } from '~/utils/stuffGrades'

const props = withDefaults(defineProps<{
  payload: AnalysisResponse | null
  title?: string
  compact?: boolean
  loading?: boolean
  locationRows?: LocationPitchTypeRow[]
  stuffGradeLabel?: string
  largeText?: boolean
}>(), {
  title: 'Arsenal Stuff+',
  compact: false,
  loading: false,
  locationRows: () => [],
  stuffGradeLabel: 'Grade',
  largeText: false
})

const rows = computed(() => (props.payload?.tables.stuff_scores?.rows || []).filter((row) => {
  const pitch = String(row.Pitch ?? row.pitch_name ?? '').trim().toLowerCase()
  return pitch !== 'pitch out' && pitch !== 'pitchout' && pitch !== 'po'
}))
const summary = computed(() => new Map((props.payload?.summary || []).map((metric) => [metric.key, metric.value])))
const overallScore = computed(() => summary.value.get('stuff_plus'))
const totalPitches = computed(() => rows.value.reduce((sum, row) => sum + (Number(row.pitches) || 0), 0) || Number(summary.value.get('source_pitches')) || 0)
const scoreSource = computed(() => String(rows.value[0]?.score_source || 'Shape proxy'))
const showLocation = computed(() => props.locationRows.length > 0)
const locationByPitch = computed(() => new Map(props.locationRows.map(row => [pitchKey(row.pitch_name), row.location_plus])))

function locationScore(pitch: unknown) {
  return locationByPitch.value.get(pitchKey(String(pitch || '')))
}

function pitchKey(value: string) {
  return value
    .replace(/^Four-Seam(?: Fastball)?$/i, '4-Seam')
    .replace(/^4-Seam Fastball$/i, '4-Seam')
    .replace(/^Split-Finger$/i, 'Splitter')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
}

function number(value: unknown, digits: number) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : '—'
}

function signed(value: unknown) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? `${parsed > 0 ? '+' : ''}${parsed.toFixed(1)}` : '—'
}
</script>

<style scoped>
.stuff-card { overflow: hidden; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); box-shadow: var(--shadow-sm); }
.stuff-card > header { min-height: 88px; display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--color-border); padding: 15px 18px; background: linear-gradient(135deg, color-mix(in srgb, var(--color-accent) 7%, transparent), transparent 65%); }
header span { color: var(--color-accent); font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
h2 { margin: 4px 0 0; color: var(--color-text); font-size: 20px; }
.overall { display: grid; grid-template-columns: auto auto; align-items: center; gap: 0 10px; text-align: right; }
.overall strong { color: var(--color-text); font: 900 28px "Fira Code", monospace; }
.overall b { min-width: 44px; border-radius: 9px; padding: 6px 8px; color: var(--grade-color); background: color-mix(in srgb, var(--grade-color) 13%, transparent); font: 900 16px "Fira Code", monospace; text-align: center; }
.overall small { grid-column: 1 / -1; color: var(--color-muted-text); font-size: 10px; font-weight: 850; text-transform: uppercase; }
[data-tone="elite"] { --grade-color: #54d68c; } [data-tone="plus"] { --grade-color: #9dd56e; } [data-tone="average"] { --grade-color: #f1b449; } [data-tone="below"] { --grade-color: #ef6c67; } [data-tone="neutral"] { --grade-color: #94a3b8; }
.table-scroll { width: 100%; overflow-x: auto; }
table { width: 100%; min-width: 660px; border-collapse: collapse; }
.with-location table { min-width: 920px; }
th, td { border-bottom: 1px solid var(--color-border); padding: 11px 14px; text-align: right; white-space: nowrap; }
th { color: var(--color-muted-text); font-size: 10px; font-weight: 900; text-transform: uppercase; }
td { color: var(--color-muted-text); font: 700 12px "Fira Code", monospace; }
th:first-child, td:first-child { text-align: left; }
td:first-child { display: flex; align-items: center; gap: 9px; color: var(--color-text); font-family: inherit; font-weight: 850; }
td:first-child i { width: 9px; height: 9px; flex: 0 0 auto; border-radius: 50%; }
td.score { color: var(--color-accent); font-weight: 900; }
.location-score { color: #ef9f3b; }
.grade { display: inline-grid; min-width: 36px; place-items: center; border-radius: 7px; padding: 4px 6px; color: var(--grade-color); background: color-mix(in srgb, var(--grade-color) 12%, transparent); }
footer { display: flex; justify-content: space-between; gap: 12px; padding: 10px 14px; color: var(--color-muted-text); font-size: 10px; }
.empty { margin: 0; padding: 24px 18px; color: var(--color-muted-text); }
.compact > header { min-height: 76px; }
.compact th, .compact td { padding-block: 9px; }
.large-text th { font-size: 11px; }
.large-text td { font-size: 13.2px; }
.large-text footer { font-size: 11px; }
@media (max-width: 700px) { footer { display: grid; } }
</style>
