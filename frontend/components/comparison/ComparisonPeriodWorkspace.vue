<template>
  <div class="workspace" :class="{ 'filters-open': open }">
    <div class="main"><slot /></div>
    <aside class="filter-rail" :class="{ open }">
      <button class="toggle" type="button" :aria-expanded="open" aria-label="Toggle period filters" @click="$emit('update:open', !open)"><span>{{ open ? '›' : '‹' }}</span><em>Filters</em></button>
      <div class="fields"><h2>{{ filterTitle }}</h2><slot name="filters" /></div>
    </aside>
  </div>
</template>
<script setup lang="ts">
withDefaults(defineProps<{ open: boolean; filterTitle?: string }>(), { filterTitle: 'Period Filters' })
defineEmits<{ (event: 'update:open', value: boolean): void }>()
</script>
<style scoped>
.workspace { display: grid; grid-template-columns: minmax(0, 1fr) 48px; gap: 18px; align-items: start; margin-top: 18px; transition: grid-template-columns .2s ease; }.workspace.filters-open { grid-template-columns: minmax(0, 1fr) 280px; }.main { min-width: 0; }.filter-rail { position: sticky; top: 90px; min-height: 220px; border: 1px solid var(--color-border); background: var(--color-surface); box-shadow: var(--shadow-sm); overflow: hidden; }.toggle { display: flex; width: 100%; min-height: 46px; align-items: center; justify-content: center; gap: 8px; border: 0; border-bottom: 1px solid var(--color-border); color: var(--color-foreground); background: var(--color-plot-bg); cursor: pointer; }.toggle span { font-size: 24px; line-height: 1; }.toggle em { display: none; font-style: normal; font-weight: 850; }.fields { display: none; gap: 12px; padding: 16px; }.filter-rail.open .fields { display: grid; }.filter-rail.open .toggle em { display: inline; }.fields h2 { margin: 0; color: var(--color-foreground); font-size: 15px; }.fields :deep(label) { display: grid; gap: 7px; color: var(--color-foreground); font-size: 11px; font-weight: 850; text-transform: uppercase; }.fields :deep(select) { width: 100%; min-height: 40px; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 10px; color: var(--color-text); background: var(--color-surface); }.fields :deep(button.apply-filter) { min-height: 40px; border: 1px solid var(--color-primary); border-radius: 0; color: var(--color-on-primary); background: var(--color-primary); font-weight: 850; cursor: pointer; }
@media (max-width: 980px) { .workspace, .workspace.filters-open { grid-template-columns: 1fr; }.filter-rail { position: static; min-height: 0; }.filter-rail .fields { display: grid; }.toggle span { display: none; }.toggle em { display: inline; } }
</style>
