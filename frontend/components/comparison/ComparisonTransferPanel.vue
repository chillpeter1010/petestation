<template>
  <section class="transfer-panel" aria-labelledby="transfer-filter-title">
    <div class="transfer-heading">
      <div><p>Team Change Detected</p><h2 id="transfer-filter-title">{{ summary }}</h2></div>
      <span>{{ stints.length }} stints · {{ stints.length - 1 }} changes</span>
    </div>
    <button v-if="stints.length === 2" class="transfer-button" type="button" :disabled="pending" @click="compare(stints[0], stints[1])">Compare {{ stints[0]?.team }} before vs {{ stints[1]?.team }} after</button>
    <div v-else class="transfer-picker">
      <label>Period A team stint<select :value="leftIndex" @change="updateIndex('left', $event)"><option v-for="stint in stints" :key="`left-${stint.stint_index}`" :value="stint.stint_index">{{ stint.label }}</option></select></label>
      <label>Period B team stint<select :value="rightIndex" @change="updateIndex('right', $event)"><option v-for="stint in stints" :key="`right-${stint.stint_index}`" :value="stint.stint_index">{{ stint.label }}</option></select></label>
      <button class="transfer-button" type="button" :disabled="pending || leftIndex === rightIndex" @click="compareSelected">Compare selected stints</button>
    </div>
  </section>
</template>
<script setup lang="ts">
import type { ComparisonTeamStint } from '~/types/api'
const props = defineProps<{ stints: ComparisonTeamStint[]; leftIndex: number | null; rightIndex: number | null; pending?: boolean }>()
const emit = defineEmits<{ (event: 'update:leftIndex' | 'update:rightIndex', value: number): void; (event: 'compare', left: ComparisonTeamStint, right: ComparisonTeamStint): void }>()
const summary = computed(() => props.stints.map(stint => stint.team).join(' → '))
function updateIndex(side: 'left' | 'right', event: Event) { emit(side === 'left' ? 'update:leftIndex' : 'update:rightIndex', Number((event.target as HTMLSelectElement).value)) }
function compare(left?: ComparisonTeamStint, right?: ComparisonTeamStint) { if (left && right) emit('compare', left, right) }
function compareSelected() { compare(props.stints.find(stint => stint.stint_index === props.leftIndex), props.stints.find(stint => stint.stint_index === props.rightIndex)) }
</script>
<style scoped>
.transfer-panel { margin-top: 16px; border: 1px solid color-mix(in srgb, var(--color-primary) 58%, var(--color-border)); padding: 16px 18px; background: color-mix(in srgb, var(--color-primary) 8%, var(--color-surface)); }
.transfer-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
.transfer-heading p, .transfer-heading h2 { margin: 0; }.transfer-heading p { color: var(--color-primary); font-size: 11px; font-weight: 900; text-transform: uppercase; }.transfer-heading h2 { margin-top: 4px; color: var(--color-foreground); font-size: 16px; }.transfer-heading span { color: var(--color-muted-text); font-size: 12px; }
.transfer-picker { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)) auto; gap: 12px; align-items: end; margin-top: 14px; }
label { display: grid; gap: 7px; color: var(--color-foreground); font-size: 11px; font-weight: 850; text-transform: uppercase; } select { min-height: 42px; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 10px; color: var(--color-text); background: var(--color-surface); }
.transfer-button { min-height: 40px; margin-top: 14px; border: 1px solid var(--color-primary); border-radius: 0; padding: 0 14px; color: var(--color-on-primary); background: var(--color-primary); font-weight: 850; cursor: pointer; }.transfer-button:disabled { opacity: .55; cursor: not-allowed; }
.transfer-picker .transfer-button { margin-top: 0; }
@media (max-width: 760px) { .transfer-heading { display: grid; }.transfer-picker { grid-template-columns: 1fr; } }
</style>
