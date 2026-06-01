<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

const props = defineProps<{
  title: string
  value: number | string
  change?: number
  trend?: number[]
  precision?: number
}>()

const formattedValue = computed(() => {
  if (typeof props.value === 'number') {
    return props.value.toFixed(props.precision || 2)
  }
  return props.value
})

const changeClass = computed(() => {
  if (!props.change) return 'text-flat'
  return props.change > 0 ? 'text-rise' : 'text-fall'
})

const changeSymbol = computed(() => {
  if (!props.change) return ''
  return props.change > 0 ? '+' : ''
})

const changeText = computed(() => {
  if (!props.change) return ''
  return `${changeSymbol.value}${props.change.toFixed(2)}%`
})

let chartInstance: echarts.ECharts | null = null
const chartRef = ref<HTMLElement | null>(null)

const initChart = () => {
  if (!chartRef.value || !props.trend || props.trend.length === 0) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)
  
  const isRise = props.change && props.change > 0
  
  const option: EChartsOption = {
    grid: {
      left: 0,
      right: 0,
      bottom: 0,
      top: 0,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      show: false,
      data: props.trend.map((_, i) => i.toString())
    },
    yAxis: {
      type: 'value',
      show: false
    },
    series: [
      {
        type: 'line',
        data: props.trend,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: isRise ? '#cf222e' : '#1a7f37',
          width: 2
        },
        animation: false
      }
    ]
  }
  
  chartInstance.setOption(option)
}

onMounted(() => {
  initChart()
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<template>
  <div class="metric-card">
    <div class="card-header">
      <span class="card-title">{{ title }}</span>
    </div>
    <div class="card-body">
      <div class="metric-main">
        <span class="metric-value">{{ formattedValue }}</span>
        <span v-if="change !== undefined" class="metric-change" :class="changeClass">
          {{ changeText }}
        </span>
      </div>
      <div v-if="trend && trend.length > 0" class="mini-chart">
        <div ref="chartRef" class="chart-container"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.metric-card {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  padding: var(--spacing-md);
  flex: 1;
  min-width: 0;
}

.card-header {
  margin-bottom: var(--spacing-sm);
}

.card-title {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.metric-main {
  display: flex;
  align-items: baseline;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.metric-value {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.metric-change {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  padding: 2px 6px;
  border-radius: var(--radius-small);
  background-color: var(--color-bg-secondary);
}

.mini-chart {
  height: 32px;
}

.chart-container {
  width: 100%;
  height: 100%;
}

@media (max-width: 767px) {
  .metric-card {
    padding: var(--spacing-sm);
  }

  .metric-value {
    font-size: var(--font-size-base);
  }

  .card-title {
    font-size: 10px;
  }

  .metric-change {
    font-size: 9px;
    padding: 1px 4px;
  }

  .mini-chart {
    height: 24px;
  }
}
</style>
