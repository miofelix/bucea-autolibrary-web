<template>
  <section class="log-panel">
    <div class="log-toolbar">
      <div>
        <h2>实时日志</h2>
        <p>{{ statusText }}</p>
      </div>
      <div class="row-actions">
        <label class="field inline">
          <span>作业 ID</span>
          <input v-model.number="jobId" type="number" min="1" placeholder="123" />
        </label>
        <button class="button primary" type="button" :disabled="!jobId" @click="start">
          <Play :size="14" />
          连接
        </button>
        <button class="button muted" type="button" :disabled="!connected" @click="stop">
          <Square :size="14" />
          断开
        </button>
        <button class="button muted" type="button" @click="lines = []">
          <Trash2 :size="14" />
          清空
        </button>
      </div>
    </div>

    <pre class="log-output">{{ output }}</pre>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Play, Square, Trash2 } from '@lucide/vue'

import { logStreamUrl, type JobLogRecord } from '@/api/logs'

const route = useRoute()
const jobId = ref<number | null>(null)
const lines = ref<string[]>([])
const connected = ref(false)
let source: EventSource | null = null

const output = computed(() => (lines.value.length > 0 ? lines.value.join('\n') : '等待日志…'))
const statusText = computed(() => {
  if (!jobId.value) return '请输入作业 ID 后连接'
  return connected.value ? `已连接作业 #${jobId.value}` : '未连接'
})

onMounted(() => {
  const fromQuery = route.query.job
  if (fromQuery) {
    const parsed = Number(fromQuery)
    if (Number.isFinite(parsed)) {
      jobId.value = parsed
      start()
    }
  }
})

onBeforeUnmount(stop)

function start() {
  stop()
  if (!jobId.value) return
  lines.value = []
  source = new EventSource(logStreamUrl(jobId.value), { withCredentials: true })
  source.addEventListener('log', (event) => {
    try {
      const data = JSON.parse((event as MessageEvent).data) as JobLogRecord
      lines.value.push(`[${data.level}] ${data.created_at} ${data.message}`)
    } catch {
      lines.value.push(String((event as MessageEvent).data))
    }
  })
  source.onopen = () => {
    connected.value = true
  }
  source.onerror = () => {
    connected.value = false
  }
}

function stop() {
  connected.value = false
  if (source) {
    source.close()
    source = null
  }
}
</script>

<style scoped>
.field.inline {
  display: inline-grid;
  grid-template-columns: auto 120px;
  align-items: center;
  gap: 8px;
}

.field.inline input {
  min-height: 32px;
}

.button.primary,
.button.muted {
  min-height: 32px;
  padding: 0 10px;
}
</style>
