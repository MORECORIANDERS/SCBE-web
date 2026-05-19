<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  StarOutlined,
  SearchOutlined,
  WarningOutlined,
  SettingOutlined
} from '@ant-design/icons-vue'
import NavTabs from '@/components/common/NavTabs.vue'
import BottomNav from '@/components/common/BottomNav.vue'
import QuickEntry from '@/components/common/QuickEntry.vue'
import BondTable from '@/components/common/BondTable.vue'
import RiseFallChart from '@/components/charts/RiseFallChart.vue'
import type { BondData } from '@/components/common/BondTable.vue'
import mockData from '../../mock/data.json'

const router = useRouter()

const riseCount = ref(mockData.marketStats.riseCount)
const fallCount = ref(mockData.marketStats.fallCount)
const flatCount = ref(mockData.marketStats.flatCount)

const totalVolume = ref(mockData.marketStats.totalVolume)
const volumeChange = ref(mockData.marketStats.volumeChange)

const priceMedian = ref(mockData.marketStats.priceMedian)
const changeMedian = ref(mockData.marketStats.changeMedian)
const volumeMedian = ref(mockData.marketStats.volumeMedian)

const riseFallData = ref({
  categories: mockData.riseFallDistribution.categories,
  values: mockData.riseFallDistribution.values
})

const volumeDistributionData = ref(mockData.volumeDistribution)
const priceDistributionData = ref(mockData.priceDistribution)

const bondList = ref<BondData[]>([])

const quickEntries = [
  { icon: StarOutlined, label: '自选转债', path: '/' },
  { icon: SearchOutlined, label: '高级筛选', path: '/scatter' },
  { icon: WarningOutlined, label: '强赎预警', action: () => message.info('强赎预警功能开发中') },
  { icon: SettingOutlined, label: '系统设置', path: '/settings' }
]

const activeMetric = ref('risefall')

const chartTitles: Record<string, string> = {
  risefall: '涨跌分布',
  volume: '成交额分布',
  median: '价格分布'
}

const activeChartData = computed(() => {
  switch (activeMetric.value) {
    case 'volume':
      return volumeDistributionData.value
    case 'median':
      return priceDistributionData.value
    case 'risefall':
    default:
      return riseFallData.value
  }
})

const activeChartTitle = computed(() => chartTitles[activeMetric.value] || '涨跌分布')

const handleMetricClick = (type: string) => {
  activeMetric.value = activeMetric.value === type ? null : type
  if (activeMetric.value === null) {
    activeMetric.value = 'risefall'
  }
}

const handleLogout = () => {
  localStorage.removeItem('isLoggedIn')
  message.success('已退出登录')
  router.push('/login')
}

onMounted(() => {
  bondList.value = (mockData.bonds as BondData[]).slice(0, 10)
})
</script>

<template>
  <div class="home-layout">
    <NavTabs />

    <div class="top-toolbar">
      <div class="toolbar-content">
        <div class="toolbar-left">
          <span class="current-date text-secondary text-sm">
            {{ new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }) }}
          </span>
        </div>
        <div class="toolbar-right">
          <a-button size="small" @click="handleLogout">
            退出登录
          </a-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <div class="page-container">
        <section class="section metrics-section">
          <h2 class="section-title">市场核心指标</h2>
          <div class="metrics-grid">
            <div
              class="metric-card metric-card-risefall"
              :class="{ 'metric-card-active': activeMetric === 'risefall' }"
              @click="handleMetricClick('risefall')"
            >
              <div class="metric-card-header">
                <span class="metric-card-title">涨跌分布</span>
              </div>
              <div class="metric-card-body">
                <div class="risefall-stats">
                  <span class="risefall-stat risefall-stat-rise">{{ riseCount }}</span>
                  <span class="risefall-stat risefall-stat-flat">：{{ flatCount }}：</span>
                  <span class="risefall-stat risefall-stat-fall">{{ fallCount }}</span>
                </div>
              </div>
            </div>

            <div
              class="metric-card metric-card-volume"
              :class="{ 'metric-card-active': activeMetric === 'volume' }"
              @click="handleMetricClick('volume')"
            >
              <div class="metric-card-header">
                <span class="metric-card-title">成交额情况</span>
              </div>
              <div class="metric-card-body">
                <div class="metric-card-value">{{ totalVolume.toFixed(2) }}亿元</div>
                <div class="metric-card-change" :class="volumeChange >= 0 ? 'text-rise' : 'text-fall'">
                  较上日 {{ volumeChange >= 0 ? '+' : '' }}{{ volumeChange.toFixed(2) }}亿元
                </div>
              </div>
            </div>

            <div
              class="metric-card metric-card-median"
              :class="{ 'metric-card-active': activeMetric === 'median' }"
              @click="handleMetricClick('median')"
            >
              <div class="metric-card-header">
                <span class="metric-card-title">中位数</span>
              </div>
              <div class="metric-card-body">
                <div class="median-row">价格：<strong>{{ priceMedian.toFixed(2) }}</strong></div>
                <div class="median-row">涨幅：<strong class="text-rise">{{ changeMedian.toFixed(2) }}%</strong></div>
                <div class="median-row">成交额 <strong>{{ volumeMedian.toFixed(2) }}亿元</strong></div>
              </div>
            </div>
          </div>
        </section>

        <section class="section rise-fall-section">
          <h2 class="section-title">{{ activeChartTitle }}</h2>
          <RiseFallChart
            :categories="activeChartData.categories"
            :values="activeChartData.values"
          />
        </section>

        <section class="section quick-entry-section">
          <h2 class="section-title">快捷功能</h2>
          <div class="quick-entries">
            <QuickEntry
              v-for="(entry, index) in quickEntries"
              :key="index"
              :icon="entry.icon"
              :label="entry.label"
              :path="entry.path"
              :action="entry.action"
            />
          </div>
        </section>

        <section class="section bond-list-section">
          <h2 class="section-title">可转债行情</h2>
          <BondTable :data="bondList" />
        </section>
      </div>
    </div>

    <BottomNav />
  </div>
</template>

<style scoped>
.home-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--color-bg-secondary);
}

.top-toolbar {
  background-color: var(--color-bg-primary);
  border-bottom: 1px solid var(--color-border-light);
  padding: var(--spacing-sm) 0;
}

.toolbar-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 var(--spacing-xl);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-right {
  display: flex;
  gap: var(--spacing-md);
}

.main-content {
  flex: 1;
  padding-bottom: calc(60px + env(safe-area-inset-bottom, 0));
}

.page-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: var(--spacing-lg);
}

.section {
  margin-bottom: var(--spacing-xl);
}

.section-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-md);
}

.metrics-grid {
  display: flex;
  gap: var(--spacing-md);
}

.metrics-grid > * {
  flex: 1 1 0;
  min-width: 0;
  width: 0;
}

.metric-card {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  padding: var(--spacing-md);
  cursor: pointer;
  transition: box-shadow 0.2s, border-color 0.2s;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.metric-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.metric-card-active {
  border-color: var(--color-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
}

.metric-card-header {
  margin-bottom: var(--spacing-sm);
  text-align: center;
}

.metric-card-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.metric-card-body {
  display: flex;
  flex-direction: column;
  justify-content: center;
  flex: 1;
  gap: var(--spacing-xs);
}

.metric-card-value {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.metric-card-change {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
}

.risefall-stats {
  display: flex;
  gap: var(--spacing-sm);
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  line-height: 1;
}

.risefall-stat-rise {
  color: #cf222e;
}

.risefall-stat-flat {
  color: #656d76;
}

.risefall-stat-fall {
  color: #1a7f37;
}

.median-row {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.median-row strong {
  color: var(--color-text-primary);
  font-weight: var(--font-weight-semibold);
}

.quick-entries {
  display: flex;
  gap: var(--spacing-md);
}

@media (max-width: 767px) {
  .page-container {
    padding: var(--spacing-sm);
  }

  .section {
    margin-bottom: var(--spacing-lg);
  }

  .metrics-grid {
    gap: var(--spacing-sm);
  }

  .quick-entries {
    gap: var(--spacing-sm);
  }

  .section-title {
    font-size: var(--font-size-base);
    margin-bottom: var(--spacing-sm);
  }

  .metric-card-value {
    font-size: var(--font-size-base);
  }

  .risefall-stats {
    font-size: var(--font-size-sm);
  }
}
</style>