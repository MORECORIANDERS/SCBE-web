<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  HomeOutlined,
  AppstoreOutlined,
  LineChartOutlined,
  ControlOutlined
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()

const tabs = [
  { key: 'home', label: '首页', path: '/', icon: HomeOutlined },
  { key: 'heatmap', label: '行业', path: '/heatmap', icon: AppstoreOutlined },
  { key: 'scatter', label: '策略', path: '/scatter', icon: LineChartOutlined },
  { key: 'control', label: '配置', path: '/control', icon: ControlOutlined }
]

const activeKey = computed(() => {
  const current = tabs.find(tab => tab.path === route.path)
  return current?.key || 'home'
})

const handleTabClick = (path: string) => {
  router.push(path)
}
</script>

<template>
  <div class="bottom-nav">
    <div
      v-for="tab in tabs"
      :key="tab.key"
      class="nav-item"
      :class="{ active: activeKey === tab.key }"
      @click="handleTabClick(tab.path)"
    >
      <component :is="tab.icon" class="nav-icon" />
      <span class="nav-label">{{ tab.label }}</span>
    </div>
  </div>
</template>

<style scoped>
.bottom-nav {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: var(--color-bg-primary);
  border-top: 1px solid var(--color-border);
  z-index: var(--z-index-fixed);
  padding: var(--spacing-xs) 0;
  padding-bottom: calc(var(--spacing-xs) + env(safe-area-inset-bottom, 0));
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: var(--spacing-sm);
  cursor: pointer;
  transition: color var(--transition-fast);
  color: var(--color-text-secondary);
}

.nav-item.active {
  color: var(--color-primary);
}

.nav-item:hover {
  color: var(--color-primary);
}

.nav-icon {
  font-size: 20px;
  line-height: 1;
}

.nav-label {
  font-size: 10px;
  font-weight: var(--font-weight-medium);
}

@media (max-width: 767px) {
  .bottom-nav {
    display: flex;
  }
}
</style>
