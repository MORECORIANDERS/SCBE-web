<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  BarChartOutlined,
  ClockCircleOutlined,
  BellOutlined
} from '@ant-design/icons-vue'
import NavTabs from '@/components/common/NavTabs.vue'
import BottomNav from '@/components/common/BottomNav.vue'
import {
  refreshData,
  triggerDailyOversold,
  triggerWeeklyOversold,
  triggerVolumeFilter
} from '@/api'

interface Settings {
  webhookUrl: string
  pushEnabled: boolean
  scheduledEnabled: boolean
  scheduledTime: string
  retentionDays: number
}

const taskStates = reactive({
  snapshot: { loading: false, lastRun: '2024-01-21 10:30:45' },
  daily: { loading: false, lastRun: '' },
  weekly: { loading: false, lastRun: '' },
  volume: { loading: false, lastRun: '' }
})

const isModalVisible = ref(false)
const pendingAction = ref<() => Promise<void>>()
const isSaving = ref(false)

const formState = ref<Settings>({
  webhookUrl: '',
  pushEnabled: false,
  scheduledEnabled: false,
  scheduledTime: '09:00',
  retentionDays: 30
})

onMounted(() => {
  const savedSettings = localStorage.getItem('settings')
  if (savedSettings) {
    formState.value = JSON.parse(savedSettings)
  }
})

const runTask = async (key: keyof typeof taskStates, label: string, fn: () => Promise<any>) => {
  taskStates[key].loading = true
  const msgKey = `task-${key}`
  message.loading({ content: `${label}执行中...`, key: msgKey })
  try {
    await fn()
    taskStates[key].lastRun = new Date().toLocaleString('zh-CN')
    message.success({ content: `${label}完成`, key: msgKey })
  } catch (e: any) {
    message.error({ content: `${label}失败: ${e.message}`, key: msgKey })
  } finally {
    taskStates[key].loading = false
  }
}

const handleCollect = () => {
  pendingAction.value = async () => {
    await runTask('snapshot', '数据采集', refreshData)
  }
  isModalVisible.value = true
}

const confirmCollect = async () => {
  isModalVisible.value = false
  if (pendingAction.value) {
    await pendingAction.value()
  }
}

const cancelModal = () => {
  isModalVisible.value = false
  pendingAction.value = undefined
}

const handleTriggerDaily = () => runTask('daily', '日线超卖采集', triggerDailyOversold)
const handleTriggerWeekly = () => runTask('weekly', '周线超卖采集', triggerWeeklyOversold)
const handleTriggerVolume = () => runTask('volume', '成交额2倍采集', triggerVolumeFilter)

const handleSave = () => {
  if (formState.value.scheduledTime && !/^\d{2}:\d{2}$/.test(formState.value.scheduledTime)) {
    message.warning('定时采集时间格式错误，请使用 HH:mm 格式')
    return
  }
  if (formState.value.webhookUrl && !formState.value.webhookUrl.startsWith('https://')) {
    message.warning('Webhook 地址格式错误，请使用 https:// 开头的地址')
    return
  }
  isSaving.value = true

  setTimeout(() => {
    localStorage.setItem('settings', JSON.stringify(formState.value))
    message.success('配置保存成功')
    isSaving.value = false
  }, 500)
}

const handleReset = () => {
  formState.value = {
    webhookUrl: '',
    pushEnabled: false,
    scheduledEnabled: false,
    scheduledTime: '09:00',
    retentionDays: 30
  }
  message.info('已重置为默认值')
}
</script>

<template>
  <div class="page-layout">
    <NavTabs />

    <div class="main-content">
      <div class="page-container">
        <div class="page-header">
          <h1 class="page-title">系统配置</h1>
        </div>

        <section class="section">
          <div class="config-card">
            <h2 class="card-title">数据采集</h2>
            <div class="task-grid">
              <div class="task-item">
                <div class="task-header">
                  <span class="task-label">行情数据</span>
                  <span class="task-time" v-if="taskStates.snapshot.lastRun">
                    {{ taskStates.snapshot.lastRun }}
                  </span>
                </div>
                <div class="task-desc">从 EastMoney 采集可转债行情快照</div>
                <a-button
                  type="primary"
                  :loading="taskStates.snapshot.loading"
                  @click="handleCollect"
                >
                  {{ taskStates.snapshot.loading ? '采集中...' : '更新数据' }}
                </a-button>
              </div>

              <div class="task-item">
                <div class="task-header">
                  <span class="task-label">日线超卖</span>
                  <span class="task-time" v-if="taskStates.daily.lastRun">
                    {{ taskStates.daily.lastRun }}
                  </span>
                </div>
                <div class="task-desc">计算日线 CCI/WR，标记超卖转债</div>
                <a-button
                  type="primary"
                  ghost
                  :loading="taskStates.daily.loading"
                  @click="handleTriggerDaily"
                >
                  {{ taskStates.daily.loading ? '采集中...' : '开始采集' }}
                </a-button>
              </div>

              <div class="task-item">
                <div class="task-header">
                  <span class="task-label">周线超卖</span>
                  <span class="task-time" v-if="taskStates.weekly.lastRun">
                    {{ taskStates.weekly.lastRun }}
                  </span>
                </div>
                <div class="task-desc">计算周线 CCI/WR，标记超卖转债</div>
                <a-button
                  type="primary"
                  ghost
                  :loading="taskStates.weekly.loading"
                  @click="handleTriggerWeekly"
                >
                  {{ taskStates.weekly.loading ? '采集中...' : '开始采集' }}
                </a-button>
              </div>

              <div class="task-item">
                <div class="task-header">
                  <span class="task-label">成交额2倍</span>
                  <span class="task-time" v-if="taskStates.volume.lastRun">
                    {{ taskStates.volume.lastRun }}
                  </span>
                </div>
                <div class="task-desc">筛选当日成交额超过近5日均值2倍的转债</div>
                <a-button
                  type="primary"
                  ghost
                  :loading="taskStates.volume.loading"
                  @click="handleTriggerVolume"
                >
                  {{ taskStates.volume.loading ? '采集中...' : '开始采集' }}
                </a-button>
              </div>
            </div>
          </div>
        </section>

        <section class="section">
          <div class="config-card">
            <h2 class="card-title">飞书推送配置</h2>
            <a-form layout="vertical">
              <a-form-item label="飞书机器人 Webhook 地址">
                <a-input
                  v-model:value="formState.webhookUrl"
                  placeholder="请输入飞书群机器人的 Webhook 地址"
                />
                <p class="form-help text-secondary text-xs">
                  格式：https://open.feishu.cn/open-apis/bot/v2/hook/xxx
                </p>
              </a-form-item>

              <a-form-item label="启用飞书推送">
                <a-switch v-model:checked="formState.pushEnabled" />
                <p class="form-help text-secondary text-xs">
                  开启后，数据采集完成将自动推送通知到飞书群
                </p>
              </a-form-item>
            </a-form>
          </div>
        </section>

        <section class="section">
          <div class="config-card">
            <h2 class="card-title">定时任务配置</h2>
            <a-form layout="vertical">
              <a-form-item label="启用定时采集">
                <a-switch v-model:checked="formState.scheduledEnabled" />
                <p class="form-help text-secondary text-xs">
                  开启后，将按照设定的时间自动执行数据采集任务
                </p>
              </a-form-item>

              <a-form-item label="定时采集时间">
                <a-input
                  v-model:value="formState.scheduledTime"
                  placeholder="请输入时间"
                  :disabled="!formState.scheduledEnabled"
                />
                <p class="form-help text-secondary text-xs">
                  格式：HH:mm，例如 09:00 表示每天上午9点执行
                </p>
              </a-form-item>
            </a-form>
          </div>
        </section>

        <section class="section">
          <div class="config-card">
            <h2 class="card-title">数据管理</h2>
            <a-form layout="vertical">
              <a-form-item label="历史数据保留天数">
                <a-input-number
                  v-model:value="formState.retentionDays"
                  :min="1"
                  :max="365"
                />
                <p class="form-help text-secondary text-xs">
                  超过此天数的历史数据将被自动清理，建议设置为 7-90 天
                </p>
              </a-form-item>
            </a-form>
          </div>
        </section>

        <section class="section">
          <div class="action-buttons">
            <a-button
              type="primary"
              size="large"
              @click="handleSave"
              :loading="isSaving"
            >
              保存配置
            </a-button>
            <a-button
              size="large"
              @click="handleReset"
            >
              重置默认值
            </a-button>
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
                    按照配置的时间自动执行数据采集任务（需在下方配置中开启）
                  </p>
                </div>
              </li>
              <li class="feature-item">
                <BellOutlined class="feature-icon" />
                <div class="feature-content">
                  <h4 class="feature-name">飞书通知</h4>
                  <p class="feature-desc text-secondary text-sm">
                    采集完成后自动推送通知到飞书群（需在下方配置中设置 Webhook）
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
              <li class="text-secondary text-sm">所有配置将保存在浏览器本地存储中</li>
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

.config-card {
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

.task-grid {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.task-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-medium);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-label {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.task-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.task-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.4;
}

.form-help {
  margin-top: var(--spacing-xs);
  color: var(--color-text-secondary);
}

.action-buttons {
  display: flex;
  gap: var(--spacing-md);
  flex-wrap: wrap;
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

  .task-item :deep(.ant-btn) {
    width: 100%;
  }

  .action-buttons {
    flex-direction: column;
  }

  .action-buttons :deep(.ant-btn) {
    width: 100%;
  }
}
</style>
