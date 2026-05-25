<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <span class="eyebrow">/history?type=SEAT</span>
        <h2>我的预约</h2>
      </div>
      <div class="row-actions">
        <AccountPicker v-model="userId" />
        <button class="button muted" type="button" :disabled="!userId || loading" @click="load">
          <RefreshCw :size="16" />
          刷新
        </button>
      </div>
    </div>

    <p v-if="error" class="notice danger">{{ error }}</p>

    <div v-if="!userId" class="empty-state">
      <CalendarRange :size="24" />
      <strong>请选择账号</strong>
      <span>登录会话后才能查询历史预约。</span>
    </div>

    <div v-else-if="loading" class="empty-state">
      <Loader :size="24" />
      <strong>加载中</strong>
    </div>

    <div v-else-if="entries.length === 0" class="empty-state">
      <CalendarRange :size="24" />
      <strong>暂无预约记录</strong>
      <span>登录会话存活期间，凭证 / 详情来自 /history 页面解析结果。</span>
    </div>

    <div v-else class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>日期</th>
            <th>时间</th>
            <th>位置</th>
            <th>状态</th>
            <th>凭证 ID</th>
            <th class="actions-col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in entries" :key="(entry.reservation_id ?? '') + (entry.date ?? '')">
            <td>
              <strong>{{ entry.date ?? entry.raw_date_label ?? '-' }}</strong>
              <span v-if="entry.raw_date_label && entry.raw_date_label !== entry.date" class="hint">
                {{ entry.raw_date_label }}
              </span>
            </td>
            <td>{{ entry.start_label && entry.end_label ? `${entry.start_label} - ${entry.end_label}` : '-' }}</td>
            <td>{{ entry.room_name ?? '-' }}</td>
            <td>
              <span class="tag" :class="statusClass(entry.status)">{{ entry.status ?? '-' }}</span>
            </td>
            <td><code>{{ entry.reservation_id ?? '-' }}</code></td>
            <td>
              <button
                class="icon-button"
                type="button"
                title="查看详情"
                :disabled="!entry.reservation_id"
                @click="openDetail(entry.reservation_id!)"
              >
                <Eye :size="16" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <section v-if="userId" class="panel">
    <div class="panel-header">
      <div>
        <span class="eyebrow">Live Actions</span>
        <h2>当前预约操作</h2>
      </div>
    </div>
    <ReservationActionsPanel :user-id="userId" @changed="load" />
  </section>

  <ReservationDetailDialog
    v-if="detailId && userId"
    :user-id="userId"
    :reservation-id="detailId"
    @close="detailId = null"
  />
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { CalendarRange, Eye, Loader, RefreshCw } from '@lucide/vue'

import AccountPicker from '@/components/AccountPicker.vue'
import ReservationActionsPanel from '@/components/ReservationActionsPanel.vue'
import ReservationDetailDialog from '@/components/ReservationDetailDialog.vue'
import { fetchHistory, type HistoryEntry } from '@/api/library'

const userId = ref<number | null>(null)
const entries = ref<HistoryEntry[]>([])
const loading = ref(false)
const error = ref('')
const detailId = ref<string | null>(null)

function openDetail(id: string): void {
  detailId.value = id
}

watch(userId, async (value) => {
  entries.value = []
  if (value) await load()
})

async function load() {
  if (!userId.value) return
  loading.value = true
  error.value = ''
  try {
    entries.value = await fetchHistory(userId.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载预约记录失败'
  } finally {
    loading.value = false
  }
}

function statusClass(status: string | null): string {
  if (!status) return 'disabled'
  if (status.includes('已预约')) return 'success'
  if (status.includes('使用中')) return 'success'
  if (status.includes('已完成') || status.includes('已结束')) return 'enabled'
  if (status.includes('已取消')) return 'disabled'
  if (status.includes('失约') || status.includes('迟到')) return 'needs_user_confirmation'
  return 'disabled'
}
</script>

<style scoped>
.hint {
  display: block;
  margin-top: 2px;
  color: var(--text-muted);
  font-size: 0.78rem;
}
</style>
