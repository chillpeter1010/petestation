<template>
  <section class="mix-panel">
    <header>
      <div>
        <h3>{{ title }}</h3>
        <p>{{ payload.total.toLocaleString() }} pitches</p>
      </div>
    </header>
    <div v-if="rows.length" class="mix-list">
      <div v-for="row in rows" :key="row.pitch" class="mix-row">
        <div class="mix-label">
          <span>
            <i :style="{ background: colorForPitch(row.pitch) }" />
            {{ row.pitch }}
          </span>
          <strong>{{ formatPct(row.usagePct) }}</strong>
        </div>
        <div class="bar-track">
          <div class="bar-fill" :style="{ width: `${Math.min(row.usagePct, 100)}%`, background: colorForPitch(row.pitch) }" />
        </div>
        <span class="pitch-count">{{ row.pitches.toLocaleString() }} pitches</span>
      </div>
    </div>
    <p v-else class="empty">No pitch mix rows for this period.</p>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{
  title: string
  payload: { rows: Record<string, unknown>[]; total: number }
}>()

const rows = computed(() => props.payload.rows.map((row) => ({
  pitch: String(row.pitch || row.pitch_name || row.Pitch || 'Unknown'),
  pitches: Number(row.pitches || row.Pitches || 0),
  usagePct: Number(row.usage_pct || row['Usage%'] || row.rate || 0)
})))

function formatPct(value: number) {
  return Number.isFinite(value) ? `${value.toFixed(1)}%` : '-'
}

function colorForPitch(pitch: string) {
  return pitchColors[pitch] || defaultPitchColor
}

const pitchColors: Record<string, string> = {
  '4-Seam Fastball': '#d62828',
  Fastball: '#d62828',
  'Four-Seam': '#d62828',
  '4-Seam': '#d62828',
  Sinker: '#f77f00',
  Cutter: '#7f5539',
  Slider: '#ffd166',
  Changeup: '#28c97b',
  'Split-Finger': '#00a6a6',
  Splitter: '#00a6a6',
  Curveball: '#277da1',
  Sweeper: '#bc8a3c'
}
const defaultPitchColor = '#8b949e'
</script>

<style scoped>
.mix-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

header {
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}

h3 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

p {
  margin: 4px 0 0;
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
  gap: 5px;
}

.mix-label {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--color-text);
  font-size: 13px;
}

.mix-label span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.mix-label i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  border: 0.7px solid rgba(255, 255, 255, 0.9);
}

.mix-label strong,
.pitch-count {
  color: var(--color-foreground);
  font-family: "Fira Code", "Consolas", monospace;
}

.bar-track {
  height: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-muted);
}

.bar-fill {
  height: 100%;
  border-radius: inherit;
}

.pitch-count,
.empty {
  font-size: 12px;
}

.empty {
  margin: 0;
  padding: 16px 14px;
}
</style>
