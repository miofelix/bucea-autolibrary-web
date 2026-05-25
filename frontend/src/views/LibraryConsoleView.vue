<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <span class="eyebrow">Library Console</span>
        <h2>账号会话</h2>
      </div>
      <div class="row-actions">
        <AccountPicker v-model="selectedUserId" />
        <button class="button muted" type="button" :disabled="busy" @click="refreshStatus">
          <RefreshCw :size="16" />
          刷新状态
        </button>
      </div>
    </div>

    <p class="notice info">
      选择账号后会自动建立登录会话；验证码由后端 ddddocr 自动识别并提交，识别失败会自动用新验证码重试最多 {{ retries }} 次。
    </p>

    <div v-if="status" class="settings-list">
      <div class="settings-row">
        <span>登录状态</span>
        <span class="tag" :class="status.logged_in ? 'enabled' : 'disabled'">
          {{ status.logged_in ? '已登录' : '未登录' }}
        </span>
      </div>
      <div class="settings-row">
        <span>sysUsername</span>
        <code>{{ status.sys_username ?? '-' }}</code>
      </div>
      <div class="settings-row">
        <span>CSRF</span>
        <span class="tag" :class="status.has_csrf ? 'enabled' : 'disabled'">
          {{ status.has_csrf ? '已就绪' : '缺失' }}
        </span>
      </div>
    </div>

    <div class="form-actions" style="margin-top: 16px;">
      <button
        class="button primary"
        type="button"
        :disabled="!selectedUserId || busy"
        @click="submitLogin"
      >
        <LogIn :size="16" />
        {{ busy ? '登录中…' : '自动登录' }}
      </button>
      <button
        class="button"
        type="button"
        :disabled="!status?.logged_in || busy"
        @click="logout"
      >
        <LogOut :size="16" />
        退出登录
      </button>
    </div>

    <p v-if="loginMessage" :class="['notice', loginSuccess ? 'success' : 'warning']">
      {{ loginMessage }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { LogIn, LogOut, RefreshCw } from '@lucide/vue'

import {
  fetchSession,
  loginLibrary,
  logoutLibrary,
  type SessionStatus,
} from '@/api/library'
import { fetchRuntimeSettings } from '@/api/settings'
import AccountPicker from '@/components/AccountPicker.vue'

const selectedUserId = ref<number | null>(null)
const status = ref<SessionStatus | null>(null)
const loginMessage = ref('')
const loginSuccess = ref(false)
const busy = ref(false)
const retries = ref(3)

onMounted(async () => {
  try {
    const runtime = await fetchRuntimeSettings()
    if (runtime.enable_captcha_ocr === false) {
      loginMessage.value = '后端未开启 ddddocr，自动登录不可用。请在 .env 设置 AUTO_LIBRARY_ENABLE_CAPTCHA_OCR=true。'
      loginSuccess.value = false
    }
  } catch {
    // Settings endpoint failure isn't fatal here.
  }
})

watch(selectedUserId, () => {
  loginMessage.value = ''
  void refreshStatus()
})

async function refreshStatus(): Promise<void> {
  if (!selectedUserId.value) {
    status.value = null
    return
  }
  try {
    status.value = await fetchSession(selectedUserId.value)
  } catch (err) {
    status.value = null
    loginSuccess.value = false
    loginMessage.value = err instanceof Error ? err.message : '自动登录失败'
  }
}

async function submitLogin(): Promise<void> {
  if (!selectedUserId.value) return
  busy.value = true
  loginMessage.value = ''
  try {
    const result = await loginLibrary(selectedUserId.value)
    loginSuccess.value = result.success
    loginMessage.value = result.message || (result.success ? '登录成功' : '登录失败')
    await refreshStatus()
  } catch (err) {
    loginSuccess.value = false
    loginMessage.value = err instanceof Error ? err.message : '登录请求失败'
  } finally {
    busy.value = false
  }
}

async function logout(): Promise<void> {
  if (!selectedUserId.value) return
  busy.value = true
  try {
    await logoutLibrary(selectedUserId.value)
    loginMessage.value = ''
    await refreshStatus()
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.notice.success {
  color: #0f684d;
  background: #e6f6ef;
}

.notice.info {
  color: #1f4a90;
  background: #eaf1ff;
  margin: 0 0 16px;
  padding: 10px 12px;
  border-radius: 8px;
  font-weight: 600;
}
</style>
