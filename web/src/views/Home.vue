<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  StarOutlined,
  SearchOutlined,
  WarningOutlined,
  SettingOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue'
import NavTabs from '@/components/common/NavTabs.vue'
import BottomNav from '@/components/common/BottomNav.vue'
import QuickEntry from '@/components/common/QuickEntry.vue'
import BondTable from '@/components/common/BondTable.vue'
import RiseFallChart from '@/components/charts/RiseFallChart.vue'
import StackedBarChart from '@/components/charts/StackedBarChart.vue'
import type { BondData } from '@/components/common/BondTable.vue'
import { fetchAll, refreshData } from '@/api'

const router = useRouter()

const loading = ref(false)
const refreshing = ref(false)

const riseCount = ref(0)
const fallCount = ref(0)
const flatCount = ref(0)
const totalVolume = ref(0)
const volumeChange = ref(0)
const priceMedian = ref(0)
const changeMedian = ref(0)
const volumeMedian = ref(0)

const RISE_FALL_CATEGORIES = ['跌停', '<-7%', '-7~-5%', '-5~-3%', '-3~0%', '0', '0~3%', '3~5%', '5~7%', '>7%', '涨停']

function getChangeCategory(changePct: number): string {
  if (changePct >= 19.8) return '涨停'
  if (changePct > 7) return '>7%'
  if (changePct >= 5) return '5~7%'
  if (changePct >= 3) return '3~5%'
  if (changePct > 0) return '0~3%'
  if (changePct === 0) return '0'
  if (changePct > -3) return '-3~0%'
  if (changePct >= -5) return '-5~-3%'
  if (changePct >= -7) return '-7~-5%'
  if (changePct > -19.8) return '<-7%'
  return '跌停'
}

const riseFallData = computed(() => {
  const counts: Record<string, number> = {}
  for (const cat of RISE_FALL_CATEGORIES) {
    counts[cat] = 0
  }
  for (const bond of bondList.value) {
    const cat = getChangeCategory(bond.changePercent)
    counts[cat]++
  }
  const values = RISE_FALL_CATEGORIES.map(cat => counts[cat])
  return { categories: RISE_FALL_CATEGORIES, values }
})

const volumeDistributionData = computed(() => {
  const ranges = [
    { label: '<1亿', max: 1 },
    { label: '1~5亿', max: 5 },
    { label: '5~10亿', max: 10 },
    { label: '10~50亿', max: 50 },
    { label: '50亿+', max: Infinity },
  ]
  const counts = ranges.map(() => 0)
  for (const bond of bondList.value) {
    const idx = ranges.findIndex(r => bond.amount < r.max)
    if (idx >= 0) counts[idx]++
  }
  return { categories: ranges.map(r => r.label), values: counts }
})

const priceDistributionData = computed(() => {
  const ranges = [
    { label: '<100', max: 100 },
    { label: '100~110', max: 110 },
    { label: '110~120', max: 120 },
    { label: '120~130', max: 130 },
    { label: '130~140', max: 140 },
    { label: '140~150', max: 150 },
    { label: '150~160', max: 160 },
    { label: '160~200', max: 200 },
    { label: '200+', max: Infinity },
  ]
  const upCounts = ranges.map(() => 0)
  const downCounts = ranges.map(() => 0)
  const flatCounts = ranges.map(() => 0)
  const amounts: number[][] = ranges.map(() => [])
  for (const bond of bondList.value) {
    const idx = ranges.findIndex(r => bond.price < r.max)
    if (idx < 0) continue
    if (bond.changePercent > 0) upCounts[idx]++
    else if (bond.changePercent < 0) downCounts[idx]++
    else flatCounts[idx]++
    amounts[idx].push(bond.amount)
  }
  const amountSumValues = amounts.map(arr => +arr.reduce((s, v) => s + v, 0).toFixed(2))
  const amountMedianValues = amounts.map(arr => {
    if (arr.length === 0) return 0
    const sorted = [...arr].sort((a, b) => a - b)
    const mid = Math.floor(sorted.length / 2)
    return +sorted[mid].toFixed(2)
  })
  return {
    categories: ranges.map(r => r.label),
    upValues: upCounts,
    downValues: downCounts,
    flatValues: flatCounts,
    totalValues: upCounts.map((_, i) => upCounts[i] + downCounts[i] + flatCounts[i]),
    amountSumValues,
    amountMedianValues,
  }
})

const bondList = ref<BondData[]>([])
const selectedChangeCategory = ref<string | null>(null)
const selectedPriceRange = ref<string | null>(null)
const selectedVolumeRange = ref<string | null>(null)

function getPriceRange(price: number): string {
  if (price < 100) return '<100'
  if (price < 110) return '100~110'
  if (price < 120) return '110~120'
  if (price < 130) return '120~130'
  if (price < 140) return '130~140'
  if (price < 150) return '140~150'
  if (price < 160) return '150~160'
  if (price < 200) return '160~200'
  return '200+'
}

function getVolumeRange(amount: number): string {
  if (amount < 1) return '<1亿'
  if (amount < 5) return '1~5亿'
  if (amount < 10) return '5~10亿'
  if (amount < 50) return '10~50亿'
  return '50亿+'
}

const filteredBondList = computed(() => {
  let list = [...bondList.value]
  if (selectedChangeCategory.value) {
    list = list.filter(b => getChangeCategory(b.changePercent) === selectedChangeCategory.value)
  }
  if (selectedPriceRange.value) {
    list = list.filter(b => getPriceRange(b.price) === selectedPriceRange.value)
  }
  if (selectedVolumeRange.value) {
    list = list.filter(b => getVolumeRange(b.amount) === selectedVolumeRange.value)
  }
  list.sort((a, b) => b.changePercent - a.changePercent)
  return list
})

const quickEntries = [
  { icon: StarOutlined, label: '自选转债', path: '/' },
  { icon: SearchOutlined, label: '高级筛选', path: '/scatter' },
  { icon: WarningOutlined, label: '强赎预警', action: () => message.info('强赎预警功能开发中') },
  { icon: SettingOutlined, label: '系统设置', path: '/settings' }
]

const activeMetric = ref<string>('risefall')

const activeChartData = computed(() => {
  if (activeMetric.value === 'volume') {
    return volumeDistributionData.value
  }
  return riseFallData.value
})

const activeChartTitle = computed(() => {
  if (activeMetric.value === 'volume') return '成交额分布'
  if (activeMetric.value === 'median') return '价格分布'
  return '涨跌分布'
})

const handleMetricClick = (type: string) => {
  activeMetric.value = activeMetric.value === type ? '' : type
}

const handleLogout = () => {
  localStorage.removeItem('isLoggedIn')
  message.success('已退出登录')
  router.push('/login')
}

async function loadData() {
  try {
    const data = await fetchAll()
    if (data.marketStats) {
      riseCount.value = data.marketStats.upCount
      fallCount.value = data.marketStats.downCount
      flatCount.value = data.marketStats.flatCount
      totalVolume.value = data.marketStats.totalVolume
      priceMedian.value = data.marketStats.priceMedian
      changeMedian.value = data.marketStats.changeMedian
      volumeMedian.value = data.marketStats.volumeMedian
      volumeChange.value = data.marketStats.volumeChange ?? 0
    }
    if (data.bonds?.length) {
      bondList.value = data.bonds.map(b => ({
        code: b.code,
        name: b.name,
        price: b.price,
        changePercent: b.change_pct,
        amount: b.amount,
        industry1: b.industry,
        industry2: b.industry2,
        remainSize: b.latest_amount,
        maturityDate: b.maturity_date,
      }))
    }
  } catch (e: any) {
    message.error('数据加载失败: ' + (e.message || '未知错误'))
  }
}

async function handleRefresh() {
  refreshing.value = true
  message.loading({ content: '正在采集最新数据...', key: 'refresh' })
  try {
    selectedChangeCategory.value = null
    selectedPriceRange.value = null
    selectedVolumeRange.value = null
    await refreshData()
    await loadData()
    message.success({ content: '数据已更新', key: 'refresh' })
  } catch {
    message.error({ content: '刷新失败', key: 'refresh' })
  } finally {
    refreshing.value = false
  }
}

function handleChangeBarClick(category: string) {
  selectedChangeCategory.value = selectedChangeCategory.value === category ? null : category
  selectedPriceRange.value = null
  selectedVolumeRange.value = null
}

function handlePriceBarClick(category: string) {
  selectedPriceRange.value = selectedPriceRange.value === category ? null : category
  selectedChangeCategory.value = null
  selectedVolumeRange.value = null
}

function handleVolumeBarClick(category: string) {
  selectedVolumeRange.value = selectedVolumeRange.value === category ? null : category
  selectedChangeCategory.value = null
  selectedPriceRange.value = null
}

onMounted(() => {
  loading.value = true
  loadData().finally(() => { loading.value = false })
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
          <a-button
            size="small"
            :loading="refreshing"
            :icon="h(ReloadOutlined)"
            @click="handleRefresh"
          >
            刷新数据
          </a-button>
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
                  <span class="risefall-stat risefall-stat-flat">:{{ flatCount }}:</span>
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
          <h2 class="section-title">
            {{ activeChartTitle }}
            <template v-if="activeMetric === 'risefall' && selectedChangeCategory">
              <span class="filter-hint">— 筛选: {{ selectedChangeCategory }}</span>
              <a-button size="small" type="link" @click="selectedChangeCategory = null">清除</a-button>
            </template>
            <template v-else-if="activeMetric === 'volume' && selectedVolumeRange">
              <span class="filter-hint">— 筛选: {{ selectedVolumeRange }}</span>
              <a-button size="small" type="link" @click="selectedVolumeRange = null">清除</a-button>
            </template>
            <template v-else-if="activeMetric === 'median' && selectedPriceRange">
              <span class="filter-hint">— 筛选: {{ selectedPriceRange }}</span>
              <a-button size="small" type="link" @click="selectedPriceRange = null">清除</a-button>
            </template>
          </h2>
          <template v-if="activeMetric === 'median'">
            <StackedBarChart
              :categories="priceDistributionData.categories"
              :up-values="priceDistributionData.upValues"
              :down-values="priceDistributionData.downValues"
              :flat-values="priceDistributionData.flatValues"
              :total-values="priceDistributionData.totalValues"
              :amount-sum-values="priceDistributionData.amountSumValues"
              :amount-median-values="priceDistributionData.amountMedianValues"
              :selected-category="selectedPriceRange"
              @bar-click="handlePriceBarClick($event)"
            />
          </template>
          <template v-else>
            <RiseFallChart
              :categories="activeChartData.categories"
              :values="activeChartData.values"
              :selected-category="activeMetric === 'risefall' ? selectedChangeCategory : selectedVolumeRange"
              @bar-click="activeMetric === 'risefall' ? handleChangeBarClick($event) : handleVolumeBarClick($event)"
            />
          </template>
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
          <h2 class="section-title">
            可转债行情
            <template v-if="selectedChangeCategory">
              <span class="filter-hint">— 筛: {{ selectedChangeCategory }}</span>
              <a-button size="small" type="link" @click="selectedChangeCategory = null; selectedPriceRange = null; selectedVolumeRange = null">清除</a-button>
            </template>
            <template v-else-if="selectedPriceRange">
              <span class="filter-hint">— 筛: {{ selectedPriceRange }}</span>
              <a-button size="small" type="link" @click="selectedPriceRange = null; selectedChangeCategory = null; selectedVolumeRange = null">清除</a-button>
            </template>
            <template v-else-if="selectedVolumeRange">
              <span class="filter-hint">— 筛: {{ selectedVolumeRange }}</span>
              <a-button size="small" type="link" @click="selectedVolumeRange = null; selectedChangeCategory = null; selectedPriceRange = null">清除</a-button>
            </template>
          </h2>
          <BondTable :data="filteredBondList" />
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
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.filter-hint {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-normal);
  color: var(--color-text-secondary);
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
  justify-content: center;
  gap: 2px;
  font-size: 50px;
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