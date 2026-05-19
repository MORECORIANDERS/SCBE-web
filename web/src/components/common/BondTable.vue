<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Table, Tag } from 'ant-design-vue'

export interface BondData {
  code: string
  name: string
  price: number
  changePercent: number
  stockPrice: number
  stockChangePercent: number
  premium: number
  remainSize: number
  doubleLow: number
  industry: string
  isNew?: boolean
}

const props = defineProps<{
  data: BondData[]
}>()

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
    width: 100,
    minWidth: 80
  },
  {
    title: '转债价格',
    dataIndex: 'price',
    key: 'price',
    width: 120
  },
  {
    title: '涨跌幅',
    dataIndex: 'changePercent',
    key: 'changePercent',
    width: 100
  },
  {
    title: '正股价格',
    dataIndex: 'stockPrice',
    key: 'stockPrice',
    width: 120
  },
  {
    title: '正股涨跌',
    dataIndex: 'stockChangePercent',
    key: 'stockChangePercent',
    width: 100
  },
  {
    title: '溢价率',
    dataIndex: 'premium',
    key: 'premium',
    width: 100
  },
  {
    title: '剩余规模',
    dataIndex: 'remainSize',
    key: 'remainSize',
    width: 120
  },
  {
    title: '双低数值',
    dataIndex: 'doubleLow',
    key: 'doubleLow',
    width: 120
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
</script>

<template>
  <div class="bond-table-wrapper">
    <a-table
      :columns="columns"
      :data-source="data"
      :pagination="{ pageSize: 10 }"
      :scroll="{ x: 1000 }"
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
        <template v-else-if="column.key === 'stockChangePercent'">
          <span :class="getChangeClass((record as BondData).stockChangePercent)">
            {{ (record as BondData).stockChangePercent > 0 ? '+' : '' }}{{ formatNumber((record as BondData).stockChangePercent) }}%
          </span>
        </template>
        <template v-else-if="column.key === 'premium'">
          <span>{{ formatNumber((record as BondData).premium) }}%</span>
        </template>
        <template v-else-if="column.key === 'remainSize'">
          <span>{{ formatNumber((record as BondData).remainSize, 2) }}亿</span>
        </template>
        <template v-else-if="column.key === 'doubleLow'">
          <span>{{ formatNumber((record as BondData).doubleLow) }}</span>
        </template>
        <template v-else>
          <span>{{ formatNumber((record as any)[column.key]) }}</span>
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
</style>
