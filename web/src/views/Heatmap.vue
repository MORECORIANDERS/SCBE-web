<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { DatePicker, Segmented } from 'ant-design-vue'
import { Table } from 'ant-design-vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import NavTabs from '@/components/common/NavTabs.vue'
import BottomNav from '@/components/common/BottomNav.vue'
import mockData from '../../mock/data.json'

const selectedDate = ref<string>(new Date().toISOString().split('T')[0])
const selectedDimension = ref<'premium' | 'doubleLow'>('premium')

const industryData = ref(mockData.industryData)

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const dimensionLabels = {
  premium: '转股溢价率',
  doubleLow: '双低数值'
}

const initChart = () => {
  if (!chartRef.value) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  const data = industryData.value.map(item => ({
    name: item.industry,
    value: selectedDimension.value === 'premium' ? item.avgPremium : item.avgDoubleLow
  }))

  const sortedData = [...data].sort((a, b) => b.value - a.value)

  const option: EChartsOption = {
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
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: sortedData.map(item => item.name),
      axisLine: {
        lineStyle: {
          color: '#d0d7de'
        }
      },
      axisLabel: {
        color: '#656d76',
        fontSize: 11,
        interval: 0,
        rotate: 45
      },
      axisTick: {
        show: false
      }
    },
    yAxis: {
      type: 'value',
      name: dimensionLabels[selectedDimension.value],
      nameTextStyle: {
        color: '#656d76',
        fontSize: 12
      },
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
        name: dimensionLabels[selectedDimension.value],
        type: 'bar',
        data: sortedData.map(item => item.value),
        itemStyle: {
          color: (params: any) => {
            const value = params.value
            const max = Math.max(...sortedData.map(item => item.value))
            const min = Math.min(...sortedData.map(item => item.value))
            const ratio = (value - min) / (max - min)
            const color = selectedDimension.value === 'premium' ? '#cf222e' : '#0969da'
            const alpha = 0.3 + ratio * 0.7
            return color + Math.round(alpha * 255).toString(16).padStart(2, '0')
          },
          borderRadius: [0, 0, 0, 0]
        },
        barWidth: '50%',
        animation: false
      }
    ]
  }

  chartInstance.setOption(option)
}

onMounted(() => {
  initChart()
})

watch(selectedDimension, () => {
  initChart()
})

const columns = [
  {
    title: '行业',
    dataIndex: 'industry',
    key: 'industry'
  },
  {
    title: '平均溢价率',
    dataIndex: 'avgPremium',
    key: 'avgPremium',
    sorter: (a: any, b: any) => a.avgPremium - b.avgPremium,
    customRender: ({ text }: { text: number }) => `${text.toFixed(2)}%`
  },
  {
    title: '平均双低',
    dataIndex: 'avgDoubleLow',
    key: 'avgDoubleLow',
    sorter: (a: any, b: any) => a.avgDoubleLow - b.avgDoubleLow,
    customRender: ({ text }: { text: number }) => text.toFixed(2)
  },
  {
    title: '转债数量',
    dataIndex: 'count',
    key: 'count',
    sorter: (a: any, b: any) => a.count - b.count
  }
]

const formatNumber = (num: number) => {
  return num.toFixed(2)
}
</script>

<template>
  <div class="page-layout">
    <NavTabs />

    <div class="main-content">
      <div class="page-container">
        <div class="page-header">
          <h1 class="page-title">行业热力图</h1>
          <div class="page-controls">
            <a-date-picker
              v-model:value="selectedDate"
              size="small"
              style="width: 150px"
            />
            <a-segmented
              v-model:value="selectedDimension"
              :options="[
                { label: '溢价率', value: 'premium' },
                { label: '双低数值', value: 'doubleLow' }
              ]"
            />
          </div>
        </div>

        <section class="section">
          <h2 class="section-title">{{ dimensionLabels[selectedDimension] }}分布</h2>
          <div class="chart-container">
            <div ref="chartRef" class="chart"></div>
          </div>
        </section>

        <section class="section">
          <h2 class="section-title">行业均值排行</h2>
          <div class="table-wrapper">
            <a-table
              :columns="columns"
              :data-source="industryData"
              :pagination="{ pageSize: 10 }"
              :row-key="(record: any) => record.industry"
              size="middle"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'avgPremium'">
                  <span class="text-fall">{{ formatNumber(record.avgPremium) }}%</span>
                </template>
                <template v-else-if="column.key === 'avgDoubleLow'">
                  <span class="font-medium">{{ formatNumber(record.avgDoubleLow) }}</span>
                </template>
              </template>
            </a-table>
          </div>
        </section>
      </div>
    </div>

    <BottomNav />
  </div>
</template>

<style scoped>
.page-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--color-bg-secondary);
}

.main-content {
  flex: 1;
  padding-bottom: calc(60px + env(safe-area-inset-bottom, 0));
}

.page-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: var(--spacing-xl);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xl);
  flex-wrap: wrap;
  gap: var(--spacing-md);
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.page-controls {
  display: flex;
  gap: var(--spacing-md);
  align-items: center;
  flex-wrap: wrap;
}

.section {
  margin-bottom: var(--spacing-xl);
}

.section-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-lg);
}

.chart-container {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  padding: var(--spacing-lg);
}

.chart {
  width: 100%;
  height: 400px;
}

.table-wrapper {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  overflow: hidden;
}

@media (max-width: 767px) {
  .page-container {
    padding: var(--spacing-md);
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .page-title {
    font-size: var(--font-size-xl);
  }

  .chart {
    height: 300px;
  }
}
</style>
