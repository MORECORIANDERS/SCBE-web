<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

const props = defineProps<{
  title: string
  data: Array<{ date: string; value: number }>
  color?: string
}>()

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const initChart = () => {
  if (!chartRef.value) return

  chartInstance = echarts.init(chartRef.value)

  const option: EChartsOption = {
    grid: {
      left: '2%',
      right: '2%',
      bottom: '2%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      show: false,
      data: props.data.map(item => item.date)
    },
    yAxis: {
      type: 'value',
      show: false
    },
    series: [
      {
        name: props.title,
        type: 'line',
        data: props.data.map(item => item.value),
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: props.color || '#0969da',
          width: 2
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: props.color || '#0969da' + '40' },
              { offset: 1, color: props.color || '#0969da' + '00' }
            ]
          }
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
  }
})
</script>

<template>
  <div class="mini-chart">
    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<style scoped>
.mini-chart {
  width: 100%;
  height: 40px;
}

.chart-container {
  width: 100%;
  height: 100%;
}
</style>
