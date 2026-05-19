<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { DatePicker } from 'ant-design-vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import NavTabs from '@/components/common/NavTabs.vue'
import BottomNav from '@/components/common/BottomNav.vue'
import mockData from '../../mock/data.json'

const selectedDate = ref<string>(new Date().toISOString().split('T')[0])

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const industryColors: Record<string, string> = {
  '银行': '#0969da',
  '光伏': '#1a7f37',
  '电子': '#8250df',
  '化工': '#bf8700',
  '食品': '#cf222e',
  '医药': '#0550ae',
  '汽车': '#8c959f',
  '环保': '#2da44e',
  '通信': '#6e7781',
  '证券': '#a371f7'
}

const initChart = () => {
  if (!chartRef.value) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  const bonds = mockData.bonds

  const series = Object.keys(industryColors).map(industry => {
    const industryBonds = bonds.filter(bond => bond.industry === industry)
    return {
      name: industry,
      type: 'scatter',
      data: industryBonds.map(bond => [bond.premium, bond.price, bond]),
      symbolSize: 8,
      itemStyle: {
        color: industryColors[industry]
      }
    }
  })

  const option: EChartsOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: '#ffffff',
      borderColor: '#d0d7de',
      borderWidth: 1,
      textStyle: {
        color: '#24292f',
        fontSize: 12
      },
      formatter: (params: any) => {
        const bond = params.data[2]
        return `
          <div style="font-weight: 500; margin-bottom: 4px;">${bond.name} (${bond.code})</div>
          <div>转债价格: <strong>${bond.price.toFixed(2)}</strong></div>
          <div>转股溢价率: <strong>${bond.premium.toFixed(2)}%</strong></div>
          <div>双低数值: <strong>${bond.doubleLow.toFixed(2)}</strong></div>
          <div>行业: ${bond.industry}</div>
        `
      }
    },
    legend: {
      orient: 'horizontal',
      bottom: 10,
      textStyle: {
        color: '#656d76',
        fontSize: 11
      },
      itemWidth: 12,
      itemHeight: 12,
      pageTextStyle: {
        color: '#656d76'
      }
    },
    grid: {
      left: '5%',
      right: '5%',
      bottom: '15%',
      top: '5%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '转股溢价率 (%)',
      nameTextStyle: {
        color: '#656d76',
        fontSize: 12,
        padding: [0, 0, 0, -20]
      },
      axisLine: {
        lineStyle: {
          color: '#d0d7de'
        }
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
    yAxis: {
      type: 'value',
      name: '转债价格 (元)',
      nameTextStyle: {
        color: '#656d76',
        fontSize: 12,
        padding: [0, 0, 0, -20]
      },
      axisLine: {
        show: false
      },
      axisLabel: {
        color: '#656d76',
        fontSize: 11,
        formatter: '{value}'
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
    series: series,
    animation: false
  }

  chartInstance.setOption(option)
}

onMounted(() => {
  initChart()
})
</script>

<template>
  <div class="page-layout">
    <NavTabs />

    <div class="main-content">
      <div class="page-container">
        <div class="page-header">
          <h1 class="page-title">双低散点分析</h1>
          <div class="page-controls">
            <a-date-picker
              v-model:value="selectedDate"
              size="small"
            />
          </div>
        </div>

        <section class="section">
          <h2 class="section-title">价格 vs 溢价率分布</h2>
          <div class="chart-container">
            <div ref="chartRef" class="chart"></div>
          </div>
          <div class="chart-legend-note">
            <p class="text-secondary text-sm">
              * X轴：转股溢价率（越低越好）<br>
              * Y轴：转债价格（越低越好）<br>
              * 右下角区域为双低优选区域
            </p>
          </div>
        </section>

        <section class="section">
          <div class="tips-card">
            <h3 class="tips-title">双低策略说明</h3>
            <p class="text-secondary text-sm">
              双低 = 转债价格 + 转股溢价率 × 100<br><br>
              双低数值越小，表示转债价格越低、溢价率越低，投资价值相对越高。<br>
              该策略适合寻找安全边际较高、进攻性较强的可转债标的。
            </p>
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
  height: 500px;
}

.chart-legend-note {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background-color: var(--color-bg-secondary);
  border-radius: var(--radius-small);
}

.tips-card {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  padding: var(--spacing-lg);
}

.tips-title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-md);
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
    height: 350px;
  }
}
</style>
