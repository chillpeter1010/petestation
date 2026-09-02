<template>
  <section class="panel-grid">
    <div class="stuff-columns wide-panel">
      <div class="stuff-column">
        <DataTable title="Movement Summary" :table="movement?.tables.movement_summary" />
        <DataTable title="Movement vs League" :table="movement?.tables.movement_league_comparison" />
        <DataTable title="Run Values by Pitch Type" :table="movement?.tables.run_values_by_pitch_type" />
      </div>
      <div class="stuff-column">
        <MovementChart
          v-model:mode="movementChartMode"
          :scatter-rows="movementScatterRows"
          :summary-rows="movementUsageRows"
          :league-rows="movement?.tables.movement_league_comparison.rows || []"
          allow-stuff-color
          :stuff-color-loading="loading"
          :pitcher-hand="pitcherHand"
          @request-stuff-colors="emit('load-pitch-stuff')"
        />
        <StuffArsenalTable
          :payload="props.stuffScore"
          title="Season Stuff+ by Pitch"
          :loading="props.stuffScoreLoading"
        />
        <section class="consistency-panel">
          <header>
            <div>
              <span>Pitch-level distribution</span>
              <h2>Stuff+ consistency</h2>
            </div>
            <small>{{ metricValue('pitch_stuff_coverage') }} cached pitches</small>
          </header>
          <div class="consistency-metrics">
            <div><span>Mean</span><strong>{{ metricValue('pitch_stuff_mean') }}</strong></div>
            <div><span>SD</span><strong>{{ metricValue('pitch_stuff_sd') }}</strong></div>
            <div><span>SE</span><strong>{{ metricValue('pitch_stuff_se') }}</strong></div>
          </div>
          <p>SD describes pitch-to-pitch variation; SE describes uncertainty around the estimated mean.</p>
          <DataTable
            title="Stuff+ variability by pitch type"
            :table="props.stuffScore?.tables.stuff_variability"
            :max-rows="14"
          />
        </section>
      </div>
    </div>
    <div class="location-workspace wide-panel">
      <div class="location-left">
        <HeatmapBlendControl v-model="heatmapBlend" />
        <StrikeZoneScatter
          class="location-main"
          :points="pitchLocationPoints"
          :total-pitches="filteredTotal"
          :selected-key="selectedPitchKey"
          :heatmap-blend="heatmapBlend"
          @select-point="selectedPitch = $event"
        />
      </div>
      <aside class="location-side">
        <SummaryCards :metrics="snapshotMetrics" />
        <section class="stuff-filters location-filters">
          <label>
            Stand
            <CheckboxDropdown v-model="stand" :options="standOptions" />
          </label>
          <label>
            Count
            <CheckboxDropdown v-model="count" :options="countOptions" />
          </label>
          <label>
            Pitch
            <CheckboxDropdown v-model="pitch" :options="pitchOptions" />
          </label>
          <label>
            Pitch Result
            <CheckboxDropdown v-model="pitchResult" :options="pitchResultOptions" />
          </label>
          <label>
            In Play Result
            <CheckboxDropdown v-model="inPlayResult" :options="inPlayResultOptions" />
          </label>
          <label>
            PA Result
            <CheckboxDropdown v-model="paResult" :options="paResultOptions" />
          </label>
          <label>
            Paired Catcher
            <CheckboxDropdown v-model="catcher" :options="catcherOptions" />
          </label>
          <span class="filter-status">{{ loading ? 'Updating Stuff view' : `${filteredTotal || 0} filtered pitches` }}</span>
        </section>
      </aside>
    </div>
    <section class="selected-pitch-panel wide-panel">
      <header>
        <div>
          <h2>Selected Pitch</h2>
          <p>{{ selectedPitch ? selectedPitchLabel : 'Click a pitch in the location chart.' }}</p>
        </div>
        <button v-if="selectedPitchVideoUrl" class="video-button" type="button" @click="emit('open-video')">Open Video</button>
      </header>
      <dl class="pitch-detail-grid">
        <div v-for="field in selectedPitchFields" :key="field.key">
          <dt>{{ field.label }}</dt>
          <dd>{{ field.value }}</dd>
        </div>
      </dl>
      <p v-if="selectedPitch && !selectedPitchVideoUrl" class="muted-note">No video mapping is available for this pitch yet.</p>
    </section>
    <section class="panel-section wide-panel">
      <header class="toggle-header">
        <div>
          <h2>Swing Timing / Miss Distance</h2>
        </div>
        <label class="toggle-control">
          <input v-model="showTiming" type="checkbox">
          Show Timing
        </label>
      </header>
      <template v-if="showTiming">
        <p v-if="timingLoading" class="muted-note">Loading timing data...</p>
        <SummaryCards :metrics="timing?.summary || []" />
        <DataTable title="Pitch Timing Coverage" :table="timing?.tables.timing_by_pitch" />
      </template>
      <p v-else class="muted-note">Enable timing to load swing timing and miss distance data.</p>
    </section>
  </section>
</template>

<script setup lang="ts">
import type { AnalysisResponse, MetricItem } from '~/types/api'

type SelectOption = { value: string; label: string }

const stand = defineModel<string>('stand', { required: true })
const count = defineModel<string>('count', { required: true })
const pitch = defineModel<string>('pitch', { required: true })
const pitchResult = defineModel<string>('pitchResult', { required: true })
const inPlayResult = defineModel<string>('inPlayResult', { required: true })
const paResult = defineModel<string>('paResult', { required: true })
const catcher = defineModel<string>('catcher', { required: true })
const movementChartMode = defineModel<'scatter' | 'average'>('movementChartMode', { required: true })
const heatmapBlend = defineModel<number>('heatmapBlend', { required: true })
const selectedPitch = defineModel<Record<string, unknown> | null>('selectedPitch', { required: true })
const showTiming = defineModel<boolean>('showTiming', { required: true })

const emit = defineEmits<{
  'open-video': []
  'load-pitch-stuff': []
}>()

const props = defineProps<{
  movement: AnalysisResponse | null
  stuffScore: AnalysisResponse | null
  stuffScoreLoading: boolean
  timing: AnalysisResponse | null
  standOptions: string[]
  countOptions: string[]
  pitchOptions: string[]
  pitchResultOptions: SelectOption[]
  inPlayResultOptions: SelectOption[]
  paResultOptions: SelectOption[]
  catcherOptions: string[]
  loading: boolean
  timingLoading: boolean
  filteredTotal: number | null
  snapshotMetrics: MetricItem[]
  pitchDistribution: Array<Record<string, unknown>>
  movementUsageRows: Array<Record<string, unknown>>
  movementScatterRows: Array<Record<string, unknown>>
  pitchLocationPoints: Array<Record<string, unknown>>
  selectedPitchKey: string | null
  selectedPitchLabel: string
  selectedPitchVideoUrl: string
  selectedPitchFields: Array<{ key: string; label: string; value: unknown }>
}>()

const pitcherHand = computed(() => {
  const item = props.movement?.summary.find((metric) => metric.key === 'pitcher_hand')
  const value = String(item?.value || '').toUpperCase()
  return value === 'L' || value === 'R' ? value : 'Unknown'
})

function metricValue(key: string) {
  const metric = props.stuffScore?.summary.find(item => item.key === key)
  const value = metric?.value
  if (value === null || value === undefined || value === '') return '-'
  return typeof value === 'number' ? value.toFixed(1) : String(value)
}
</script>

<style scoped>
.consistency-panel {
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.consistency-panel > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
  padding: 16px 18px;
}

.consistency-panel header span {
  color: var(--color-primary);
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
}

.consistency-panel h2 {
  margin: 4px 0 0;
  color: var(--color-foreground);
  font-size: 20px;
}

.consistency-panel small,
.consistency-panel p {
  color: var(--color-muted-text);
}

.consistency-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-bottom: 1px solid var(--color-border);
}

.consistency-metrics div {
  display: grid;
  gap: 6px;
  padding: 16px 18px;
}

.consistency-metrics div + div {
  border-left: 1px solid var(--color-border);
}

.consistency-metrics span {
  color: var(--color-muted-text);
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
}

.consistency-metrics strong {
  color: var(--color-foreground);
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 24px;
}

.consistency-panel > p {
  margin: 0;
  padding: 12px 18px;
  font-size: 12px;
}

@media (max-width: 680px) {
  .consistency-metrics { grid-template-columns: 1fr; }
  .consistency-metrics div + div { border-left: 0; border-top: 1px solid var(--color-border); }
}
</style>
