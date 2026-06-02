<script setup lang="ts">
import { ref, computed, h, onMounted, watch } from 'vue'
import { Tag, Tabs, Select, Input, InputNumber, message } from 'ant-design-vue'
import NavTabs from '@/components/common/NavTabs.vue'
import BottomNav from '@/components/common/BottomNav.vue'
import { fetchOversold, fetchStrategyWeekly, fetchStrategyVolume } from '@/api'
import type { OversoldBond } from '@/api'

type TabKey = 'daily' | 'weekly' | 'volume'

const activeTab = ref<TabKey>('daily')
const rawData = ref<OversoldBond[]>([])
const loading = ref(false)

const searchText = ref('')
const filterIndustry = ref<string | undefined>(undefined)
const filterOversold = ref<string | undefined>(undefined)
const filterScaleMin = ref<number | undefined>(undefined)
const filterScaleMax = ref<number | undefined>(undefined)

const apiMap: Record<TabKey, () => Promise<OversoldBond[]>> = {
  daily: fetchOversold,
  weekly: fetchStrategyWeekly,
  volume: fetchStrategyVolume
}

async function fetchData() {
  loading.value = true
  try {
    const api = apiMap[activeTab.value]
    if (!api) return
    const data = await api()
    rawData.value = data
  } catch (e) {
    console.error('获取数据失败:', e)
    message.error('获取策略数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})

watch(activeTab, () => {
  searchText.value = ''
  filterIndustry.value = undefined
  filterOversold.value = undefined
  filterScaleMin.value = undefined
  filterScaleMax.value = undefined
  fetchData()
})

const industryOptions = computed(() => {
  const set = new Set(rawData.value.map(d => d.industry_level1))
  return Array.from(set).sort().map(v => ({ value: v, label: v }))
})

const filteredData = computed(() => {
  let list = rawData.value
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(d => d.bond_name.toLowerCase().includes(q) || d.bond_code.toLowerCase().includes(q))
  }
  if (filterIndustry.value) {
    list = list.filter(d => d.industry_level1 === filterIndustry.value)
  }
  if (activeTab.value !== 'volume' && filterOversold.value === 'yes') {
    list = list.filter(d => d.is_oversold)
  } else if (activeTab.value !== 'volume' && filterOversold.value === 'no') {
    list = list.filter(d => !d.is_oversold)
  }
  if (filterScaleMin.value !== undefined) {
    list = list.filter(d => d.remain_scale >= filterScaleMin.value!)
  }
  if (filterScaleMax.value !== undefined) {
    list = list.filter(d => d.remain_scale <= filterScaleMax.value!)
  }
  return list
})

function isOversoldColumns() {
  return activeTab.value === 'daily' || activeTab.value === 'weekly'
}

const columns = computed(() => {
  const common: any[] = [
    {
      title: '转债名称',
      dataIndex: 'bond_name',
      key: 'bond_name',
      align: 'center' as const,
      width: 70,
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      align: 'center' as const,
      width: 80,
      customRender: ({ text }: { text: number }) => {
        return h('span', {}, (text || 0).toFixed(3))
      },
    },
    {
      title: '涨跌幅',
      dataIndex: 'change_percent',
      key: 'change_percent',
      align: 'center' as const,
      width: 80,
      sorter: (a: OversoldBond, b: OversoldBond) => a.change_percent - b.change_percent,
      customRender: ({ text }: { text: number }) => {
        const val = text ?? 0
        const color = val >= 0 ? '#ff4d4f' : '#52c41a'
        const prefix = val >= 0 ? '+' : ''
        return h('span', { style: { color, fontWeight: 500 } }, `${prefix}${val.toFixed(2)}%`)
      },
    },
    {
      title: '行业一级',
      dataIndex: 'industry_level1',
      key: 'industry_level1',
      align: 'center' as const,
      width: 80,
    },
    {
      title: '行业二级',
      dataIndex: 'industry_level2',
      key: 'industry_level2',
      align: 'center' as const,
      width: 90,
    },
    {
      title: '行业三级',
      dataIndex: 'industry_level3',
      key: 'industry_level3',
      align: 'center' as const,
      width: 130
    },
    {
      title: '剩余规模',
      dataIndex: 'remain_scale',
      key: 'remain_scale',
      align: 'center' as const,
      width: 80,
      sorter: (a: OversoldBond, b: OversoldBond) => a.remain_scale - b.remain_scale,
      customRender: ({ text }: { text: number }) => {
        return h('span', {}, (text || 0).toFixed(2))
      },
    },
    {
      title: '到期日期',
      dataIndex: 'maturity_date',
      key: 'maturity_date',
      align: 'center' as const,
      width: 100,
    },
  ]

  if (isOversoldColumns()) {
    common.splice(3, 0,
      {
        title: '超卖',
        dataIndex: 'is_oversold',
        key: 'is_oversold',
        align: 'center' as const,
        width: 60,
        customRender: ({ text }: { text: boolean }) => {
          return h(Tag, { color: text ? 'red' : 'default' }, () => text ? '是' : '否')
        },
      },
      {
        title: 'CCI',
        dataIndex: 'cci',
        key: 'cci',
        align: 'center' as const,
        width: 80,
        sorter: (a: OversoldBond, b: OversoldBond) => a.cci - b.cci,
        customRender: ({ text }: { text: number }) => {
          return h(Tag, { color: text < -100 ? 'red' : 'default' }, () => (text ?? 0).toFixed(2))
        },
      },
      {
        title: 'WR',
        dataIndex: 'wr',
        key: 'wr',
        align: 'center' as const,
        width: 80,
        sorter: (a: OversoldBond, b: OversoldBond) => a.wr - b.wr,
        customRender: ({ text }: { text: number }) => {
          return h(Tag, { color: text > 80 ? 'red' : 'default' }, () => (text ?? 0).toFixed(2))
        },
      }
    )
  } else {
    common.splice(3, 0,
      {
        title: '成交额(亿)',
        dataIndex: 'amount_yi',
        key: 'amount_yi',
        align: 'center' as const,
        width: 90,
        sorter: (a: OversoldBond, b: OversoldBond) => a.amount_yi - b.amount_yi,
        customRender: ({ text }: { text: number }) => {
          return h('span', { style: { fontWeight: 500 } }, (text ?? 0).toFixed(3))
        },
      },
      {
        title: '前5日均额(亿)',
        dataIndex: 'avg_amount_yi',
        key: 'avg_amount_yi',
        align: 'center' as const,
        width: 90,
        sorter: (a: OversoldBond, b: OversoldBond) => a.avg_amount_yi - b.avg_amount_yi,
        customRender: ({ text }: { text: number }) => {
          return h('span', {}, (text ?? 0).toFixed(4))
        },
      },
      {
        title: '倍数',
        dataIndex: 'volume_ratio',
        key: 'volume_ratio',
        align: 'center' as const,
        width: 60,
        sorter: (a: OversoldBond, b: OversoldBond) => a.volume_ratio - b.volume_ratio,
        customRender: ({ text }: { text: number }) => {
          const val = text ?? 0
          return h('span', { style: { color: val >= 2 ? '#ff4d4f' : 'inherit', fontWeight: 500 } }, `${val.toFixed(2)}x`)
        },
      },
    )
  }

  return common
})
</script>

<template>
  <div class="page-layout">
    <NavTabs />

    <div class="main-content">
      <div class="page-container">
        <div class="page-header">
          <h1 class="page-title">策略分析</h1>
          <Tabs v-model:activeKey="activeTab" @change="fetchData" size="small">
            <Tabs.TabPane key="daily" tab="日线超卖" />
            <Tabs.TabPane key="weekly" tab="周线超卖" />
            <Tabs.TabPane key="volume" tab="成交额2倍" />
          </Tabs>
        </div>

        <section class="section">
          <div class="filter-bar">
            <Input
              v-model:value="searchText"
              placeholder="搜索转债名称/代码"
              style="width: 200px"
              size="small"
              allow-clear
            />
            <Select
              v-model:value="filterIndustry"
              placeholder="行业筛选"
              style="width: 140px"
              size="small"
              :options="industryOptions"
              allow-clear
            />
            <Select
              v-if="activeTab !== 'volume'"
              v-model:value="filterOversold"
              placeholder="是否超卖"
              style="width: 120px"
              size="small"
              allow-clear
            >
              <Select.Option value="yes">是</Select.Option>
              <Select.Option value="no">否</Select.Option>
            </Select>
          </div>
          <div class="filter-bar" style="margin-top: 6px">
            <span class="filter-label">剩余规模</span>
            <InputNumber
              v-model:value="filterScaleMin"
              placeholder="最小值"
              :min="0"
              :precision="2"
              size="small"
              style="width: 100px"
            />
            <span class="filter-sep">—</span>
            <InputNumber
              v-model:value="filterScaleMax"
              placeholder="最大值"
              :min="0"
              :precision="2"
              size="small"
              style="width: 100px"
            />
          </div>
        </section>

        <section class="section">
          <div v-if="filteredData.length > 0">
            <div class="table-wrapper">
              <a-table
                :columns="columns"
                :data-source="filteredData"
                :pagination="false"
                :row-key="(record: OversoldBond) => record.bond_code"
                :scroll="{ y: 600, x: 'max-content' }"
                size="small"
                bordered
              />
            </div>
          </div>
          <div v-else class="empty-state">
            <a-tag color="blue">{{ loading ? '加载中...' : '暂无匹配数据' }}</a-tag>
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
  margin-bottom: var(--spacing-lg);
  flex-wrap: wrap;
  gap: var(--spacing-md);
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.section {
  margin-bottom: var(--spacing-lg);
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.filter-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.filter-sep {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.table-wrapper {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  overflow: hidden;
}

:deep(.ant-table-tbody > tr > td) {
  padding: 2px 4px !important;
  font-size: 12px;
}

:deep(.ant-table-thead > tr > th) {
  text-align: center !important;
  font-size: 12px;
  padding: 4px 4px !important;
}

:deep(.ant-table-body::-webkit-scrollbar) {
  display: none;
}

:deep(.ant-table-body) {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

:deep(.ant-table-ping-right:not(.ant-table-has-fix-right) .ant-table-container::after) {
  box-shadow: none;
}

:deep(.ant-tag) {
  margin-inline-end: 0;
}

.empty-state {
  padding: 40px;
  text-align: center;
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
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
}
</style>
