<script setup lang="ts">
import { ref } from 'vue'
import { Button, Modal, message } from 'ant-design-vue'
import {
  BarChartOutlined,
  ClockCircleOutlined,
  BellOutlined
} from '@ant-design/icons-vue'
import NavTabs from '@/components/common/NavTabs.vue'
import BottomNav from '@/components/common/BottomNav.vue'

const lastRunTime = ref<string>('2024-01-21 10:30:45')
const runStatus = ref<'idle' | 'running'>('idle')
const isModalVisible = ref(false)

const handleCollect = () => {
  isModalVisible.value = true
}

const confirmCollect = () => {
  isModalVisible.value = false
  runStatus.value = 'running'

  message.loading({ content: '正在采集数据...', key: 'collect' })

  setTimeout(() => {
    runStatus.value = 'idle'
    lastRunTime.value = new Date().toLocaleString('zh-CN')
    message.success({ content: '数据采集完成', key: 'collect' })
  }, 2000)
}

const cancelModal = () => {
  isModalVisible.value = false
}

const statusMap = {
  idle: { text: '空闲', class: 'status-idle' },
  running: { text: '运行中', class: 'status-running' }
}
</script>

<template>
  <div class="page-layout">
    <NavTabs />

    <div class="main-content">
      <div class="page-container">
        <div class="page-header">
          <h1 class="page-title">系统控制面板</h1>
        </div>

        <section class="section">
          <div class="control-card">
            <h2 class="card-title">数据采集管理</h2>
            <div class="control-content">
              <div class="control-info">
                <div class="info-row">
                  <span class="info-label">最近执行时间：</span>
                  <span class="info-value font-medium">{{ lastRunTime }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">运行状态：</span>
                  <span class="status-badge" :class="statusMap[runStatus].class">
                    {{ statusMap[runStatus].text }}
                  </span>
                </div>
              </div>

              <div class="control-action">
                <a-button
                  type="primary"
                  size="large"
                  @click="handleCollect"
                  :loading="runStatus === 'running'"
                >
                  {{ runStatus === 'running' ? '采集中...' : '更新数据' }}
                </a-button>
              </div>
            </div>
          </div>
        </section>

        <section class="section">
          <div class="info-card">
            <h3 class="info-title">功能说明</h3>
            <ul class="feature-list">
              <li class="feature-item">
                <BarChartOutlined class="feature-icon" />
                <div class="feature-content">
                  <h4 class="feature-name">手动采集</h4>
                  <p class="feature-desc text-secondary text-sm">
                    立即执行一次数据采集任务，获取最新的可转债行情数据
                  </p>
                </div>
              </li>
              <li class="feature-item">
                <ClockCircleOutlined class="feature-icon" />
                <div class="feature-content">
                  <h4 class="feature-name">定时采集</h4>
                  <p class="feature-desc text-secondary text-sm">
                    按照配置的时间自动执行数据采集任务（需在参数配置中开启）
                  </p>
                </div>
              </li>
              <li class="feature-item">
                <BellOutlined class="feature-icon" />
                <div class="feature-content">
                  <h4 class="feature-name">飞书通知</h4>
                  <p class="feature-desc text-secondary text-sm">
                    采集完成后自动推送通知到飞书群（需在参数配置中设置 Webhook）
                  </p>
                </div>
              </li>
            </ul>
          </div>
        </section>

        <section class="section">
          <div class="notice-card">
            <h3 class="notice-title">注意事项</h3>
            <ul class="notice-list">
              <li class="text-secondary text-sm">手动采集可能需要几秒钟时间，请耐心等待</li>
              <li class="text-secondary text-sm">采集过程中请勿关闭页面</li>
              <li class="text-secondary text-sm">建议在非交易时间段进行数据采集</li>
              <li class="text-secondary text-sm">如需设置定时任务，请前往参数配置页面</li>
            </ul>
          </div>
        </section>
      </div>
    </div>

    <a-modal
      v-model:open="isModalVisible"
      title="确认采集"
      @ok="confirmCollect"
      @cancel="cancelModal"
      :ok-text="'确认采集'"
      :cancel-text="'取消'"
    >
      <p>确定要立即执行数据采集任务吗？</p>
      <p class="text-secondary text-sm" style="margin-top: 8px;">
        采集过程可能需要几秒钟时间
      </p>
    </a-modal>

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
  max-width: 800px;
  margin: 0 auto;
  padding: var(--spacing-xl);
}

.page-header {
  margin-bottom: var(--spacing-xl);
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.section {
  margin-bottom: var(--spacing-xl);
}

.control-card {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  padding: var(--spacing-xl);
}

.card-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-xl);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--color-border-light);
}

.control-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--spacing-xl);
  flex-wrap: wrap;
}

.control-info {
  flex: 1;
  min-width: 200px;
}

.info-row {
  margin-bottom: var(--spacing-md);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.info-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.info-value {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-small);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
}

.status-idle {
  background-color: var(--color-bg-secondary);
  color: var(--color-text-secondary);
}

.status-running {
  background-color: var(--color-rise-bg);
  color: var(--color-rise);
}

.control-action {
  flex-shrink: 0;
}

.info-card {
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  padding: var(--spacing-xl);
}

.info-title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-lg);
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.feature-item {
  display: flex;
  gap: var(--spacing-md);
  align-items: flex-start;
}

.feature-icon {
  font-size: 20px;
  line-height: 1;
  flex-shrink: 0;
  color: var(--color-text-secondary);
}

.feature-content {
  flex: 1;
}

.feature-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-xs);
}

.notice-card {
  background-color: var(--color-warning-bg);
  border: 1px solid #d4a72c;
  border-radius: var(--radius-medium);
  padding: var(--spacing-lg);
}

.notice-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-warning);
  margin-bottom: var(--spacing-md);
}

.notice-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

@media (max-width: 767px) {
  .page-container {
    padding: var(--spacing-md);
  }

  .page-title {
    font-size: var(--font-size-xl);
  }

  .control-content {
    flex-direction: column;
  }

  .control-action {
    width: 100%;
  }

  .control-action :deep(.ant-btn) {
    width: 100%;
  }
}
</style>
