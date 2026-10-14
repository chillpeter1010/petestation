<template>
  <section class="period-setup">
    <div class="directory-fields">
      <slot name="directory" />
    </div>

    <slot name="between" />

    <div class="period-fields">
      <div class="period-group">
        <h2>Period A</h2>
        <label>Year<select :value="leftYear" @change="emitNumber('update:leftYear', $event)"><option v-for="year in years" :key="`left-${year}`" :value="year">{{ year }}</option></select></label>
        <label>Start<input :value="leftStart" type="date" @input="emitText('update:leftStart', $event)"></label>
        <label>End<input :value="leftEnd" type="date" @input="emitText('update:leftEnd', $event)"></label>
      </div>
      <div class="period-group">
        <h2>Period B</h2>
        <label>Year<select :value="rightYear" @change="emitNumber('update:rightYear', $event)"><option v-for="year in years" :key="`right-${year}`" :value="year">{{ year }}</option></select></label>
        <label>Start<input :value="rightStart" type="date" @input="emitText('update:rightStart', $event)"></label>
        <label>End<input :value="rightEnd" type="date" @input="emitText('update:rightEnd', $event)"></label>
      </div>
      <button class="apply-button" type="button" :disabled="!canApply || pending" @click="$emit('apply')">
        {{ pending ? 'Loading…' : 'Apply Periods' }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ years: number[]; leftYear: number; rightYear: number; leftStart: string; leftEnd: string; rightStart: string; rightEnd: string; canApply: boolean; pending?: boolean }>()
const emit = defineEmits<{ (event: 'update:leftYear' | 'update:rightYear', value: number): void; (event: 'update:leftStart' | 'update:leftEnd' | 'update:rightStart' | 'update:rightEnd', value: string): void; (event: 'apply'): void }>()
function emitNumber(event: 'update:leftYear' | 'update:rightYear', source: Event) { emit(event, Number((source.target as HTMLSelectElement).value)) }
function emitText(event: 'update:leftStart' | 'update:leftEnd' | 'update:rightStart' | 'update:rightEnd', source: Event) { emit(event, (source.target as HTMLInputElement).value) }
</script>

<style scoped>
.period-setup { margin-top: 16px; }
.directory-fields, .period-fields { display: grid; gap: 14px; border: 1px solid var(--color-border); background: var(--color-surface); box-shadow: var(--shadow-sm); }
.directory-fields { grid-template-columns: 140px 180px minmax(260px, 420px); align-items: end; padding: 18px; }
.period-fields { grid-template-columns: repeat(2, minmax(0, 1fr)) auto; align-items: end; margin-top: 16px; padding: 18px; }
.period-group { display: grid; grid-template-columns: 90px repeat(2, minmax(0, 1fr)); gap: 12px; align-items: end; }
.period-group h2 { grid-column: 1 / -1; margin: 0; color: var(--color-foreground); font-size: 15px; }
.directory-fields :deep(label), .period-group label { display: grid; gap: 7px; color: var(--color-foreground); font-size: 11px; font-weight: 850; text-transform: uppercase; }
.directory-fields :deep(select), .period-group select, .period-group input { width: 100%; min-height: 42px; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 10px; color: var(--color-text); background: var(--color-surface); }
.apply-button { min-height: 42px; border: 1px solid var(--color-primary); border-radius: 0; padding: 0 18px; color: var(--color-on-primary); background: var(--color-primary); font-weight: 850; cursor: pointer; }
.apply-button:disabled { cursor: not-allowed; opacity: .55; }
@media (max-width: 980px) { .directory-fields, .period-fields { grid-template-columns: 1fr 1fr; } .apply-button { grid-column: 1 / -1; } }
@media (max-width: 680px) { .directory-fields, .period-fields, .period-group { grid-template-columns: 1fr; } }
</style>
