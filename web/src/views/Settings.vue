<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Form, FormItem, Input, Switch, InputNumber, Button, message } from 'ant-design-vue'
import NavTabs from '@/components/common/NavTabs.vue'
import BottomNav from '@/components/common/BottomNav.vue'

interface Settings {
  webhookUrl: string
  pushEnabled: boolean
  scheduledEnabled: boolean
  scheduledTime: string
  retentionDays: number
}

const formState = ref<Settings>({
  webhookUrl: '',
  pushEnabled: false,
  scheduledEnabled: false,
  scheduledTime: '09:00',
  retentionDays: 30
})

const isLoading = ref(false)

onMounted(() => {
  const savedSettings = localStorage.getItem('settings')
  if (savedSettings) {
    formState.value = JSON.parse(savedSettings)
  }
})

const handleSave = () => {
  isLoading.value = true

  setTimeout(() => {
    localStorage.setItem('settings', JSON.stringify(formState.value))
    message.success('配置保存成功')
    isLoading.value = false
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
          <h1 class="page-title">系统参数配置</h1>
        </div>

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
            <h2 class="card-title">数据管理配置</h2>
            <a-form layout="vertical">
              <a-form-item label="历史数据保留天数">
                <a-input-number
                  v-model:value="formState.retentionDays"
                  :min="1"
                  :max="365"
                  :disabled="false"
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
              :loading="isLoading"
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
          <div class="notice-card">
            <h3 class="notice-title">配置说明</h3>
            <ul class="notice-list">
              <li class="text-secondary text-sm">
                <strong>飞书 Webhook：</strong>需要在飞书群中添加自定义机器人，并复制 Webhook 地址
              </li>
              <li class="text-secondary text-sm">
                <strong>定时任务：</strong>定时任务依赖于系统运行，请确保系统保持在线状态
              </li>
              <li class="text-secondary text-sm">
                <strong>数据保留：</strong>设置较短的天数可以减少存储空间占用
              </li>
              <li class="text-secondary text-sm">
                <strong>配置保存：</strong>所有配置将保存在浏览器本地存储中
              </li>
            </ul>
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

.form-help {
  margin-top: var(--spacing-xs);
  color: var(--color-text-secondary);
}

.action-buttons {
  display: flex;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.notice-card {
  background-color: var(--color-info-bg);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-medium);
  padding: var(--spacing-lg);
}

.notice-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
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

  .action-buttons {
    flex-direction: column;
  }

  .action-buttons :deep(.ant-btn) {
    width: 100%;
  }
}
</style>
