<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Tabs } from 'ant-design-vue'

const router = useRouter()
const route = useRoute()

const activeKey = computed(() => {
  const routeMap: Record<string, string> = {
    '/': 'home',
    '/heatmap': 'heatmap',
    '/scatter': 'scatter',
    '/control': 'control',
    '/settings': 'settings'
  }
  return routeMap[route.path] || 'home'
})

const handleTabChange = (key: string) => {
  const pathMap: Record<string, string> = {
    home: '/',
    heatmap: '/heatmap',
    scatter: '/scatter',
    control: '/control',
    settings: '/settings'
  }
  router.push(pathMap[key] || '/')
}
</script>

<template>
  <div class="nav-tabs">
    <div class="nav-tabs-content">
      <div class="nav-brand">
        <span class="brand-text">可转债系统</span>
      </div>

      <a-tabs
        :active-key="activeKey"
        @change="handleTabChange"
      >
        <a-tab-pane key="home">
          <template #tab>
            <span class="tab-label">首页</span>
          </template>
        </a-tab-pane>

        <a-tab-pane key="heatmap">
          <template #tab>
            <span class="tab-label">行业热力图</span>
          </template>
        </a-tab-pane>

        <a-tab-pane key="scatter">
          <template #tab>
            <span class="tab-label">双低分析</span>
          </template>
        </a-tab-pane>

        <a-tab-pane key="control">
          <template #tab>
            <span class="tab-label">系统控制</span>
          </template>
        </a-tab-pane>

        <a-tab-pane key="settings">
          <template #tab>
            <span class="tab-label">参数配置</span>
          </template>
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<style scoped>
.nav-tabs {
  background-color: var(--color-bg-primary);
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: var(--z-index-sticky);
}

.nav-tabs-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 var(--spacing-xl);
  display: flex;
  align-items: center;
  gap: var(--spacing-xxl);
}

.nav-brand {
  padding: var(--spacing-lg) 0;
  flex-shrink: 0;
}

.brand-text {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

:deep(.ant-tabs) {
  flex: 1;
}

:deep(.ant-tabs-nav) {
  margin-bottom: 0;
}

.tab-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}

@media (max-width: 767px) {
  .nav-tabs {
    display: none;
  }
}
</style>
