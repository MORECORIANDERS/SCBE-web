<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  categories: string[]
  upValues: number[]
  downValues: number[]
  flatValues: number[]
  totalValues: number[]
  amountSumValues: number[]
  selectedCategory?: string | null
}>()

const emit = defineEmits<{
  barClick: [category: string]
}>()

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const initChart = () => {
  if (!chartRef.value) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#d0d7de',
      borderWidth: 1,
      textStyle: { color: '#24292f', fontSize: 12 },
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const idx = params[0].dataIndex
        const total = props.totalValues[idx]
        const up = props.upValues[idx]
        const down = props.downValues[idx]
        const flat = props.flatValues[idx]
        const amountSum = props.amountSumValues[idx]
        return `${props.categories[idx]}<br/>
          <span style="color:#cf222e">●</span> 上涨: <strong>${up}</strong><br/>
          <span style="color:#1a7f37">●</span> 下跌: <strong>${down}</strong><br/>
          <span style="color:#656d76">●</span> 持平: <strong>${flat}</strong><br/>
          <strong>合计: ${total}</strong><br/>
          <span style="color:#e16f24">━</span> 成交额: <strong>${amountSum}亿</strong>`
      }
    },
    legend: {
      data: ['下跌', '持平', '上涨', '成交额'],
      top: 0,
      left: 'center',
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 8,
      textStyle: { color: '#656d76', fontSize: 11 },
    },
    grid: {
      left: '3%',
      right: '5%',
      bottom: '8%',
      top: '18%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: props.categories,
      axisLine: { lineStyle: { color: '#d0d7de' } },
      axisLabel: { color: '#656d76', fontSize: 11, interval: 0, rotate: props.categories.length > 6 ? 45 : 0 },
      axisTick: { show: false }
    },
    yAxis: [
      {
        type: 'value',
        name: '数量',
        nameTextStyle: { color: '#656d76', fontSize: 10 },
        axisLine: { show: false },
        axisLabel: { color: '#656d76', fontSize: 11 },
        splitLine: { lineStyle: { color: '#f0f3f6' } },
        axisTick: { show: false }
      },
      {
        type: 'value',
        name: '成交额(亿)',
        nameTextStyle: { color: '#656d76', fontSize: 10 },
        axisLine: { show: false },
        axisLabel: { color: '#656d76', fontSize: 11 },
        splitLine: { show: false },
        axisTick: { show: false }
      }
    ],
    series: [
      {
        name: '下跌',
        type: 'bar',
        stack: 'total',
        yAxisIndex: 0,
        data: props.downValues,
        itemStyle: {
          color: (params: any) => {
            const cat = props.categories[params.dataIndex]
            if (props.selectedCategory && props.selectedCategory !== cat) return '#1a7f3730'
            return '#1a7f37'
          },
        },
        barWidth: '50%',
        animation: false
      },
      {
        name: '持平',
        type: 'bar',
        stack: 'total',
        yAxisIndex: 0,
        data: props.flatValues,
        itemStyle: {
          color: (params: any) => {
            const cat = props.categories[params.dataIndex]
            if (props.selectedCategory && props.selectedCategory !== cat) return '#656d7630'
            return '#656d76'
          },
        },
        barWidth: '50%',
        animation: false
      },
      {
        name: '上涨',
        type: 'bar',
        stack: 'total',
        yAxisIndex: 0,
        data: props.upValues,
        itemStyle: {
          color: (params: any) => {
            const cat = props.categories[params.dataIndex]
            if (props.selectedCategory && props.selectedCategory !== cat) return '#cf222e30'
            return '#cf222e'
          },
        },
        label: {
          show: true,
          position: 'top',
          color: '#24292f',
          fontSize: 11,
          fontWeight: 500,
          formatter: (params: any) => String(props.totalValues[params.dataIndex])
        },
        barWidth: '50%',
        animation: false
      },
      {
        name: '成交额',
        type: 'line',
        yAxisIndex: 1,
        data: props.amountSumValues,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#e16f24', width: 2 },
        itemStyle: { color: '#e16f24' },
        smooth: true,
        animation: false
      },
    ]
  }

  chartInstance.setOption(option)

  chartInstance.off('click')
  chartInstance.on('click', (params: any) => {
    if (params.componentType === 'series') {
      const category = props.categories[params.dataIndex]
      emit('barClick', category)
    }
  })
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
  () => [props.categories, props.upValues, props.downValues, props.flatValues, props.totalValues, props.amountSumValues, props.selectedCategory],
  () => initChart(),
  { deep: true }
)
</script>

<template>
  <div class="stacked-bar-chart">
    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<style scoped>
.stacked-bar-chart {
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
  .stacked-bar-chart {
    height: 250px;
    padding: var(--spacing-md);
  }
}
</style>
