<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  categories: string[]
  values: number[]
}>()

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const initChart = () => {
  if (!chartRef.value) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  const riseColor = '#cf222e'
  const fallColor = '#1a7f37'
  const neutralColor = '#656d76'

  const colors = props.values.map((val: number) => {
    if (val > 0) return riseColor
    if (val < 0) return fallColor
    return neutralColor
  })

  const absoluteValues = props.values.map((val: number) => Math.abs(val))

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#d0d7de',
      borderWidth: 1,
      textStyle: {
        color: '#24292f',
        fontSize: 12
      },
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params: any) => {
        const originalValue = props.values[params.dataIndex]
        return `${params.name}<br/>数量: <strong>${originalValue}</strong>`
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: props.categories,
      axisLine: {
        lineStyle: {
          color: '#d0d7de'
        }
      },
      axisLabel: {
        color: '#656d76',
        fontSize: 11,
        interval: 0,
        rotate: props.categories.length > 6 ? 45 : 0
      },
      axisTick: {
        show: false
      }
    },
    yAxis: {
      type: 'value',
      axisLine: {
        show: false
      },
      axisLabel: {
        color: '#656d76',
        fontSize: 11
      },
      splitLine: {
        lineStyle: {
          color: '#f0f3f6'
        }
      },
      axisTick: {
        show: false
      }
    },
    series: [
      {
        name: '数量',
        type: 'bar',
        data: absoluteValues,
        itemStyle: {
          color: (params: any) => colors[params.dataIndex],
          borderRadius: [0, 0, 0, 0]
        },
        barWidth: '60%',
        label: {
          show: true,
          position: 'top',
          color: '#24292f',
          fontSize: 11,
          fontWeight: 500,
          formatter: (params: any) => String(Math.abs(props.values[params.dataIndex]))
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

watch(
  () => [props.categories, props.values],
  () => {
    initChart()
  },
  { deep: true }
)
</script>

<template>
  <div class="rise-fall-chart">
    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<style scoped>
.rise-fall-chart {
  width: 100%;
  height: 300px;
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  padding: var(--spacing-lg);
}

.chart-container {
  width: 100%;
  height: 100%;
}

@media (max-width: 767px) {
  .rise-fall-chart {
    height: 250px;
    padding: var(--spacing-md);
  }
}
</style>
