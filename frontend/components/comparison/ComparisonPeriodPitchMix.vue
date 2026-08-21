<template>
  <section class="period-module">
    <header class="module-header">
      <div>
        <h2>Pitch Mix</h2>
        <p>Period A and Period B usage by pitch type.</p>
      </div>
    </header>
    <div class="mix-grid">
      <PitchMixPanel title="Period A Pitch Mix" :payload="left" />
      <PitchMixPanel title="Period B Pitch Mix" :payload="right" />
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  left: { rows: Record<string, unknown>[]; total: number }
  right: { rows: Record<string, unknown>[]; total: number }
}>()
</script>

<style scoped>
.period-module {
  display: grid;
  gap: 14px;
  margin-top: 18px;
}

.module-header h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 18px;
}

.module-header p {
  margin: 4px 0 0;
  color: var(--color-muted-text);
  font-size: 13px;
}

.mix-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

@media (max-width: 980px) {
  .mix-grid {
    grid-template-columns: 1fr;
  }
}
</style>
