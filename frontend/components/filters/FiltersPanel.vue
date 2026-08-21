<template>
  <section class="filters-panel">
    <div class="filter-title">
      <strong>Filters</strong>
      <span>{{ filters.year }} {{ filters.role }}</span>
    </div>
    <label>
      Year
      <input v-model.number="filters.year" type="number" min="2015" max="2030">
    </label>
    <label>
      Role
      <select v-model="filters.role">
        <option value="SP">SP</option>
        <option value="RP">RP</option>
      </select>
    </label>
    <label>
      Team
      <select v-model="filters.team" :disabled="isLoading || !teamOptions.length">
        <option v-for="team in teamOptions" :key="team" :value="team">{{ team }}</option>
      </select>
    </label>
    <label>
      Pitcher
      <select v-model.number="filters.pitcherId" :disabled="isLoading || !filteredPitchers.length">
        <option v-for="pitcher in filteredPitchers" :key="pitcher.value" :value="pitcher.value">
          {{ pitcher.label }}
        </option>
      </select>
    </label>
    <p v-if="isLoading" class="filter-status">Loading pitchers...</p>
    <p v-else-if="loadError" class="filter-status error">{{ loadError }}</p>
    <p v-else-if="!pitchers.length" class="filter-status">No pitchers found.</p>
  </section>
</template>

<script setup lang="ts">
import type { PitcherOption } from '~/types/api'

const filters = useAnalysisFilters()
const api = useApi()

const pitchers = ref<PitcherOption[]>([])
const isLoading = ref(false)
const loadError = ref('')

const teamOptions = computed(() => {
  return [...new Set(pitchers.value.map((pitcher) => pitcher.team).filter(Boolean))].sort()
})

const filteredPitchers = computed(() => {
  if (!filters.team) {
    return pitchers.value
  }
  return pitchers.value.filter((pitcher) => pitcher.team === filters.team)
})

watch(
  () => [filters.year, filters.role] as const,
  async () => {
    isLoading.value = true
    loadError.value = ''
    try {
      pitchers.value = await api.pitchers({ year: filters.year, role: filters.role })
      filters.team = teamOptions.value.includes(filters.team) ? filters.team : teamOptions.value[0] || ''
      filters.pitcherId = filteredPitchers.value.some((pitcher) => pitcher.value === filters.pitcherId)
        ? filters.pitcherId
        : filteredPitchers.value[0]?.value || null
    } catch (error) {
      pitchers.value = []
      filters.team = ''
      filters.pitcherId = null
      loadError.value = error instanceof Error ? error.message : 'Failed to load pitchers.'
    } finally {
      isLoading.value = false
    }
  },
  { immediate: true }
)

watch(
  () => filters.team,
  () => {
    const currentPitcherIsAvailable = filteredPitchers.value.some(
      (pitcher) => pitcher.value === filters.pitcherId
    )
    if (!currentPitcherIsAvailable) {
      filters.pitcherId = filteredPitchers.value[0]?.value || null
    }
  }
)
</script>

<style scoped>
.filters-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: end;
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--color-surface) 86%, transparent);
  box-shadow: var(--shadow-sm);
}

.filter-title {
  display: grid;
  gap: 2px;
  min-width: 120px;
  padding-bottom: 2px;
}

.filter-title strong {
  color: var(--color-foreground);
  font-size: 14px;
}

.filter-title span {
  color: var(--color-muted-text);
  font-size: 12px;
}

label {
  display: grid;
  gap: 6px;
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 650;
  text-transform: uppercase;
}

input,
select {
  min-width: 160px;
  height: 38px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  background: var(--color-plot-bg);
  color: var(--color-text);
}

input:disabled,
select:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.filter-status {
  margin: 0 0 8px;
  color: var(--color-muted-text);
  font-size: 13px;
}

.filter-status.error {
  color: #b42318;
}
</style>
