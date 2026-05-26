<template>
  <div class="dialog-backdrop" @click.self="$emit('close')">
    <div class="dialog-card">
      <header>
        <h3>预约座位 {{ seat.name }}</h3>
        <button class="icon-button" type="button" @click="$emit('close')">
          <X :size="16" />
        </button>
      </header>

      <section class="form-grid">
        <div class="settings-row">
          <span>座位</span>
          <code>{{ seat.name }} · {{ seat.room_name ?? '-' }}</code>
        </div>
        <div class="settings-row">
          <span>日期</span>
          <code>{{ date || '今天' }}</code>
        </div>

        <p v-if="usingHint" class="notice info">{{ usingHint }}</p>

        <label class="field">
          <span>开始时间</span>
          <select v-model="startValue" :disabled="loadingStart || startTimes.length === 0">
            <option value="">{{ startPlaceholder }}</option>
            <option v-for="opt in startTimes" :key="opt.raw_value" :value="opt.raw_value">
              {{ opt.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>结束时间</span>
          <select v-model="endValue" :disabled="!startValue || loadingEnd">
            <option value="">— 请选择 —</option>
            <option v-for="opt in endTimes" :key="opt.raw_value" :value="opt.raw_value">
              {{ opt.label }}
            </option>
          </select>
        </label>

        <p class="notice warning">
          点击提交后会真正调用 <code>POST /selfRes</code>。
          若后端未开启 <code>ALLOW_MUTATION_TEST</code>，会返回 blocked。
        </p>

        <p v-if="message" :class="['notice', success ? 'success' : 'danger']">{{ message }}</p>

        <div class="form-actions">
          <button class="button muted" type="button" @click="$emit('close')">
            取消
          </button>
          <button
            class="button primary"
            type="button"
            :disabled="!canSubmit"
            @click="submit"
          >
            <Send :size="16" />
            提交预约
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Send, X } from '@lucide/vue'

import {
  fetchEndTimes,
  fetchStartTimes,
  submitReservation,
  type SeatItem,
  type TimeOption,
} from '@/api/library'

const props = defineProps<{
  userId: number
  seat: SeatItem
  date: string
}>()

const emit = defineEmits<{
  close: []
  reserved: [message: string]
}>()

const startTimes = ref<TimeOption[]>([])
const endTimes = ref<TimeOption[]>([])
const startValue = ref('')
const endValue = ref('')
const loadingStart = ref(false)
const loadingEnd = ref(false)
const busy = ref(false)
const message = ref('')
const success = ref(false)

const canSubmit = computed(
  () => !!startValue.value && !!endValue.value && !busy.value,
)

const startPlaceholder = computed(() => {
  if (loadingStart.value) return '— 加载中… —'
  if (startTimes.value.length === 0) return '— 暂无可预约时段 —'
  return '— 请选择 —'
})

const usingHint = computed(() => {
  if (loadingStart.value) return ''
  const isFree = props.seat.status === 'free' || !props.seat.status
  if (isFree) return ''
  if (startTimes.value.length === 0) {
    return `座位「${props.seat.name}」当前状态为 ${props.seat.status}，今日已无可预约时段。`
  }
  const earliest = startTimes.value[0]?.label ?? ''
  return `座位「${props.seat.name}」当前正在使用，最早可从 ${earliest} 开始预约。`
})

onMounted(async () => {
  await loadStartTimes()
})

watch(startValue, async (value) => {
  endTimes.value = []
  endValue.value = ''
  if (!value) return
  await loadEndTimes(value)
})

async function loadStartTimes() {
  loadingStart.value = true
  try {
    const result = await fetchStartTimes(props.userId, props.seat.seat_id, props.date || '')
    startTimes.value = result.options
  } finally {
    loadingStart.value = false
  }
}

async function loadEndTimes(start: string) {
  loadingEnd.value = true
  try {
    endTimes.value = await fetchEndTimes(props.userId, props.seat.seat_id, start, props.date || '')
  } finally {
    loadingEnd.value = false
  }
}

async function submit() {
  if (!startValue.value || !endValue.value) return
  busy.value = true
  message.value = ''
  try {
    const result = await submitReservation(props.userId, {
      seat_id: props.seat.seat_id,
      start: startValue.value,
      end: endValue.value,
      date: props.date || '',
    })
    success.value = result.success
    message.value = result.message || (result.success ? '预约成功' : '预约失败')
    if (result.success) {
      emit('reserved', message.value)
    }
  } catch (err) {
    success.value = false
    message.value = err instanceof Error ? err.message : '提交失败'
  } finally {
    busy.value = false
  }
}
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
  width: min(100%, 520px);
  padding: 18px;
  border-radius: 14px;
  background: var(--panel);
  box-shadow: var(--shadow);
}

.dialog-card header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.dialog-card h3 {
  margin: 0;
  font-size: 1.05rem;
}

.notice.success {
  color: #0f684d;
  background: #e6f6ef;
}

.notice.info {
  color: #1f4a90;
  background: #eaf1ff;
  font-weight: 600;
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
    animation: slideUp 0.22s ease-out;
  }

  @keyframes slideUp {
    from { transform: translateY(16px); opacity: 0.6; }
    to { transform: translateY(0); opacity: 1; }
  }
}
</style>
