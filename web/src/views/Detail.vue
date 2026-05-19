<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Table } from 'ant-design-vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import NavTabs from '@/components/common/NavTabs.vue'
import BottomNav from '@/components/common/BottomNav.vue'
import mockData from '../../mock/data.json'

const route = useRoute()
const router = useRouter()

const bondCode = computed(() => route.params.code as string)

const bondInfo = ref<any>(null)
const historyData = ref<any[]>([])
const priceChartRef = ref<HTMLElement | null>(null)
const premiumChartRef = ref<HTMLElement | null>(null)
let priceChartInstance: echarts.ECharts | null = null
let premiumChartInstance: echarts.ECharts | null = null

onMounted(() => {
  const bond = mockData.bonds.find(b => b.code === bondCode.value)
  if (bond) {
    bondInfo.value = bond
    historyData.value = mockData.bondHistory[bondCode.value]?.historyPrices || [
      { date: '2024-01-15', price: 122.34, premium: 9.5 },
      { date: '2024-01-16', price: 123.56, premium: 9.2 },
      { date: '2024-01-17', price: 124.78, premium: 8.9 },
      { date: '2024-01-18', price: 125.12, premium: 8.7 },
      { date: '2024-01-19', price: 126.45, premium: 8.5 },
      { date: '2024-01-20', price: 127.23, premium: 8.6 },
      { date: '2024-01-21', price: bond.price, premium: bond.premium }
    ]
    initCharts()
  }
})

const initCharts = () => {
  if (priceChartRef.value) {
    priceChartInstance = echarts.init(priceChartRef.value)
    const priceOption: EChartsOption = {
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#ffffff',
        borderColor: '#d0d7de',
        borderWidth: 1,
        textStyle: {
          color: '#24292f',
          fontSize: 12
        }
      },
      grid: {
        left: '5%',
        right: '5%',
        bottom: '10%',
        top: '10%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: historyData.value.map(item => item.date),
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
        name: '价格 (元)',
        nameTextStyle: {
          color: '#656d76',
          fontSize: 11
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
          name: '转债价格',
          type: 'line',
          data: historyData.value.map(item => item.price),
          smooth: true,
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: {
            color: '#0969da',
            width: 2
          },
          itemStyle: {
            color: '#0969da'
          },
          animation: false
        }
      ]
    }
    priceChartInstance.setOption(priceOption)
  }

  if (premiumChartRef.value) {
    premiumChartInstance = echarts.init(premiumChartRef.value)
    const premiumOption: EChartsOption = {
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#ffffff',
        borderColor: '#d0d7de',
        borderWidth: 1,
        textStyle: {
          color: '#24292f',
          fontSize: 12
        },
        formatter: (params: any) => {
          const value = params[0].value
          return `${params[0].axisValue}<br/>溢价率: <strong>${value}%</strong>`
        }
      },
      grid: {
        left: '5%',
        right: '5%',
        bottom: '10%',
        top: '10%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: historyData.value.map(item => item.date),
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
        name: '溢价率 (%)',
        nameTextStyle: {
          color: '#656d76',
          fontSize: 11
        },
        axisLine: {
          show: false
        },
        axisLabel: {
          color: '#656d76',
          fontSize: 11,
          formatter: '{value}%'
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
          name: '溢价率',
          type: 'line',
          data: historyData.value.map(item => item.premium),
          smooth: true,
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: {
            color: '#cf222e',
            width: 2
          },
          itemStyle: {
            color: '#cf222e'
          },
          animation: false
        }
      ]
    }
    premiumChartInstance.setOption(premiumOption)
  }
}

const handleBack = () => {
  router.back()
}

const getChangeClass = (value: number) => {
  if (value > 0) return 'text-rise'
  if (value < 0) return 'text-fall'
  return 'text-flat'
}

const columns = [
  {
    title: '日期',
    dataIndex: 'date',
    key: 'date'
  },
  {
    title: '转债价格',
    dataIndex: 'price',
    key: 'price',
    customRender: ({ text }: { text: number }) => `¥${text.toFixed(2)}`
  },
  {
    title: '溢价率',
    dataIndex: 'premium',
    key: 'premium',
    customRender: ({ text }: { text: number }) => `${text.toFixed(2)}%`
  }
]
</script>

<template>
  <div class="page-layout">
    <NavTabs />

    <div class="main-content">
      <div class="page-container">
        <div class="page-header">
          <div class="header-left">
            <a-button @click="handleBack" size="small">
              ← 返回
            </a-button>
            <h1 class="page-title">{{ bondInfo?.name || '加载中...' }}</h1>
          </div>
          <span class="bond-code text-secondary">{{ bondCode }}</span>
        </div>

        <div v-if="bondInfo">
          <!-- 基本信息卡片 -->
          <section class="section">
            <div class="info-card">
              <div class="info-header">
                <h2 class="info-title">基础信息</h2>
              </div>
              <div class="info-grid">
                <div class="info-item">
                  <span class="info-label">转债代码</span>
                  <span class="info-value">{{ bondInfo.code }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">转债名称</span>
                  <span class="info-value">{{ bondInfo.name }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">正股价格</span>
                  <span class="info-value">¥{{ bondInfo.stockPrice.toFixed(2) }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">正股涨跌</span>
                  <span class="info-value" :class="getChangeClass(bondInfo.stockChangePercent)">
                    {{ bondInfo.stockChangePercent > 0 ? '+' : '' }}{{ bondInfo.stockChangePercent.toFixed(2) }}%
                  </span>
                </div>
                <div class="info-item">
                  <span class="info-label">转股溢价率</span>
                  <span class="info-value">{{ bondInfo.premium.toFixed(2) }}%</span>
                </div>
                <div class="info-item">
                  <span class="info-label">剩余规模</span>
                  <span class="info-value">{{ bondInfo.remainSize.toFixed(2) }}亿</span>
                </div>
                <div class="info-item">
                  <span class="info-label">所属行业</span>
                  <span class="info-value">{{ bondInfo.industry }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">双低数值</span>
                  <span class="info-value font-semibold">{{ bondInfo.doubleLow.toFixed(2) }}</span>
                </div>
              </div>
            </div>
          </section>

          <!-- 价格走势 -->
          <section class="section">
            <h2 class="section-title">历史价格走势</h2>
            <div class="chart-container">
              <div ref="priceChartRef" class="chart"></div>
            </div>
          </section>

          <!-- 溢价率走势 -->
          <section class="section">
            <h2 class="section-title">历史溢价率走势</h2>
            <div class="chart-container">
              <div ref="premiumChartRef" class="chart"></div>
            </div>
          </section>

          <!-- 历史行情表格 -->
          <section class="section">
            <h2 class="section-title">历史行情</h2>
            <div class="table-wrapper">
              <a-table
                :columns="columns"
                :data-source="historyData"
                :pagination="false"
                :row-key="(record: any) => record.date"
                size="middle"
              />
            </div>
          </section>
        </div>

        <div v-else class="loading-state">
          <p class="text-secondary">正在加载数据...</p>
        </div>
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

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.bond-code {
  font-size: var(--font-size-sm);
  font-family: monospace;
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

.info-card {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  padding: var(--spacing-lg);
}

.info-header {
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--color-border-light);
}

.info-title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-lg);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.info-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.info-value {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

.chart-container {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  padding: var(--spacing-lg);
}

.chart {
  width: 100%;
  height: 300px;
}

.table-wrapper {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  overflow: hidden;
}

.loading-state {
  text-align: center;
  padding: var(--spacing-xxl);
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

  .info-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .chart {
    height: 250px;
  }
}
</style>
