<template>
  <section class="chart-shell">
    <header v-if="title" class="chart-header">
      <h2>{{ title }}</h2>
      <span v-if="subtitle">{{ subtitle }}</span>
    </header>
    <ClientOnly>
      <div ref="chartElement" class="chart-canvas" :style="{ height }" />
      <template #fallback>
        <div class="chart-canvas fallback" :style="{ height }">Loading chart...</div>
      </template>
    </ClientOnly>
  </section>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { EChartsType } from 'echarts/core'
import { LineChart, PieChart, ScatterChart } from 'echarts/charts'
import { GraphicComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

use([ScatterChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, GraphicComponent, CanvasRenderer])

const props = withDefaults(defineProps<{
  option: EChartsOption
  title?: string
  subtitle?: string
  height?: string
}>(), {
  title: '',
  subtitle: '',
  height: '360px'
})

const emit = defineEmits<{
  'chart-click': [params: Record<string, unknown>]
}>()

const chartElement = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  if (!chartElement.value) {
    return
  }
  chart = init(chartElement.value)
  chart.on('click', (params) => emit('chart-click', params as Record<string, unknown>))
  resizeObserver = new ResizeObserver(() => resizeChart())
  resizeObserver.observe(chartElement.value)
  renderChart()
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  resizeObserver?.disconnect()
  resizeObserver = null
  chart?.off('click')
  chart?.dispose()
  chart = null
})

watch(
  () => props.option,
  () => renderChart(),
  { deep: true }
)

async function renderChart() {
  if (!chart) {
    return
  }
  await nextTick()
  chart.setOption(props.option, true)
  resizeChart()
  requestAnimationFrame(() => resizeChart())
}

function resizeChart() {
  chart?.resize()
}
</script>

<style scoped>
.chart-shell {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.chart-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}

.chart-header h2 {
  margin: 0;
  color: var(--color-foreground);
  font-size: 15px;
}

.chart-header span {
  color: var(--color-muted-text);
  font-size: 13px;
}

.chart-canvas {
  width: 100%;
  min-height: 240px;
}

.fallback {
  display: grid;
  place-items: center;
  color: var(--color-muted-text);
  font-size: 13px;
}
</style>
