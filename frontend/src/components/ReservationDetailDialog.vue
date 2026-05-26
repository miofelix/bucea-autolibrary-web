<template>
  <div class="dialog-backdrop" @click.self="$emit('close')">
    <div class="dialog-card">
      <header>
        <h3>预约详情 #{{ reservationId }}</h3>
        <button class="icon-button" type="button" @click="$emit('close')">
          <X :size="16" />
        </button>
      </header>

      <p v-if="loading" class="hint">加载中…</p>
      <p v-else-if="error" class="notice danger">{{ error }}</p>

      <div v-else-if="detail" class="settings-list">
        <div class="settings-row"><span>凭证号</span><code>{{ detail.credential_no ?? '-' }}</code></div>
        <div class="settings-row"><span>日期</span><code>{{ detail.date ?? '-' }}</code></div>
        <div class="settings-row">
          <span>时间</span>
          <code>{{ detail.start_label && detail.end_label ? `${detail.start_label} - ${detail.end_label}` : '-' }}</code>
        </div>
        <div class="settings-row"><span>位置</span><code>{{ detail.room_name ?? '-' }}</code></div>
        <div class="settings-row"><span>座位</span><code>{{ detail.seat_name ?? '-' }}</code></div>
        <div class="settings-row">
          <span>状态</span>
          <span class="tag">{{ detail.status ?? '-' }}</span>
        </div>

        <details class="raw-block">
          <summary>原始文本</summary>
          <pre>{{ detail.raw_text }}</pre>
        </details>
      </div>

      <div class="form-actions">
        <button class="button muted" type="button" @click="$emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { X } from '@lucide/vue'

import { fetchReservationDetail, type ReservationDetail } from '@/api/library'

interface Props {
  userId: number
  reservationId: string
}

const props = defineProps<Props>()

defineEmits<{ close: [] }>()

const detail = ref<ReservationDetail | null>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    detail.value = await fetchReservationDetail(props.userId, props.reservationId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载详情失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgb(15 23 42 / 50%);
  z-index: 70;
}

.dialog-card {
  width: min(100%, 560px);
  padding: 18px;
  border-radius: 14px;
  background: var(--panel);
  box-shadow: var(--shadow);
}

@media (max-width: 640px) {
  .dialog-backdrop {
    align-items: end;
    padding: 0;
  }

  .dialog-card {
    width: 100%;
    max-height: 92vh;
    padding: 16px 14px calc(16px + env(safe-area-inset-bottom, 0px));
    border-radius: 16px 16px 0 0;
    overflow-y: auto;
  }
}

.dialog-card header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.dialog-card h3 {
  margin: 0;
}

.raw-block {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--panel-muted);
}

.raw-block pre {
  margin: 8px 0 0;
  max-height: 220px;
  overflow: auto;
  font-size: 0.78rem;
  color: var(--text-muted);
  white-space: pre-wrap;
  word-break: break-all;
}

.hint {
  color: var(--text-muted);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
