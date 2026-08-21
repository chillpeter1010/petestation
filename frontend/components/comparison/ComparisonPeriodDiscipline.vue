<template>
  <section class="period-module">
    <header class="module-header">
      <div>
        <h2>Discipline</h2>
        <p>Reusable discipline panels for each selected period.</p>
      </div>
      <label>
        Heatmap Blend
        <input v-model.number="heatmapBlend" type="range" min="0" max="1" step="0.1">
        <span>{{ Math.round(heatmapBlend * 100) }}%</span>
      </label>
    </header>
    <div class="discipline-grid">
      <section class="period-side">
        <h3>Period A</h3>
        <DisciplinePanelBoard
          :heatmap-blend="heatmapBlend"
          :initial-group="boardInitialGroup"
          :pitch-result-panels="leftPanels.pitchResult"
          :pa-result-panels="leftPanels.paResult"
          :batted-ball-panels="leftPanels.battedBall"
          :count-situation-panels="leftPanels.countSituation"
          :count-swing-panels="leftPanels.countSwing"
          :exact-count-panels="leftPanels.exactCount"
        />
      </section>
      <section class="period-side">
        <h3>Period B</h3>
        <DisciplinePanelBoard
          :heatmap-blend="heatmapBlend"
          :initial-group="boardInitialGroup"
          :pitch-result-panels="rightPanels.pitchResult"
          :pa-result-panels="rightPanels.paResult"
          :batted-ball-panels="rightPanels.battedBall"
          :count-situation-panels="rightPanels.countSituation"
          :count-swing-panels="rightPanels.countSwing"
          :exact-count-panels="rightPanels.exactCount"
        />
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { DisciplinePanel, DisciplinePanelMetric } from '~/components/discipline/DisciplineZonePanel.vue'

type PeriodDisciplinePayload = {
  panel_groups?: Record<string, unknown>
  total?: number
}

const props = defineProps<{
  left: PeriodDisciplinePayload
  right: PeriodDisciplinePayload
  pitchFilter?: string
  groupFilter?: string
}>()

const heatmapBlend = ref(0)
const leftPanels = computed(() => panelSets(props.left))
const rightPanels = computed(() => panelSets(props.right))
const boardInitialGroup = computed(() => {
  return props.groupFilter === 'result' || props.groupFilter === 'discipline' || props.groupFilter === 'situation'
    ? props.groupFilter
    : 'All'
})

function toRows(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((row): row is Record<string, unknown> => row && typeof row === 'object' && !Array.isArray(row)) : []
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function normalizePanel(panel: Record<string, unknown>) {
  const rows = filterRows(toRows(panel.rows))
  const hasPitchFilter = selectedPitchFilters().length > 0
  return {
    key: String(panel.key || ''),
    label: String(panel.label || panel.key || ''),
    rows,
    pitches: rows.length,
    metrics: hasPitchFilter ? [] : toRows(panel.metrics).map(normalizeMetric),
    pitchMix: hasPitchFilter ? [] : toRows(panel.pitch_mix).map((pitch) => ({
      pitch: String(pitch.pitch || 'Unknown'),
      pitches: Number.isFinite(Number(pitch.pitches)) ? Number(pitch.pitches) : undefined,
      count: Number.isFinite(Number(pitch.count)) ? Number(pitch.count) : undefined,
      rate: Number.isFinite(Number(pitch.rate)) ? Number(pitch.rate) : undefined
    }))
  } satisfies DisciplinePanel
}

function normalizeMetric(metric: Record<string, unknown>): DisciplinePanelMetric {
  const rawValue = metric.value
  const numericValue = Number(rawValue)
  return {
    label: String(metric.label || ''),
    value: rawValue === null || rawValue === undefined || rawValue === ''
      ? null
      : Number.isFinite(numericValue) ? numericValue : String(rawValue),
    unit: metric.unit === null || metric.unit === undefined ? undefined : String(metric.unit)
  }
}

function filterRows(rows: Record<string, unknown>[]) {
  const selections = selectedPitchFilters()
  if (!selections.length) {
    return rows
  }
  return rows.filter((row) => selections.includes(String(row.pitch_name || row.Pitch || 'Unknown')))
}

function selectedPitchFilters() {
  return props.pitchFilter && props.pitchFilter !== 'All'
    ? props.pitchFilter.split(',').map((item) => item.trim()).filter(Boolean)
    : []
}

function groupPanels(payload: PeriodDisciplinePayload, groupKey: string, sectionKey: string) {
  if (props.groupFilter && props.groupFilter !== 'All' && props.groupFilter !== groupKey) {
    return []
  }
  const groups = asRecord(payload.panel_groups)
  const group = asRecord(groups[groupKey])
  return toRows(group[sectionKey]).map(normalizePanel)
}

function panelSets(payload: PeriodDisciplinePayload) {
  return {
    pitchResult: groupPanels(payload, 'result', 'pitch_result'),
    paResult: groupPanels(payload, 'result', 'pa_result'),
    battedBall: groupPanels(payload, 'result', 'batted_ball'),
    countSituation: groupPanels(payload, 'discipline', 'count_situation'),
    countSwing: groupPanels(payload, 'discipline', 'count_swing'),
    exactCount: groupPanels(payload, 'situation', 'exact_count')
  }
}
</script>

<style scoped>
.period-module {
  display: grid;
  gap: 14px;
  margin-top: 18px;
}

.module-header {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 14px;
}

.module-header h2,
.period-side h3 {
  margin: 0;
  color: var(--color-foreground);
}

.module-header h2 {
  font-size: 18px;
}

.module-header p {
  margin: 4px 0 0;
  color: var(--color-muted-text);
  font-size: 13px;
}

label {
  display: grid;
  min-width: 240px;
  gap: 6px;
  color: var(--color-foreground);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

label span {
  color: var(--color-muted-text);
}

.discipline-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  align-items: stretch;
}

.period-side {
  min-width: 0;
  display: grid;
  gap: 10px;
  align-content: start;
}

.period-side h3 {
  font-size: 15px;
}

.period-side :deep(.discipline-board) {
  height: 100%;
  margin-top: 0;
}

.period-side :deep(.discipline-panel-grid) {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: stretch;
}

.period-side :deep(.discipline-zone-panel) {
  height: 100%;
}

@media (max-width: 1180px) {
  .discipline-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .module-header {
    display: grid;
  }
}
</style>
