<template>
  <details class="checkbox-dropdown">
    <summary>
      <span>{{ summaryLabel }}</span>
      <span aria-hidden="true">v</span>
    </summary>
    <div class="checkbox-menu">
      <label
        v-for="option in normalizedOptions"
        :key="option.value"
        class="checkbox-option"
      >
        <input
          type="checkbox"
          :checked="isChecked(option.value)"
          @change="toggleOption(option.value)"
        >
        <span>{{ option.label }}</span>
      </label>
    </div>
  </details>
</template>

<script setup lang="ts">
type SelectOption = string | { value: string; label: string }

const model = defineModel<string>({ required: true })

const props = withDefaults(defineProps<{
  options: SelectOption[]
  allLabel?: string
}>(), {
  allLabel: 'All'
})

const normalizedOptions = computed(() => {
  const options = props.options.map((option) => {
    if (typeof option === 'string') {
      return { value: option, label: option }
    }
    return option
  })
  return options.some((option) => option.value === 'All')
    ? options
    : [{ value: 'All', label: props.allLabel }, ...options]
})

const selectedValues = computed(() => {
  const value = model.value || 'All'
  if (value === 'All') {
    return ['All']
  }
  return value.split(',').map((item) => item.trim()).filter(Boolean)
})

const selectedLabels = computed(() => {
  if (selectedValues.value.includes('All')) {
    return [props.allLabel]
  }
  const labelMap = new Map(normalizedOptions.value.map((option) => [option.value, option.label]))
  return selectedValues.value.map((value) => labelMap.get(value) || value)
})

const summaryLabel = computed(() => {
  if (selectedValues.value.includes('All')) {
    return props.allLabel
  }
  if (selectedLabels.value.length <= 2) {
    return selectedLabels.value.join(', ')
  }
  return `${selectedLabels.value.length} selected`
})

function isChecked(value: string) {
  return selectedValues.value.includes(value)
}

function toggleOption(value: string) {
  if (value === 'All') {
    model.value = 'All'
    return
  }

  const current = new Set(selectedValues.value.filter((item) => item !== 'All'))
  if (current.has(value)) {
    current.delete(value)
  } else {
    current.add(value)
  }

  model.value = current.size ? [...current].join(',') : 'All'
}
</script>

<style scoped>
.checkbox-dropdown {
  position: relative;
  min-width: 0;
}

.checkbox-dropdown summary {
  width: 100%;
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  background: var(--color-plot-bg);
  color: var(--color-text);
  font-size: 14px;
  font-weight: 750;
  text-transform: none;
  cursor: pointer;
  list-style: none;
}

.checkbox-dropdown summary::-webkit-details-marker {
  display: none;
}

.checkbox-dropdown[open] summary {
  border-color: var(--color-primary);
}

.checkbox-menu {
  position: absolute;
  z-index: 40;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  max-height: 280px;
  overflow: auto;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 6px;
  background: var(--color-surface);
  box-shadow: var(--shadow-md);
}

.checkbox-option {
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: 6px;
  padding: 7px 8px;
  color: var(--color-text);
  font-size: 13px;
  font-weight: 700;
  text-transform: none;
  cursor: pointer;
}

.checkbox-option:hover {
  background: color-mix(in srgb, var(--color-primary) 16%, transparent);
}

.checkbox-option input {
  width: 14px;
  height: 14px;
  accent-color: var(--color-primary);
}
</style>
