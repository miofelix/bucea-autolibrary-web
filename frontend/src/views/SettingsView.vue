<template>
  <section class="content-grid two-columns align-start">
    <div class="panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Runtime</span>
          <h2>系统设置</h2>
        </div>
        <button class="button muted" type="button" :disabled="loading" @click="load">
          <RefreshCw :size="16" />
          刷新
        </button>
      </div>

      <p v-if="error" class="notice danger">{{ error }}</p>

      <div v-if="runtime" class="settings-list">
        <div class="settings-row">
          <span>环境</span>
          <code>{{ runtime.app_env }}</code>
        </div>
        <div class="settings-row">
          <span>后端 API</span>
          <code>{{ apiBaseUrl || 'same-origin / Vite proxy' }}</code>
        </div>
        <div class="settings-row">
          <span>图书馆 base URL</span>
          <code>{{ runtime.library_base_url }}</code>
        </div>
        <div class="settings-row">
          <span>登录入口</span>
          <code>{{ runtime.library_login_url }}</code>
        </div>
        <div class="settings-row">
          <span>ALLOW_LIVE_TEST</span>
          <span class="tag" :class="runtime.allow_live_test ? 'enabled' : 'disabled'">
            {{ runtime.allow_live_test ? '已开启' : '已关闭' }}
          </span>
        </div>
        <div class="settings-row">
          <span>ALLOW_MUTATION_TEST</span>
          <span
            class="tag"
            :class="runtime.allow_mutation_test ? 'needs_user_confirmation' : 'disabled'"
          >
            {{ runtime.allow_mutation_test ? '已开启（写操作放行）' : '已关闭' }}
          </span>
        </div>
        <div class="settings-row">
          <span>验证码 OCR</span>
          <span class="tag" :class="runtime.enable_captcha_ocr ? 'enabled' : 'disabled'">
            {{ runtime.enable_captcha_ocr ? 'ddddocr 已开启' : '已关闭（自动登录不可用）' }}
          </span>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Preferences</span>
          <h2>偏好</h2>
        </div>
      </div>
      <div class="settings-list">
        <div class="settings-row">
          <span>默认账号</span>
          <div class="row-actions">
            <select
              :value="users.defaultUserId !== null ? String(users.defaultUserId) : ''"
              @change="onDefaultChange"
            >
              <option value="">— 不设默认 —</option>
              <option v-for="u in users.items" :key="u.id" :value="String(u.id)">
                {{ u.username }}{{ u.display_name ? ` · ${u.display_name}` : '' }}
              </option>
            </select>
            <button
              class="button muted"
              type="button"
              :disabled="users.defaultUserId === null"
              @click="users.setDefaultUser(null)"
            >
              清除
            </button>
          </div>
        </div>
        <p class="hint">
          选中后，所有需要选账号的页面 (仪表盘、座位查询、我的预约、常用座位、违约记录、账号会话)
          会自动预选该账号；页面内仍可临时改用别的账号而不影响默认。
        </p>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Security</span>
          <h2>安全状态</h2>
        </div>
      </div>
      <div class="rule-list">
        <div v-for="item in securityItems" :key="item" class="rule-item">
          <ShieldCheck :size="16" />
          <span>{{ item }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RefreshCw, ShieldCheck } from '@lucide/vue'

import { fetchRuntimeSettings, type RuntimeSettings } from '@/api/settings'
import { useUsersStore } from '@/stores/users'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
const securityItems = [
  '前端不访问图书馆系统',
  '图书馆账号密码由后端 Fernet 加密保存',
  '敏感字段不进入日志输出',
  '写操作受 ALLOW_MUTATION_TEST 门禁',
]

const users = useUsersStore()
const runtime = ref<RuntimeSettings | null>(null)
const loading = ref(false)
const error = ref('')

onMounted(async () => {
  await Promise.all([load(), users.fetchUsers()])
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    runtime.value = await fetchRuntimeSettings()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '读取运行时配置失败'
  } finally {
    loading.value = false
  }
}

function onDefaultChange(event: Event): void {
  const target = event.target as HTMLSelectElement
  const raw = target.value
  users.setDefaultUser(raw ? Number(raw) : null)
}
</script>

<style scoped>
.hint {
  margin: 6px 2px 0;
  color: var(--text-muted);
  font-size: 0.82rem;
}
</style>
