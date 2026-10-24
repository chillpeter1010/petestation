<template>
  <section class="outing-tab">
    <section class="filter-card">
      <label class="filter-field outing-select">
        <span>Outing</span>
        <select :value="selectedGamePk || ''" @change="emitSelectedGame(($event.target as HTMLSelectElement).value)">
          <option v-if="!outingRows.length" value="">No outings</option>
          <option
            v-for="outing in outingRows"
            :key="String(outing['Game PK'])"
            :value="String(outing['Game PK'])"
          >
            {{ outing.Label || `${outing.Date} vs ${outing.Opponent}` }}
          </option>
        </select>
      </label>
      <span class="filter-status">{{ outingRows.length.toLocaleString() }} games</span>
    </section>

    <p v-if="loading" class="loading-copy">Loading outing report...</p>

    <template v-else>
      <section class="outing-poster" aria-label="Pitcher outing visual report header">
        <div class="poster-top">
          <div class="poster-identity">
            <h2>{{ posterName }}</h2>
            <p>{{ pitcherHandLabel }} / USA / C: {{ catcherName }}</p>
          </div>
          <div class="poster-brand">
            <strong>Pete<span>hub</span></strong>
          </div>
        </div>

        <p class="poster-subtitle">Pitcher Performance: {{ outingDate }} @ {{ outingOpponent }}</p>

        <div class="poster-line">
          {{ outingLine }}
        </div>

        <div class="poster-main-grid">
          <div class="poster-left">
            <div class="poster-box start-grade">
              <div class="poster-box-title">Start</div>
              <strong>{{ gameScore }}</strong>
              <small>Game Score</small>
            </div>
            <div class="poster-box model-grade">
              <div class="poster-box-title">Models</div>
              <div class="model-cols">
                <span><small>Stuff+</small><b>{{ modelGrades.stuff.grade }}</b></span>
                <span><small>Location+</small><b>{{ modelGrades.locations }}</b></span>
              </div>
            </div>
            <div class="poster-box fastball-box">
              <div class="poster-box-title">Primary Fastball: <b>{{ primaryFastball.Pitch || '-' }}</b></div>
              <div class="fastball-metrics">
                <span v-for="item in posterFastballItems" :key="item.key">
                  <small>{{ item.label }}</small>
                  <b>{{ item.value }}</b>
                </span>
              </div>
            </div>
          </div>

          <div class="poster-usage">
            <div class="usage-title">Usage</div>
            <div class="usage-head">
              <span>vs LHB%</span>
              <span>vs RHB%</span>
            </div>
            <div class="usage-board">
              <div v-for="row in posterUsage.rows" :key="row.pitch" class="usage-row-poster">
                <small :class="directionClass(row.left.direction)">
                  {{ formatPercent(row.left.usage) }}
                </small>
                <i class="usage-bar left" :style="{ width: row.left.width, backgroundColor: colorForPitch(row.pitch) }" />
                <div class="usage-label">
                  <b :style="{ color: colorForPitch(row.pitch) }">{{ posterPitchLabel(row.pitch) }}</b>
                  <span>{{ formatPercent(row.usage) }}</span>
                </div>
                <i class="usage-bar right" :style="{ width: row.right.width, backgroundColor: colorForPitch(row.pitch) }" />
                <small :class="directionClass(row.right.direction)">
                  {{ formatPercent(row.right.usage) }}
                </small>
              </div>
            </div>
            <p>Split usage by batter side</p>
          </div>
        </div>
      </section>

      <section class="poster-analysis-board">
        <section class="outing-middle-grid">
          <MovementChart
            v-model:mode="movementMode"
            title="Movement"
            :scatter-rows="movementScatterRows"
            :summary-rows="movementAverageRows"
            :league-rows="movementAverageLeagueRows"
            :pitcher-hand="pitcherHand"
            :show-profile-info="false"
            allow-stuff-color
          />
          <StrikeZoneScatter
            class="poster-zone-chart"
            title="Locations vs LHB"
            :points="locationByStand.L"
            :selected-key="selectedOutingPitchKey"
            compact
            :point-scale="1.25"
            :plot-scale="1.2"
            :point-opacity="0.78"
            @select-point="selectOutingPitch"
          />
          <StrikeZoneScatter
            class="poster-zone-chart"
            title="Locations vs RHB"
            :points="locationByStand.R"
            :selected-key="selectedOutingPitchKey"
            compact
            :point-scale="1.25"
            :plot-scale="1.2"
            :point-opacity="0.78"
            @select-point="selectOutingPitch"
          />
        </section>

        <StuffArsenalTable
          :payload="stuffScorePayload"
          :location-rows="locationScorePayload?.outing_pitch_types || []"
          title="Outing Stuff+ / Location+ by Pitch"
          stuff-grade-label="S-Grade"
          compact
          large-text
          :loading="modelScoreLoading"
        />

        <DataTable
          title="Pitch Type Metrics"
          :table="report?.tables.pitch_type_metrics"
          :max-rows="12"
        />
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import type { AnalysisResponse, LocationPitcherResponse } from '~/types/api'
import { locationLetterGrade } from '~/utils/locationGrades'
import { stuffLetterGrade } from '~/utils/stuffGrades'

const props = defineProps<{
  outings: AnalysisResponse | null
  report: AnalysisResponse | null
  selectedGamePk: number | null
  loading?: boolean
  pitcherName?: string
  year: number
  pitcherId: number | null
}>()

const emit = defineEmits<{
  'update:selectedGamePk': [value: number | null]
  'select-pitch': [pitch: Record<string, unknown>]
}>()

const movementMode = ref<'scatter' | 'average'>('average')
const api = useApi()
const modelScoreLoading = ref(false)
const selectedOutingPitch = ref<Record<string, unknown> | null>(null)
const stuffScorePayload = ref<AnalysisResponse | null>(null)
const locationScorePayload = ref<LocationPitcherResponse | null>(null)
let modelScoreRequestId = 0

const outingRows = computed(() => props.outings?.tables.outings?.rows || [])
const selectedOutingPitchKey = computed(() => selectedOutingPitch.value ? pitchPointKey(selectedOutingPitch.value) : null)
const pitchMixRows = computed(() => {
  const rows = props.report?.charts.pitch_mix
  return Array.isArray(rows) ? rows.filter((row): row is Record<string, unknown> => row && typeof row === 'object' && !Array.isArray(row)) : []
})
const usageByStandRows = computed(() => {
  const rows = props.report?.charts.usage_by_stand
  return Array.isArray(rows) ? rows.filter((row): row is Record<string, unknown> => row && typeof row === 'object' && !Array.isArray(row)) : []
})
const locationByStand = computed(() => {
  const value = props.report?.charts.location_by_stand
  const record = value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
  return {
    L: rowsFrom(record.L),
    R: rowsFrom(record.R)
  }
})
const primaryFastball = computed(() => {
  const value = props.report?.charts.primary_fastball
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
})
const movementScatterRows = computed(() => rowsFrom(props.report?.charts.movement_scatter))
const movementSummaryRows = computed(() => props.report?.tables.movement_summary?.rows || [])
const movementLeagueRows = computed(() => props.report?.tables.movement_league_comparison?.rows || [])
const movementAverageRows = computed(() => {
  const rows = props.report?.tables.season_movement_summary?.rows || []
  return rows.length ? rows : movementSummaryRows.value
})
const movementAverageLeagueRows = computed(() => {
  const rows = props.report?.tables.season_movement_league_comparison?.rows || []
  return rows.length ? rows : movementLeagueRows.value
})
const pitchTypeMetricRows = computed(() => props.report?.tables.pitch_type_metrics?.rows || [])
const pitcherHand = computed(() => {
  const value = props.report?.charts.pitcher_hand
  return typeof value === 'string' ? value : 'Unknown'
})
const summaryByKey = computed(() => {
  const map = new Map<string, unknown>()
  for (const metric of props.report?.summary || []) {
    map.set(metric.key, metric.value)
  }
  return map
})
const posterName = computed(() => {
  const text = String(props.pitcherName || '').trim()
  return text || 'Pitcher'
})
const outingDate = computed(() => String(summaryByKey.value.get('date') || '-'))
const outingOpponent = computed(() => String(summaryByKey.value.get('opponent') || '-'))
const catcherName = computed(() => String(summaryByKey.value.get('catcher_name') || '-'))
const pitcherHandLabel = computed(() => {
  if (pitcherHand.value === 'R') {
    return 'RHP'
  }
  if (pitcherHand.value === 'L') {
    return 'LHP'
  }
  return 'P'
})
const outingLine = computed(() => {
  const ip = summaryByKey.value.get('ip') || '-'
  const pitches = summaryByKey.value.get('pitches') || '-'
  const whiffs = summaryByKey.value.get('whiffs') || 0
  const hits = summaryByKey.value.get('hits') || 0
  const earnedRuns = summaryByKey.value.get('earned_runs')
  const walks = summaryByKey.value.get('walks') || 0
  const strikeouts = summaryByKey.value.get('strikeouts') || 0
  const csw = summaryByKey.value.get('csw_pct')
  return `${ip} IP, ${formatPlain(earnedRuns)} ER, ${hits} Hit, ${walks} BBs, ${strikeouts} K - ${whiffs} Whiffs, ${formatPercent(csw)} CSW, ${pitches} Pitches`
})
const gameScore = computed(() => {
  const gameScoreValue = Number(summaryByKey.value.get('game_score'))
  if (Number.isFinite(gameScoreValue)) {
    return String(Math.round(gameScoreValue))
  }
  const outs = outsFromIp(summaryByKey.value.get('ip'))
  const hits = Number(summaryByKey.value.get('hits'))
  const walks = Number(summaryByKey.value.get('walks'))
  const strikeouts = Number(summaryByKey.value.get('strikeouts'))
  const whiffs = Number(summaryByKey.value.get('whiffs'))
  const csw = Number(summaryByKey.value.get('csw_pct'))
  const pitches = Number(summaryByKey.value.get('pitches'))

  let fallbackScore = 50
  fallbackScore += outs * 1.35
  fallbackScore += Number.isFinite(strikeouts) ? strikeouts * 2.0 : 0
  fallbackScore += Number.isFinite(whiffs) ? whiffs * 0.55 : 0
  fallbackScore += Number.isFinite(csw) ? (csw - 27) * 1.2 : 0
  fallbackScore -= Number.isFinite(hits) ? hits * 2.2 : 0
  fallbackScore -= Number.isFinite(walks) ? walks * 3.5 : 0

  if (outs >= 15) fallbackScore += 2
  if (outs >= 18) fallbackScore += 3
  if (outs > 0 && outs < 12) fallbackScore -= (12 - outs) * 2.2
  if (Number.isFinite(walks) && walks === 0) fallbackScore += 3
  if (Number.isFinite(pitches) && pitches > 95 && outs < 18) fallbackScore -= 3

  return Number.isFinite(fallbackScore) ? String(Math.round(fallbackScore)) : '-'
})
const modelGrades = computed(() => {
  const stuffScore = weightedTableScore(stuffScorePayload.value, 'stuff_scores', 'stuff_plus')
    ?? weightedTableScore(stuffScorePayload.value, 'stuff_scores', 'shape_proxy')
    ?? outingStuffFallbackScore.value
  const currentOutingLocation = locationScorePayload.value?.outings.find(
    row => row.game_pk === props.selectedGamePk
  )?.location_plus
  return {
    stuff: {
      grade: modelScoreLoading.value ? '...' : stuffLetterGrade(stuffScore)
    },
    locations: modelScoreLoading.value ? '...' : locationLetterGrade(currentOutingLocation)
  }
})
const posterFastballItems = computed(() => [
  { key: 'velo', label: 'Velo', value: valueOrDash(primaryFastball.value.Velo, 1) },
  { key: 'ext', label: 'Ext', value: valueOrDash(primaryFastball.value.Ext, 1, "'") },
  { key: 'ivb', label: 'IVB', value: valueOrDash(primaryFastball.value.IVB, 1, '"') },
  { key: 'hb', label: 'HB', value: valueOrDash(primaryFastball.value.HB, 1, '"') }
])
const posterUsage = computed(() => {
  const overall = pitchMixRows.value.map((row) => {
    const pitch = String(row.pitch || '')
    return {
      pitch,
      usage: Number(row.rate || 0) * 100
    }
  })
  const usageValues = [
    ...usageByStandRows.value.map((row) => Number(row.usage_pct || 0))
  ].filter((value) => Number.isFinite(value))
  const usageCap = Math.max(10, Math.ceil(Math.max(...usageValues, 0) / 10) * 10)
  const scaledWidth = (usage: number) => usage <= 0 ? '0%' : `${Math.max(3, Math.min(100, (usage / usageCap) * 100))}%`
  const splitValue = (stand: 'L' | 'R', pitch: string) => {
    const pitchKey = normalizePosterPitchKey(pitch)
    const row = usageByStandRows.value.find((item) => item.stand === stand && normalizePosterPitchKey(String(item.Pitch || '')) === pitchKey)
    const usage = Number(row?.usage_pct ?? 0)
    const diff = Number(row?.usage_diff ?? 0)
    const direction = String(row?.direction || 'flat')
    return {
      usage,
      diff,
      direction,
      width: scaledWidth(usage)
    }
  }
  return {
    overall,
    rows: overall.map((base) => ({
      ...base,
      left: splitValue('L', base.pitch),
      right: splitValue('R', base.pitch)
    }))
  }
})
const outingStuffFallbackScore = computed(() => {
  let weightedSum = 0
  let weightTotal = 0
  for (const row of pitchTypeMetricRows.value) {
    const pitches = firstFiniteNumber(row, ['Pitches', 'pitches', '#', 'Count'])
    const velo = firstFiniteNumber(row, ['Velo', 'release_speed', 'velo'])
    const ivb = firstFiniteNumber(row, ['IVB', 'ivb', 'v_break'])
    const hb = firstFiniteNumber(row, ['HB', 'hb', 'h_break'])
    if (!Number.isFinite(pitches) || pitches <= 0) {
      continue
    }
    const score = 100
      + (Number.isFinite(velo) ? velo - 90 : 0)
      + (Number.isFinite(ivb) ? Math.abs(ivb) / 2.5 : 0)
      + (Number.isFinite(hb) ? Math.abs(hb) / 3 : 0)
    weightedSum += score * pitches
    weightTotal += pitches
  }
  return weightTotal > 0 ? weightedSum / weightTotal : null
})
const outingLocationFallbackScore = computed(() => {
  const zone = Number(summaryByKey.value.get('zone_pct'))
  const csw = Number(summaryByKey.value.get('csw_pct'))
  if (!Number.isFinite(zone) && !Number.isFinite(csw)) {
    return null
  }
  return 82
    + (Number.isFinite(zone) ? zone * 0.45 : 0)
    + (Number.isFinite(csw) ? csw * 0.3 : 0)
})

watch(
  () => [props.year, props.pitcherId, outingDate.value, props.selectedGamePk] as const,
  async ([year, pitcherId, date]) => {
    const currentRequestId = ++modelScoreRequestId
    stuffScorePayload.value = null
    locationScorePayload.value = null

    const hasOutingDate = isDateString(date)
    const gamePk = Number(props.selectedGamePk)
    const hasGamePk = Number.isFinite(gamePk) && gamePk > 0
    if (!pitcherId || !Number.isFinite(year) || (!hasOutingDate && !hasGamePk)) {
      return
    }

    modelScoreLoading.value = true
    try {
      const params = {
        year,
        pitcherId: Number(pitcherId),
        startDate: hasOutingDate ? date : undefined,
        endDate: hasOutingDate ? date : undefined,
        gamePk: hasGamePk ? gamePk : undefined
      }
      const [stuffResult, locationResult] = await Promise.allSettled([
        api.stuffScore(params),
        api.locationPitcher({ year, pitcherId: Number(pitcherId), gamePk: hasGamePk ? gamePk : undefined })
      ])

      if (currentRequestId === modelScoreRequestId) {
        stuffScorePayload.value = stuffResult.status === 'fulfilled' ? stuffResult.value : null
        locationScorePayload.value = locationResult.status === 'fulfilled' ? locationResult.value : null
      }
      if (stuffResult.status === 'rejected') {
        console.warn('Failed to load outing Stuff+ score', stuffResult.reason)
      }
      if (locationResult.status === 'rejected') {
        console.warn('Failed to load outing Location+ score', locationResult.reason)
      }
    } catch (error) {
      console.warn('Failed to load outing model scores', error)
      if (currentRequestId === modelScoreRequestId) {
        stuffScorePayload.value = null
        locationScorePayload.value = null
      }
    } finally {
      if (currentRequestId === modelScoreRequestId) {
        modelScoreLoading.value = false
      }
    }
  },
  { immediate: true }
)

watch(() => props.selectedGamePk, () => {
  selectedOutingPitch.value = null
})

function posterPitchLabel(pitch: string) {
  if (pitch === 'Four-Seam' || pitch === '4-Seam') {
    return 'FF'
  }
  if (pitch === 'Sinker') {
    return 'SI'
  }
  if (pitch === 'Cutter') {
    return 'FC'
  }
  if (pitch === 'Slider') {
    return 'SL'
  }
  if (pitch === 'Sweeper') {
    return 'ST'
  }
  if (pitch === 'Changeup') {
    return 'CH'
  }
  if (pitch === 'Curveball') {
    return 'CU'
  }
  if (pitch === 'Splitter') {
    return 'FS'
  }
  return pitch
}

function normalizePosterPitchKey(pitch: string) {
  return pitch
    .replace(/^Four-Seam$/i, '4-Seam')
    .replace(/^4-Seam Fastball$/i, '4-Seam')
    .replace(/^Split-Finger$/i, 'Splitter')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
}

const pitchColors: Record<string, string> = {
  '4-Seam': '#c43c32',
  'Four-Seam': '#c43c32',
  Sinker: '#e8892f',
  Cutter: '#7b5b3f',
  Curveball: '#4f86a8',
  Slider: '#f3cf72',
  Splitter: '#5aaeb0',
  Changeup: '#69c37d',
  Sweeper: '#b9934f'
}

function emitSelectedGame(value: string) {
  const parsed = Number(value)
  emit('update:selectedGamePk', Number.isFinite(parsed) && parsed > 0 ? parsed : null)
}

function selectOutingPitch(pitch: Record<string, unknown>) {
  selectedOutingPitch.value = pitch
  emit('select-pitch', pitch)
}

function pitchPointKey(point: Record<string, unknown>) {
  return [
    point.game_pk,
    point.at_bat_number,
    point.pitch_number,
    point.plate_x,
    point.plate_z,
    point.pitch_name
  ].map(value => String(value ?? '')).join('|')
}

function rowsFrom(value: unknown) {
  return Array.isArray(value) ? value.filter((row): row is Record<string, unknown> => row && typeof row === 'object' && !Array.isArray(row)) : []
}

function isDateString(value: unknown) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
}

function weightedTableScore(payload: AnalysisResponse | null, tableKey: string, scoreKey: string) {
  const rows = payload?.tables?.[tableKey]?.rows || []
  let weightedSum = 0
  let weightTotal = 0
  for (const row of rows) {
    const score = Number(row[scoreKey])
    const weight = Number(row.pitches ?? row.Pitches ?? 0)
    if (Number.isFinite(score) && Number.isFinite(weight) && weight > 0) {
      weightedSum += score * weight
      weightTotal += weight
    }
  }
  return weightTotal > 0 ? weightedSum / weightTotal : null
}

function firstFiniteNumber(row: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = Number(row[key])
    if (Number.isFinite(value)) {
      return value
    }
  }
  return Number.NaN
}

function colorForPitch(pitch: string) {
  return pitchColors[pitch] || '#94a3b8'
}

function formatPlain(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  return String(value)
}

function formatPercent(value: unknown) {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? `${numberValue.toFixed(1)}%` : '-'
}

function formatDiff(value: unknown) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue) || Math.abs(numberValue) < 0.05) {
    return '0.0%'
  }
  return `${Math.abs(numberValue).toFixed(1)}%`
}

function suffix(value: unknown, unit: string) {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? `${numberValue.toFixed(1)} ${unit}` : '-'
}

function valueOrDash(value: unknown, digits = 1, suffixText = '') {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? `${numberValue.toFixed(digits)}${suffixText}` : '-'
}

function outsFromIp(value: unknown) {
  const text = String(value || '')
  if (!text || text === '-') {
    return 0
  }
  const [inningsText, partialText = '0'] = text.split('.')
  const innings = Number(inningsText)
  const partial = Number(partialText)
  if (!Number.isFinite(innings)) {
    return 0
  }
  return Math.max(0, innings * 3 + (Number.isFinite(partial) ? Math.min(2, partial) : 0))
}

function arrowForDirection(direction: string) {
  if (direction === 'up') {
    return '+'
  }
  if (direction === 'down') {
    return '-'
  }
  return '='
}

function directionClass(direction: string) {
  return {
    up: direction === 'up',
    down: direction === 'down',
    flat: direction !== 'up' && direction !== 'down'
  }
}
</script>

<style scoped>
.outing-tab {
  display: grid;
  gap: 16px;
}

.filter-card {
  display: grid;
  grid-template-columns: minmax(240px, 520px) auto;
  gap: 14px;
  align-items: end;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.filter-field {
  display: grid;
  gap: 7px;
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.filter-field select {
  min-height: 40px;
  border: 1px solid var(--color-border-strong);
  border-radius: 6px;
  padding: 0 12px;
  color: var(--color-foreground);
  background: var(--color-surface);
  font: inherit;
  font-size: 14px;
  text-transform: none;
}

.filter-status {
  color: var(--color-muted-text);
  font-weight: 800;
}

.loading-copy,
.empty-copy {
  margin: 0;
  color: var(--color-muted-text);
}

.outing-poster {
  --poster-cyan: #f5a12b;
  --poster-pink: #ff7a2f;
  --poster-yellow: #f8bd45;
  --poster-panel: #151515;
  --poster-muted: #b8b0a6;
  display: grid;
  gap: 12px;
  overflow: hidden;
  border: 3px solid rgba(245, 161, 43, 0.88);
  border-radius: 8px 8px 0 0;
  padding: 18px 20px 20px;
  color: #f7f8ff;
  background:
    radial-gradient(circle at 88% 0%, rgba(245, 161, 43, 0.2), transparent 34%),
    linear-gradient(180deg, #171717 0%, #111111 100%);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.28);
}

.poster-top {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: start;
}

.poster-identity h2 {
  margin: 0;
  color: #f5a12b;
  font-size: 82px;
  line-height: 0.82;
  font-weight: 900;
  letter-spacing: 0;
}

.poster-identity p,
.poster-subtitle {
  margin: 12px 0 0;
  color: var(--poster-muted);
  font-size: 22px;
  font-weight: 800;
  font-style: italic;
}

.poster-brand {
  display: flex;
  justify-content: flex-end;
  align-items: start;
  min-width: 230px;
  color: #fff;
  text-align: right;
}

.poster-brand strong {
  display: block;
  font-size: 46px;
  line-height: 1;
  font-weight: 900;
}

.poster-brand strong span {
  display: inline-block;
  margin-left: 4px;
  padding: 3px 8px 5px;
  border-radius: 8px;
  color: #111;
  background: var(--poster-cyan);
  font-weight: 900;
}

.poster-subtitle {
  justify-self: center;
  margin-top: -20px;
  color: #d9dbe7;
}

.poster-line {
  border: 3px solid var(--poster-cyan);
  border-radius: 9px;
  padding: 14px 18px;
  color: #fff2d9;
  text-align: center;
  font-size: 30px;
  font-weight: 900;
  letter-spacing: 0.01em;
  box-shadow: inset 0 0 16px rgba(245, 161, 43, 0.14);
}

.poster-main-grid {
  display: grid;
  grid-template-columns: minmax(400px, 0.72fr) minmax(520px, 1.28fr);
  gap: 0;
  align-items: stretch;
}

.poster-left {
  display: grid;
  grid-template-columns: 0.82fr 1.5fr;
  border-left: 3px solid var(--poster-cyan);
  border-bottom: 3px solid var(--poster-cyan);
}

.poster-box {
  position: relative;
  min-height: 122px;
  border-top: 3px solid var(--poster-cyan);
  border-right: 3px solid var(--poster-cyan);
  padding: 22px 24px;
}

.poster-box-title {
  position: absolute;
  top: -24px;
  left: 24px;
  padding: 0 12px;
  color: #fff;
  background: var(--poster-panel);
  font-size: 28px;
  font-weight: 900;
}

.poster-box-title b {
  color: var(--poster-pink);
}

.start-grade strong {
  display: block;
  color: #fff;
  font-size: 86px;
  line-height: 1;
  font-weight: 900;
}

.start-grade small {
  display: block;
  margin-top: 8px;
  color: var(--poster-muted);
  font-size: 20px;
  font-weight: 900;
  text-transform: uppercase;
}

.model-cols,
.fastball-metrics {
  display: grid;
  gap: 18px;
  align-items: end;
}

.model-cols {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.fastball-metrics {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.model-cols span,
.fastball-metrics span {
  display: grid;
  gap: 8px;
  text-align: center;
}

.model-cols small,
.fastball-metrics small {
  color: var(--poster-muted);
  font-size: 19px;
  font-weight: 900;
}

.model-cols b {
  color: var(--poster-pink);
  font-size: 52px;
  line-height: 1;
  font-weight: 900;
}

.model-cols span:first-child b {
  color: #ffd23f;
}

.fastball-box {
  grid-column: 1 / -1;
  min-height: 150px;
}

.fastball-metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  padding-top: 12px;
}

.fastball-metrics b {
  color: #fff;
  font-size: 28px;
  font-weight: 900;
}

.fastball-metrics span:first-child b {
  color: #ff6970;
}

.fastball-metrics span:nth-child(4) b {
  color: #79d5df;
}

.poster-usage {
  position: relative;
  border-top: 3px solid var(--poster-cyan);
  border-right: 3px solid var(--poster-cyan);
  border-bottom: 3px solid var(--poster-cyan);
  padding: 18px 24px 18px 36px;
}

.usage-title {
  position: absolute;
  top: -24px;
  left: 44%;
  padding: 0 16px;
  color: #fff;
  background: var(--poster-panel);
  font-size: 28px;
  font-weight: 900;
}

.usage-head {
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin: 0 0 8px;
  color: var(--poster-muted);
  font-size: 15px;
  font-weight: 900;
  text-align: center;
}

.usage-board {
  display: grid;
  gap: 10px;
}

.usage-row-poster {
  display: grid;
  grid-template-columns: 58px minmax(112px, 1fr) 126px minmax(112px, 1fr) 58px;
  gap: 10px;
  align-items: center;
  min-height: 46px;
}

.usage-row-poster small {
  color: var(--poster-muted);
  font-size: 15px;
  font-weight: 900;
}

.usage-bar {
  display: block;
  height: 36px;
  min-width: 12px;
  border-radius: 5px;
  opacity: 0.95;
}

.usage-bar.left {
  justify-self: end;
}

.usage-row-poster small.up {
  color: var(--poster-pink);
}

.usage-row-poster small.down {
  color: #f1a6e9;
}

.usage-row-poster small.flat {
  color: var(--poster-yellow);
}

.usage-label {
  display: flex;
  gap: 8px;
  align-items: baseline;
  justify-content: center;
  min-width: 0;
  font-size: 22px;
  font-weight: 900;
}

.usage-label span {
  color: var(--poster-pink);
}

.poster-usage p {
  position: absolute;
  right: 14px;
  bottom: 10px;
  margin: 0;
  color: var(--poster-muted);
  font-size: 11px;
  font-weight: 800;
  text-align: right;
}

.report-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(260px, 0.7fr);
  gap: 16px;
  align-items: start;
}

.split-grid,
.movement-report-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  align-items: start;
}

.outing-middle-grid {
  --poster-cyan: #f5a12b;
  display: grid;
  grid-template-columns: minmax(360px, 1.1fr) repeat(2, minmax(260px, 0.95fr));
  gap: 0;
  align-items: stretch;
}

.poster-analysis-board {
  --poster-cyan: #f5a12b;
  display: grid;
  gap: 0;
  margin-top: -16px;
  overflow: hidden;
  border: 3px solid rgba(245, 161, 43, 0.88);
  border-top: 0;
  border-radius: 0 0 8px 8px;
  background:
    radial-gradient(circle at 88% 0%, rgba(245, 161, 43, 0.12), transparent 32%),
    linear-gradient(180deg, #171717 0%, #111111 100%);
}

.poster-analysis-board :deep(.movement-chart),
.poster-analysis-board :deep(.zone-chart) {
  width: 100%;
  height: 100%;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.poster-analysis-board :deep(.movement-chart),
.poster-analysis-board :deep(.zone-chart:not(:last-child)) {
  border-right: 3px solid rgba(245, 161, 43, 0.88);
}

.poster-analysis-board :deep(.movement-chart .chart-header),
.poster-analysis-board :deep(.zone-chart .chart-header),
.poster-analysis-board :deep(.zone-chart header) {
  min-height: 74px;
  display: flex;
  align-items: center;
  border-bottom-color: rgba(245, 161, 43, 0.48);
}

.poster-analysis-board :deep(.movement-chart .profile-wrap),
.poster-analysis-board :deep(.zone-chart .zone-body),
.poster-analysis-board :deep(.zone-chart .plot-wrap) {
  background: transparent;
}

.poster-analysis-board :deep(.movement-chart .profile-bg),
.poster-analysis-board :deep(.movement-chart .profile-center-bg),
.poster-analysis-board :deep(.zone-chart .plot-bg) {
  fill: #151515;
}

.poster-analysis-board :deep(.poster-zone-chart .plot-wrap) {
  padding-top: 34px;
  padding-bottom: 18px;
}

.poster-analysis-board :deep(.poster-zone-chart svg) {
  transform: translateY(14px);
}

.poster-analysis-board :deep(.data-table-wrap) {
  border: 0;
  border-top: 3px solid rgba(245, 161, 43, 0.88);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.poster-analysis-board :deep(.stuff-card) {
  border: 0;
  border-top: 3px solid rgba(245, 161, 43, 0.88);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.poster-analysis-board :deep(.data-table-wrap table) {
  font-size: 18px;
}

.poster-analysis-board :deep(.data-table-wrap th),
.poster-analysis-board :deep(.data-table-wrap td) {
  padding: 12px 16px;
}

.poster-analysis-board :deep(.data-table-wrap .table-header h2) {
  font-size: 22px;
}

.poster-analysis-board :deep(.data-table-wrap .table-header span) {
  font-size: 18px;
}

.report-panel {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.panel-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}

.panel-header h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

.panel-header span {
  color: var(--color-muted-text);
  font-size: 13px;
}

.mix-list {
  display: grid;
  gap: 12px;
  padding: 14px;
}

.mix-row {
  display: grid;
  gap: 6px;
}

.mix-row div:first-child {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: var(--color-text);
  font-size: 13px;
}

.mix-row strong {
  color: var(--color-foreground);
}

.mix-track {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-muted);
}

.mix-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--color-primary);
}

.usage-split-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 14px;
}

.usage-card {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 12px;
  background: color-mix(in srgb, var(--color-surface) 92%, var(--color-muted));
}

.usage-card h3 {
  margin: 0 0 10px;
  color: var(--color-foreground);
  font-size: 14px;
}

.usage-list {
  display: grid;
  gap: 8px;
}

.usage-row {
  display: grid;
  grid-template-columns: 12px minmax(64px, 1fr) 52px 58px;
  gap: 8px;
  align-items: center;
  color: var(--color-text);
  font-size: 13px;
}

.pitch-dot {
  width: 9px;
  height: 9px;
  border: 1px solid rgba(0, 0, 0, 0.6);
  border-radius: 999px;
}

.usage-row strong {
  color: var(--color-foreground);
}

.usage-row b {
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 12px;
  text-align: right;
}

.usage-row b.up {
  color: #ef6b61;
}

.usage-row b.down {
  color: #6fb4de;
}

.usage-row b.flat {
  color: var(--color-muted-text);
}

.primary-fastball {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.primary-fastball > strong {
  color: var(--color-primary);
  font-size: 24px;
  line-height: 1;
}

.primary-fastball dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
}

.primary-fastball dt {
  color: var(--color-muted-text);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.primary-fastball dd {
  margin: 3px 0 0;
  color: var(--color-foreground);
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 16px;
}

@media (max-width: 860px) {
  .filter-card,
  .report-grid,
  .split-grid,
  .outing-middle-grid,
  .movement-report-grid,
  .usage-split-grid {
    grid-template-columns: 1fr;
  }
}
</style>
