<template>
  <section class="discipline-board wide-panel">
    <header class="board-header">
      <div>
        <h2>Discipline Panels</h2>
        <p>{{ activeGroupDescription }}</p>
      </div>
      <div class="board-controls">
        <div class="segmented" aria-label="Panel group">
          <button
            v-for="group in availableGroups"
            :key="group.key"
            type="button"
            :class="{ active: activeGroup === group.key }"
            @click="activeGroup = group.key"
          >
            {{ group.label }}
          </button>
        </div>
        <div class="segmented compact" aria-label="Panel side mode">
          <button type="button" :class="{ active: sideMode === 'pitch' }" @click="sideMode = 'pitch'">Pitch</button>
          <button type="button" :class="{ active: sideMode === 'info' }" @click="sideMode = 'info'">Info</button>
        </div>
      </div>
    </header>

    <template v-if="activeGroup === 'result'">
      <DisciplinePanelSection
        v-for="section in resultSections"
        :key="section.key"
        :title="section.title"
        :panels="section.panels"
        :heatmap-blend="heatmapBlend"
        :side-mode="sideMode"
      />
    </template>

    <template v-else-if="activeGroup === 'discipline'">
      <DisciplinePanelSection
        v-for="section in disciplineSections"
        :key="section.key"
        :title="section.title"
        :panels="section.panels"
        :heatmap-blend="heatmapBlend"
        :side-mode="sideMode"
      />
    </template>

    <template v-else>
      <DisciplinePanelSection
        title="Exact Count Grid"
        :panels="situationPanels"
        :heatmap-blend="heatmapBlend"
        :side-mode="sideMode"
      />
    </template>
  </section>
</template>

<script setup lang="ts">
import type { DisciplinePanel } from './DisciplineZonePanel.vue'

type PanelGroup = 'result' | 'discipline' | 'situation'

const props = defineProps<{
  heatmapBlend: number
  pitchResultPanels: DisciplinePanel[]
  paResultPanels?: DisciplinePanel[]
  battedBallPanels?: DisciplinePanel[]
  countSituationPanels: DisciplinePanel[]
  countSwingPanels?: DisciplinePanel[]
  exactCountPanels: DisciplinePanel[]
  initialGroup?: PanelGroup | 'All'
}>()

const activeGroup = ref<PanelGroup>('result')
const sideMode = ref<'pitch' | 'info'>('pitch')

const availableGroups = [
  { key: 'result' as const, label: 'Result', description: 'Pitch result, PA result, and batted-ball panels.' },
  { key: 'discipline' as const, label: 'Discipline', description: 'Count situation and swing-only count panels.' },
  { key: 'situation' as const, label: 'Situation', description: 'Exact count grid from 0-0 through 3-2.' }
]

const activeGroupDescription = computed(() => availableGroups.find((group) => group.key === activeGroup.value)?.description || '')

watch(
  () => props.initialGroup,
  (group) => {
    if (group && group !== 'All') {
      activeGroup.value = group
    }
  },
  { immediate: true }
)

const resultSections = computed(() => [
  { key: 'pitch_result', title: 'Pitch Result', panels: props.pitchResultPanels },
  { key: 'pa_result', title: 'PA Result', panels: props.paResultPanels || [] },
  { key: 'batted_ball', title: 'Batted Ball Type', panels: props.battedBallPanels || [] }
].filter((section) => section.panels.length))

const disciplineSections = computed(() => [
  { key: 'count_situation', title: 'Count Situation', panels: props.countSituationPanels },
  { key: 'count_swing', title: 'Count Swings', panels: props.countSwingPanels || [] }
].filter((section) => section.panels.length))

const situationPanels = computed(() => props.exactCountPanels)
</script>

<style scoped>
.discipline-board {
  display: grid;
  gap: 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px;
  background: color-mix(in srgb, var(--color-surface) 88%, transparent);
  box-shadow: var(--shadow-sm);
}

.board-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.board-header h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

.board-header p {
  margin: 4px 0 0;
  color: var(--color-muted-text);
  font-size: 13px;
}

.board-controls {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.segmented {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.segmented button {
  min-height: 34px;
  border: 0;
  border-right: 1px solid var(--color-border-strong);
  padding: 7px 11px;
  color: var(--color-muted-text);
  background: transparent;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.segmented button:last-child {
  border-right: 0;
}

.segmented button.active {
  color: var(--color-on-primary);
  background: var(--color-primary);
}

.segmented.compact button {
  padding-inline: 10px;
}

@media (max-width: 860px) {
  .board-header {
    display: grid;
  }

  .board-controls {
    justify-content: flex-start;
  }
}
</style>
