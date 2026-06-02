<script setup lang="ts">
import { useRouter } from 'vue-router'
import { computed } from 'vue'

export interface BondData {
  code: string
  name: string
  price: number
  changePercent: number
  amount: number
  industry1: string
  industry2: string
  remainSize: number
  maturityDate: string
  isNew?: boolean
}

const props = defineProps<{
  data: BondData[]
}>()

const maxAmount = computed(() => {
  if (props.data.length === 0) return 10
  const max = Math.max(...props.data.map(b => b.amount))
  return Math.max(max, 0.1)
})

const router = useRouter()

const handleRowClick = (record: BondData) => {
  router.push(`/detail/${record.code}`)
}

const columns = [
  {
    title: '转债名称',
    dataIndex: 'name',
    key: 'name',
    fixed: 'left',
    width: 70
  },
  {
    title: '转债价格',
    dataIndex: 'price',
    key: 'price',
    width: 80,
    align: 'right',
    sorter: (a: BondData, b: BondData) => a.price - b.price
  },
  {
    title: '涨跌幅',
    dataIndex: 'changePercent',
    key: 'changePercent',
    width: 80,
    align: 'right',
    sorter: (a: BondData, b: BondData) => a.changePercent - b.changePercent,
    defaultSortOrder: 'descend'
  },
  {
    title: '成交额(亿)',
    dataIndex: 'amount',
    key: 'amount',
    width: 150,
    sorter: (a: BondData, b: BondData) => a.amount - b.amount
  },
  {
    title: '剩余规模',
    dataIndex: 'remainSize',
    key: 'remainSize',
    align: 'right',
    width: 90,
    sorter: (a: BondData, b: BondData) => a.remainSize - b.remainSize
  },
  {
    title: '行业一级',
    dataIndex: 'industry1',
    key: 'industry1',
    width: 90
  },
  {
    title: '行业二级',
    dataIndex: 'industry2',
    key: 'industry2',
    width: 90
  },
  {
    title: '到期日期',
    dataIndex: 'maturityDate',
    key: 'maturityDate',
    width: 100
  }
]

const formatNumber = (num: number, decimals: number = 2) => {
  return num.toFixed(decimals)
}

const getChangeClass = (value: number) => {
  if (value > 0) return 'text-rise'
  if (value < 0) return 'text-fall'
  return 'text-flat'
}

const amountBarWidth = (amount: number) => {
  const ratio = amount / maxAmount.value
  return Math.min(Math.max(ratio * 100, 2), 100)
}
</script>

<template>
  <div class="bond-table-wrapper">
    <a-table
      :columns="columns"
      :data-source="data"
      :pagination="{ pageSize: 15 }"
      :scroll="{ x: 900 }"
      :row-key="(record: BondData) => record.code"
      :custom-row="(record: BondData) => ({ onClick: () => handleRowClick(record), style: { cursor: 'pointer' } })"
      size="middle"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <div class="bond-name-cell">
            <div class="bond-name-row">
              <span class="bond-name">{{ (record as BondData).name }}</span>
              <a-tag v-if="(record as BondData).isNew" color="gold" class="new-tag">新上市</a-tag>
            </div>
            <span class="bond-code">{{ (record as BondData).code }}</span>
          </div>
        </template>
        <template v-else-if="column.key === 'changePercent'">
          <span :class="getChangeClass((record as BondData).changePercent)">
            {{ (record as BondData).changePercent > 0 ? '+' : '' }}{{ formatNumber((record as BondData).changePercent) }}%
          </span>
        </template>
        <template v-else-if="column.key === 'amount'">
          <div class="amount-bar-wrapper">
            <div class="amount-bar-track">
              <div
                class="amount-bar-fill"
                :style="{ width: amountBarWidth((record as BondData).amount) + '%' }"
              ></div>
            </div>
            <span class="amount-bar-label">{{ formatNumber((record as BondData).amount, 2) }}</span>
          </div>
        </template>
        <template v-else-if="column.key === 'price'">
          <span>{{ formatNumber((record as BondData).price, 3) }}</span>
        </template>
        <template v-else-if="column.key === 'remainSize'">
          <span>{{ formatNumber((record as BondData).remainSize, 2) }}</span>
        </template>
        <template v-else>
          <span>{{ (record as any)[column.key] }}</span>
        </template>
      </template>
    </a-table>
  </div>
</template>

<style scoped>
.bond-table-wrapper {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  overflow: hidden;
}

.bond-table-wrapper :deep(.ant-table-thead > tr > th),
.bond-table-wrapper :deep(.ant-table-tbody > tr > td) {
  padding: 6px 8px;
}

.bond-table-wrapper :deep(.ant-table-tbody > tr > td) {
  font-family: Consolas, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', sans-serif;
}

.bond-name-cell {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.bond-name-row {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
}

.bond-name {
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  white-space: nowrap;
}

.bond-code {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.new-tag {
  font-size: 9px;
  padding: 0 3px;
  flex-shrink: 0;
}

.amount-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.amount-bar-track {
  flex: 1;
  height: 10px;
  background-color: #f0f3f6;
  border-radius: 5px;
  overflow: hidden;
  min-width: 40px;
}

.amount-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #54aeff, #0969da);
  border-radius: 5px;
  transition: width 0.3s ease;
}

.amount-bar-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-primary);
  white-space: nowrap;
  min-width: 36px;
  text-align: right;
}
</style>
