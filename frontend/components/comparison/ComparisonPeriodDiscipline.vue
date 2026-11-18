<template>
  <section class="period-module">
    <header class="module-header">
      <div>
        <h2>Discipline</h2>
        <p>AVG＝該面板球數／條件下終結打數的 H／AB；PA result 篩選保留符合最終結果之打席內的投球。點擊投球可查看影片。</p>
      </div>
    </header>
    <HeatmapBlendControl v-model="heatmapBlend" title="Period pitch location" />
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
          @select-point="selectedLeftPoint = $event; videoOpen = true"
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
          @select-point="selectedRightPoint = $event; videoOpen = true"
        />
      </section>
    </div>
    <Teleport to="body">
      <div v-if="videoOpen" class="period-video-backdrop" @click.self="videoOpen = false" @keydown.esc="videoOpen = false">
        <section class="period-video-dialog" role="dialog" aria-modal="true" aria-label="Period selected pitch videos">
          <button type="button" class="video-close" autofocus @click="videoOpen = false">關閉影片 ×</button>
          <ComparisonPeriodVideos
            :left="{ rows: [], total: left.total || 0 }"
            :right="{ rows: [], total: right.total || 0 }"
            :selected-left-point="selectedLeftPoint"
            :selected-right-point="selectedRightPoint"
          />
        </section>
      </div>
    </Teleport>
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
const selectedLeftPoint = ref<Record<string, unknown> | null>(null)
const selectedRightPoint = ref<Record<string, unknown> | null>(null)
const videoOpen = ref(false)
watch(() => [props.left, props.right], () => {
  selectedLeftPoint.value = null
  selectedRightPoint.value = null
  videoOpen.value = false
})
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
    pitches: hasPitchFilter ? rows.length : Number(panel.pitches ?? rows.length),
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
.period-video-backdrop { position: fixed; inset: 0; z-index: 1000; display: grid; place-items: center; padding: 20px; background: rgb(0 0 0 / 78%); }
.period-video-dialog { width: min(1180px, 96vw); max-height: 92vh; overflow: auto; border: 1px solid var(--color-border); padding: 16px; background: var(--color-surface); }
.video-close { display: block; margin-left: auto; padding: 8px 14px; border: 1px solid var(--color-border); color: var(--color-text); background: var(--color-surface); cursor: pointer; }
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
