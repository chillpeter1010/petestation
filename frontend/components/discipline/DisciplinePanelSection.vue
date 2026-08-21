<template>
  <section class="discipline-panel-section">
    <header>
      <h3>{{ title }}</h3>
      <span>{{ totalPitches.toLocaleString() }} pitches</span>
    </header>
    <div class="discipline-panel-grid">
      <DisciplineZonePanel
        v-for="panel in panels"
        :key="panel.key"
        :panel="panel"
        :heatmap-blend="heatmapBlend"
        :side-mode="sideMode"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import type { DisciplinePanel } from './DisciplineZonePanel.vue'

const props = defineProps<{
  title: string
  panels: DisciplinePanel[]
  heatmapBlend: number
  sideMode: 'pitch' | 'info'
}>()

const totalPitches = computed(() => props.panels.reduce((sum, panel) => sum + (panel.pitches ?? panel.rows.length), 0))
</script>

<style scoped>
.discipline-panel-section {
  display: grid;
  gap: 10px;
}

.discipline-panel-section header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.discipline-panel-section h3 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 14px;
}

.discipline-panel-section span {
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 650;
}

.discipline-panel-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

@media (max-width: 1180px) {
  .discipline-panel-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .discipline-panel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
