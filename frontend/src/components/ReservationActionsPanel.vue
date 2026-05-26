<template>
  <div class="panel-inner">
    <p class="hint">
      所有按钮直接调用上游写接口；后端 ALLOW_MUTATION_TEST 关闭时会返回 blocked。
      调用前会弹出二次确认。
    </p>

    <div class="action-grid">
      <button
        class="button"
        type="button"
        :disabled="busy || !userId"
        @click="run('check-in', '签到', checkIn)"
      >
        <CheckCircle2 :size="16" />
        签到
      </button>
      <button
        class="button"
        type="button"
        :disabled="busy || !userId"
        @click="run('renew', '续约', renew)"
      >
        <RotateCw :size="16" />
        续约
      </button>
      <button
        class="button"
        type="button"
        :disabled="busy || !userId"
        @click="run('leave', '暂离', leave)"
      >
        <PauseCircle :size="16" />
        暂离
      </button>
      <button
        class="button"
        type="button"
        :disabled="busy || !userId"
        @click="run('resume', '返回 (从暂离)', resume)"
      >
        <PlayCircle :size="16" />
        返回
      </button>
      <button
        class="button danger"
        type="button"
        :disabled="busy || !userId"
        @click="run('stop-using', '结束使用', stopUse)"
      >
        <StopCircle :size="16" />
        结束使用
      </button>
    </div>

    <ul v-if="results.length > 0" class="result-log">
      <li v-for="(r, idx) in results" :key="idx" :class="r.ok ? 'ok' : 'fail'">
        <strong>{{ r.label }}</strong>
        <span>{{ r.message }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  CheckCircle2,
  PauseCircle,
  PlayCircle,
  RotateCw,
  StopCircle,
} from '@lucide/vue'

import {
  checkInLibrary,
  leaveLibrary,
  renewLibrary,
  resumeLibrary,
  stopUsing,
  type MutationResponse,
} from '@/api/library'
import { ApiError } from '@/api/client'

interface Props {
  userId: number | null
}

interface ResultRow {
  label: string
  message: string
  ok: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  changed: []
}>()

const busy = ref(false)
const results = ref<ResultRow[]>([])

type ActionFn = (id: number) => Promise<MutationResponse>

const checkIn: ActionFn = (id) => checkInLibrary(id)
const renew: ActionFn = (id) => renewLibrary(id)
const leave: ActionFn = (id) => leaveLibrary(id)
const resume: ActionFn = (id) => resumeLibrary(id)
const stopUse: ActionFn = (id) => stopUsing(id)

async function run(key: string, label: string, fn: ActionFn): Promise<void> {
  if (!props.userId) return
  if (!window.confirm(`确认执行「${label}」？此操作会直接调用上游接口。`)) return
  busy.value = true
  try {
    const res = await fn(props.userId)
    results.value = [
      { label, message: res.message || (res.success ? '成功' : '失败'), ok: res.success },
      ...results.value,
    ].slice(0, 10)
    if (res.success) emit('changed')
  } catch (err) {
    const message = err instanceof ApiError
      ? err.message
      : err instanceof Error
        ? err.message
        : '请求失败'
    results.value = [{ label, message, ok: false }, ...results.value].slice(0, 10)
  } finally {
    busy.value = false
    void key
  }
}
</script>

<style scoped>
.panel-inner {
  display: grid;
  gap: 14px;
}

.hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}

.button.danger {
  color: #ffffff;
  background: var(--danger);
}

.button.danger:hover:not(:disabled) {
  background: #95201a;
}

.result-log {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 6px;
  max-height: 220px;
  overflow: auto;
}

.result-log li {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel-muted);
  font-size: 0.85rem;
}

@media (max-width: 640px) {
  .action-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .result-log li {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}

.result-log li.ok {
  border-color: #b7dfd7;
  background: #eaf7f4;
}

.result-log li.fail {
  border-color: #f0caca;
  background: #fff0ee;
}
</style>
