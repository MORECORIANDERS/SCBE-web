<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'

const router = useRouter()
const password = ref('')
const loading = ref(false)

const handleLogin = async () => {
  if (!password.value) {
    message.warning('请输入密码')
    return
  }

  loading.value = true

  setTimeout(() => {
    localStorage.setItem('isLoggedIn', 'true')
    message.success('登录成功')
    router.push('/')
    loading.value = false
  }, 500)
}
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1 class="login-title">可转债投资系统</h1>
        <p class="login-subtitle">Bond Investment System</p>
      </div>

      <form @submit.prevent="handleLogin">
        <div class="form-item">
          <label class="form-label">密码</label>
          <input
            v-model="password"
            type="password"
            class="form-input"
            placeholder="请输入密码"
          />
        </div>

        <div class="form-item">
          <button
            type="submit"
            class="submit-btn"
            :disabled="loading"
          >
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </div>
      </form>

      <div class="login-footer">
        <p class="text-secondary text-xs">
          演示密码：任意密码均可登录
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--color-bg-secondary);
  padding: var(--spacing-lg);
}

.login-card {
  width: 100%;
  max-width: 400px;
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-large);
  padding: var(--spacing-xxl);
}

.login-header {
  text-align: center;
  margin-bottom: var(--spacing-xl);
}

.login-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-xs);
}

.login-subtitle {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.form-item {
  margin-bottom: var(--spacing-lg);
}

.form-label {
  display: block;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-sm);
}

.form-input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-base);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  outline: none;
  transition: border-color var(--transition-fast);
}

.form-input:focus {
  border-color: var(--color-primary);
}

.submit-btn {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: #ffffff;
  background-color: var(--color-primary);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-medium);
  cursor: pointer;
  transition: background-color var(--transition-fast);
}

.submit-btn:hover:not(:disabled) {
  background-color: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-footer {
  margin-top: var(--spacing-lg);
  text-align: center;
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--color-border-light);
}

@media (max-width: 767px) {
  .login-card {
    padding: var(--spacing-xl);
  }

  .login-title {
    font-size: var(--font-size-xl);
  }
}
</style>
