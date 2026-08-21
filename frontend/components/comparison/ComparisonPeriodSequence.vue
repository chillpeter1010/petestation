<template>
  <section class="period-sequence-panel">
    <header class="panel-header">
      <div>
        <h2>Period Sequence</h2>
        <p>Count-state pitch mix by selected date window.</p>
      </div>
      <span>{{ leftTotal.toLocaleString() }} A pitches / {{ rightTotal.toLocaleString() }} B pitches</span>
    </header>

    <div class="sequence-grid">
      <section class="sequence-side">
        <header class="side-header">
          <h3>Period A Sequence</h3>
          <span>{{ leftTotal.toLocaleString() }} pitches</span>
        </header>
        <SummaryCards :metrics="leftSnapshotMetrics" />
        <SequenceOutcomeTree
          v-if="leftCountRows.length"
          :rows="leftCountRows"
          :source-rows="leftPitchRows"
        />
        <p v-else class="empty-note">No sequence rows for Period A.</p>
        <div class="table-grid">
          <DataTable title="Shallow Count Sequences" :table="left.tables.shallow_sequences" />
          <DataTable title="Two-Strike Sequences" :table="left.tables.two_strike_sequences" />
        </div>
      </section>

      <section class="sequence-side">
        <header class="side-header">
          <h3>Period B Sequence</h3>
          <span>{{ rightTotal.toLocaleString() }} pitches</span>
        </header>
        <SummaryCards :metrics="rightSnapshotMetrics" />
        <SequenceOutcomeTree
          v-if="rightCountRows.length"
          :rows="rightCountRows"
          :source-rows="rightPitchRows"
        />
        <p v-else class="empty-note">No sequence rows for Period B.</p>
        <div class="table-grid">
          <DataTable title="Shallow Count Sequences" :table="right.tables.shallow_sequences" />
          <DataTable title="Two-Strike Sequences" :table="right.tables.two_strike_sequences" />
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AnalysisResponse, MetricItem } from '~/types/api'

const props = defineProps<{
  left: AnalysisResponse
  right: AnalysisResponse
}>()

const leftCountRows = computed(() => chartRows(props.left, 'count_pitch_mix'))
const rightCountRows = computed(() => chartRows(props.right, 'count_pitch_mix'))
const leftPitchRows = computed(() => chartRows(props.left, 'pitch_location_scatter'))
const rightPitchRows = computed(() => chartRows(props.right, 'pitch_location_scatter'))
const leftTotal = computed(() => pitchTotal(props.left, leftPitchRows.value))
const rightTotal = computed(() => pitchTotal(props.right, rightPitchRows.value))
const leftSnapshotMetrics = computed(() => snapshotMetrics(props.left, leftTotal.value))
const rightSnapshotMetrics = computed(() => snapshotMetrics(props.right, rightTotal.value))

function chartRows(payload: AnalysisResponse, key: string) {
  const rows = payload.charts[key]
  return Array.isArray(rows)
    ? rows.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object' && !Array.isArray(row))
    : []
}

function pitchTotal(payload: AnalysisResponse, fallbackRows: Record<string, unknown>[]) {
  const snapshot = payload.charts.filter_snapshot as Record<string, unknown> | undefined
  const total = Number(snapshot?.pitches)
  return Number.isFinite(total) && total > 0 ? total : fallbackRows.length
}

function snapshotMetrics(payload: AnalysisResponse, total: number): MetricItem[] {
  if (payload.summary.length) {
    return payload.summary
  }
  const snapshot = payload.charts.filter_snapshot as Record<string, unknown> | undefined
  return [
    { key: 'pitches', label: 'Filtered Pitches', value: total },
    { key: 'zone_pct', label: 'Zone%', value: snapshot?.zone_pct as number | string | null, unit: '%' },
    { key: 'swing_pct', label: 'Swing%', value: snapshot?.swing_pct as number | string | null, unit: '%' },
    { key: 'whiff_pct', label: 'Whiff%', value: snapshot?.whiff_pct as number | string | null, unit: '%' }
  ].filter((metric) => metric.value !== undefined)
}
</script>

<style scoped>
.period-sequence-panel {
  margin-top: 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.panel-header,
.side-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
  border-bottom: 1px solid var(--color-border);
  padding: 16px 18px;
}

.panel-header h2,
.side-header h3 {
  margin: 0;
  color: var(--color-foreground);
}

.panel-header p {
  margin: 4px 0 0;
  color: var(--color-muted);
}

.panel-header span,
.side-header span {
  color: var(--color-muted);
  white-space: nowrap;
}

.sequence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  padding: 18px;
}

.sequence-side {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-panel);
}

.sequence-side :deep(.summary-grid) {
  margin: 16px;
}

.sequence-side :deep(.sequence-tree) {
  margin: 16px;
}

.sequence-side :deep(.tree-wrap) {
  min-height: 420px;
}

.table-grid {
  display: grid;
  gap: 14px;
  padding: 0 16px 16px;
}

.empty-note {
  margin: 16px;
  color: var(--color-muted);
}

@media (max-width: 980px) {
  .sequence-grid {
    grid-template-columns: 1fr;
  }
}
</style>
