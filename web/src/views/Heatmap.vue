<script setup lang="ts">
import { ref, onMounted, computed, h } from 'vue'
import { Table, Spin } from 'ant-design-vue'
import NavTabs from '@/components/common/NavTabs.vue'
import BottomNav from '@/components/common/BottomNav.vue'
import mockData from '../../mock/data.json'

// ==================== 类型定义 ====================
interface IndustryItem {
  industry: string
  total: number
  up_count: number
  down_count: number
  flat_count: number
  avg_change: number
  total_amount: number
  avg_amount: number
  change_median: number
}

// ==================== 状态 ====================
const loading = ref(false)
const industryData = ref<IndustryItem[]>([])

// ==================== 数据获取 ====================
const fetchIndustryData = async () => {
  loading.value = true
  await new Promise(r => setTimeout(r, 300))
  industryData.value = mockData.industryStats || []
  loading.value = false
}

// ==================== 行业表格列定义 ====================
const maxChange = computed(() => {
  const vals = industryData.value.map(d => Math.abs(d.change_median))
  return Math.max(...vals, 0.01)
})

const maxAmount = computed(() => {
  return Math.max(...industryData.value.map(d => d.total_amount), 1)
})

const maxAvgAmount = computed(() => {
  return Math.max(...industryData.value.map(d => d.avg_amount), 1)
})

const industryColumns = [
  {
    title: '行业',
    dataIndex: 'industry',
    key: 'industry',
    fixed: 'left' as const,
    align: 'center' as const,
    sorter: (a: IndustryItem, b: IndustryItem) => a.industry.localeCompare(b.industry),
  },
  {
    title: '总数',
    dataIndex: 'total',
    key: 'total',
    align: 'center' as const,
    sorter: (a: IndustryItem, b: IndustryItem) => a.total - b.total,
    customRender: ({ text }: { text: number }) => {
      return h('span', { style: { fontWeight: 500 } }, text)
    },
  },
  {
    title: '下跌',
    dataIndex: 'down_count',
    key: 'down_count',
    align: 'center' as const,
    sorter: (a: IndustryItem, b: IndustryItem) => a.down_count - b.down_count,
    customRender: ({ text }: { text: number }) => {
      return h('span', { style: { color: '#52c41a', fontWeight: 500 } }, text)
    },
  },
  {
    title: '上涨',
    dataIndex: 'up_count',
    key: 'up_count',
    align: 'center' as const,
    sorter: (a: IndustryItem, b: IndustryItem) => a.up_count - b.up_count,
    customRender: ({ text }: { text: number }) => {
      return h('span', { style: { color: '#ff4d4f', fontWeight: 500 } }, text)
    },
  },
  {
    title: '涨幅中位数',
    dataIndex: 'change_median',
    key: 'change_median',
    align: 'center' as const,
    sorter: (a: IndustryItem, b: IndustryItem) => a.change_median - b.change_median,
    customRender: ({ text }: { text: number }) => {
      const pct = Math.min((Math.abs(text) / maxChange.value) * 100, 100)
      return h('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'flex-start', gap: '1px', paddingLeft: '2px' } }, [
        h('span', { style: { color: text >= 0 ? '#ff4d4f' : '#52c41a', fontWeight: 500, fontSize: '13px', minWidth: '52px', textAlign: 'right' } }, `${text >= 0 ? '+' : ''}${text.toFixed(2)}%`),
        h('div', { style: { display: 'flex', alignItems: 'center', width: '90px', height: '16px', borderRadius: '4px', overflow: 'hidden' } }, [
          h('div', { style: { flex: 1, height: '100%', display: 'flex', justifyContent: 'flex-end', backgroundColor: '#f6ffed' } }, [
            text < 0 ? h('div', { style: { width: `${pct}%`, height: '100%', backgroundColor: '#52c41a', borderRadius: '3px 0 0 3px', transition: 'width 0.3s' } }) : null,
          ]),
          h('div', { style: { width: '1px', height: '100%', backgroundColor: '#d0d7de' } }),
          h('div', { style: { flex: 1, height: '100%', backgroundColor: '#fff2f0' } }, [
            text >= 0 ? h('div', { style: { width: `${pct}%`, height: '100%', backgroundColor: '#ff4d4f', borderRadius: '0 3px 3px 0', transition: 'width 0.3s' } }) : null,
          ]),
        ]),
      ])
    },
  },
  {
    title: '成交额（亿）',
    dataIndex: 'total_amount',
    key: 'total_amount',
    align: 'center' as const,
    sorter: (a: IndustryItem, b: IndustryItem) => a.total_amount - b.total_amount,
    customRender: ({ text }: { text: number }) => {
      const pct = (text / maxAmount.value) * 100
      return h('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'flex-start', gap: '1px', paddingLeft: '2px' } }, [
        h('span', { style: { fontWeight: 500, fontSize: '13px', minWidth: '48px', textAlign: 'right' } }, text.toFixed(2)),
        h('div', {
          style: {
            width: '80px',
            height: '16px',
            backgroundColor: '#fffbe6',
            borderRadius: '4px',
            overflow: 'hidden',
          }
        }, [
          h('div', {
            style: {
              width: `${Math.min(pct, 100)}%`,
              height: '100%',
              backgroundColor: '#faad14',
              borderRadius: '4px',
              transition: 'width 0.3s',
            }
          }),
        ]),
      ])
    },
  },
  {
    title: '成交额中位数',
    dataIndex: 'avg_amount',
    key: 'avg_amount',
    align: 'center' as const,
    sorter: (a: IndustryItem, b: IndustryItem) => a.avg_amount - b.avg_amount,
    customRender: ({ text }: { text: number }) => {
      const pct = (text / maxAvgAmount.value) * 100
      return h('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'flex-start', gap: '1px', paddingLeft: '2px' } }, [
        h('span', { style: { fontWeight: 500, fontSize: '13px', minWidth: '48px', textAlign: 'right' } }, text.toFixed(2)),
        h('div', {
          style: {
            width: '80px',
            height: '16px',
            backgroundColor: '#fffbe6',
            borderRadius: '4px',
            overflow: 'hidden',
          }
        }, [
          h('div', {
            style: {
              width: `${Math.min(pct, 100)}%`,
              height: '100%',
              backgroundColor: '#faad14',
              borderRadius: '4px',
              transition: 'width 0.3s',
            }
          }),
        ]),
      ])
    },
  },
]

// ==================== 生命周期 ====================
onMounted(() => {
  fetchIndustryData()
})
</script>

<template>
  <div class="page-layout">
    <NavTabs />

    <div class="main-content">
      <div class="page-container">
        <div class="page-header">
          <h1 class="page-title">行业分析</h1>
        </div>

        <a-spin :spinning="loading">
          <div class="table-wrapper">
            <a-table
              :columns="industryColumns"
              :data-source="industryData"
              :pagination="false"
              :row-key="(record: IndustryItem) => record.industry"
              :scroll="{ x: 'max-content' }"
              size="middle"
              bordered
            />
          </div>
        </a-spin>
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
  padding: var(--spacing-lg) var(--spacing-xl);
}

.page-header {
  margin-bottom: var(--spacing-md);
}

.page-title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.table-wrapper {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  overflow: hidden;
}

:deep(.ant-table-thead > tr > th) {
  text-align: center !important;
  font-weight: var(--font-weight-semibold);
  font-size: 13px;
  padding: 6px 8px !important;
}

:deep(.ant-table-tbody > tr > td) {
  padding: 4px 8px !important;
  font-size: 13px;
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

@media (max-width: 767px) {
  .page-container {
    padding: var(--spacing-sm) var(--spacing-md);
  }

  .page-title {
    font-size: var(--font-size-lg);
  }
}</style>
