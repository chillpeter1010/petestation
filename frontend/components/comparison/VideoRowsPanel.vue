<template>
  <section class="video-panel">
    <header>
      <div>
        <h3>{{ title }}</h3>
        <p>{{ payload.total.toLocaleString() }} video rows</p>
      </div>
    </header>
    <div v-if="rows.length" class="video-list">
      <a
        v-for="(row, index) in rows"
        :key="`${row.videoUrl}-${index}`"
        :href="row.videoUrl"
        target="_blank"
        rel="noreferrer"
        class="video-row"
      >
        <span>{{ row.date || '-' }}</span>
        <strong>{{ row.pitch }}</strong>
        <em>{{ row.count }} · {{ row.description }}</em>
      </a>
    </div>
    <p v-else class="empty">No video rows for this period.</p>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{
  title: string
  payload: { rows: Record<string, unknown>[]; total: number }
}>()

const rows = computed(() => props.payload.rows.map((row) => ({
  date: String(row.game_date || ''),
  pitch: String(row.pitch_name || 'Unknown'),
  description: String(row.description || row.events || '-'),
  count: `${row.balls ?? '-'}-${row.strikes ?? '-'}`,
  videoUrl: String(row.video_url || '')
})).filter((row) => row.videoUrl))
</script>

<style scoped>
.video-panel {
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

.video-list {
  display: grid;
  max-height: 420px;
  overflow: auto;
}

.video-row {
  display: grid;
  grid-template-columns: 88px 140px minmax(0, 1fr);
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text);
  text-decoration: none;
}

.video-row:hover {
  background: color-mix(in srgb, var(--color-muted) 60%, transparent);
}

.video-row strong {
  color: var(--color-foreground);
}

.video-row em,
.video-row span {
  color: var(--color-muted-text);
  font-style: normal;
}

.empty {
  margin: 0;
  padding: 16px 14px;
}

@media (max-width: 640px) {
  .video-row {
    grid-template-columns: 1fr;
  }
}
</style>
