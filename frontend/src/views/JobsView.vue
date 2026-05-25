<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <span class="eyebrow">History</span>
        <h2>运行历史</h2>
      </div>
      <button class="button muted" type="button" @click="load">
        <RefreshCw :size="16" />
        刷新
      </button>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>作业 ID</th>
            <th>任务</th>
            <th>账号</th>
            <th>状态</th>
            <th>开始</th>
            <th>结束</th>
            <th>结果</th>
            <th class="actions-col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="jobs.length === 0"><td colspan="8">暂无作业</td></tr>
          <tr v-for="job in jobs" :key="job.id">
            <td>{{ job.id }}</td>
            <td>{{ job.task_type }}{{ job.task_id ? ` · #${job.task_id}` : '' }}</td>
            <td>{{ job.library_user_id }}</td>
            <td>
              <span class="tag" :class="job.status">{{ job.status }}</span>
            </td>
            <td>{{ formatTime(job.started_at) }}</td>
            <td>{{ formatTime(job.finished_at) }}</td>
            <td>{{ job.summary ?? '-' }}</td>
            <td>
              <RouterLink class="button muted small" :to="`/logs?job=${job.id}`">
                <ScrollText :size="14" />
                日志
              </RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RefreshCw, ScrollText } from '@lucide/vue'

import { listJobs, type JobRecord } from '@/api/jobs'

const jobs = ref<JobRecord[]>([])

onMounted(load)

async function load() {
  jobs.value = await listJobs()
}

function formatTime(value: string | null): string {
  if (!value) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value))
}
</script>

<style scoped>
.tag.success {
  color: #0f684d;
  background: #e6f6ef;
}

.tag.running,
.tag.pending {
  color: #2f6feb;
  background: #eaf1ff;
}

.tag.failed,
.tag.cancelled {
  color: #b42318;
  background: #fff0ee;
}

.tag.blocked_need_user_confirmation {
  color: #86520b;
  background: #fff3d8;
}

.button.small {
  min-height: 30px;
  padding: 0 10px;
  font-size: 0.82rem;
}
</style>
