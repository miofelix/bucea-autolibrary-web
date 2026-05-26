<template>
  <section v-if="announcement" class="announcement">
    <Megaphone :size="18" />
    <span>{{ announcement }}</span>
  </section>

  <section class="dashboard-grid">
    <article class="metric-card">
      <div class="metric-icon success">
        <Server :size="20" />
      </div>
      <div>
        <span>后端健康</span>
        <strong>{{ healthLabel }}</strong>
      </div>
    </article>

    <article class="metric-card">
      <div class="metric-icon">
        <Users :size="20" />
      </div>
      <div>
        <span>启用账号</span>
        <strong>{{ users.enabledCount }} / {{ users.items.length }}</strong>
      </div>
    </article>

    <article class="metric-card">
      <div class="metric-icon" :class="reservationStatusVariant">
        <CalendarClock :size="20" />
      </div>
      <div>
        <span>当前预约状态</span>
        <strong>{{ reservationStatusLabel }}</strong>
      </div>
    </article>

    <article class="metric-card">
      <div class="metric-icon" :class="checkInVariant">
        <CheckCircle2 :size="20" />
      </div>
      <div>
        <span>签到状态</span>
        <strong>{{ checkInLabel }}</strong>
      </div>
    </article>
  </section>

  <section class="content-grid two-columns">
    <div class="panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Session</span>
          <h2>当前账号</h2>
        </div>
        <AccountPicker v-model="userId" />
      </div>

      <div v-if="!userId" class="empty-state">
        <KeyRound :size="24" />
        <strong>选择账号</strong>
        <span>选择账号后会显示其会话状态。</span>
      </div>

      <div v-else-if="session" class="settings-list">
        <div class="settings-row">
          <span>登录状态</span>
          <span class="tag" :class="session.logged_in ? 'enabled' : 'disabled'">
            {{ session.logged_in ? '已登录' : '未登录' }}
          </span>
        </div>
        <div class="settings-row">
          <span>sysUsername</span>
          <code>{{ session.sys_username ?? '-' }}</code>
        </div>
        <div class="settings-row">
          <span>预约状态</span>
          <code>{{ reservationStatusRaw }}</code>
        </div>
        <div class="settings-row">
          <span>已签到</span>
          <code>{{ checkInRaw }}</code>
        </div>
        <div class="settings-row">
          <span>软模式</span>
          <code>{{ softModeRaw }}</code>
        </div>
      </div>

      <div class="form-actions" style="margin-top: 16px;">
        <RouterLink class="button muted" to="/library">
          <KeyRound :size="16" />
          会话详情
        </RouterLink>
        <RouterLink class="button muted" to="/reservations">
          <CalendarRange :size="16" />
          我的预约
        </RouterLink>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Sessions</span>
          <h2>所有账号会话</h2>
        </div>
        <button class="button muted" type="button" :disabled="loadingSnapshots" @click="loadSnapshots">
          <RefreshCw :size="16" />
          刷新
        </button>
      </div>

      <div v-if="users.items.length === 0" class="empty-state">
        <Users :size="24" />
        <strong>暂无账号</strong>
        <span>到「账号管理」添加图书馆账号。</span>
      </div>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>账号</th>
              <th>会话</th>
              <th>sysUsername</th>
              <th>预约状态</th>
              <th>签到</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="snap in snapshots" :key="snap.user.id">
              <td data-label="账号">
                <strong>{{ snap.user.username }}</strong>
                <span v-if="snap.user.display_name" class="hint">{{ snap.user.display_name }}</span>
              </td>
              <td data-label="会话">
                <span class="tag" :class="snap.session?.logged_in ? 'enabled' : 'disabled'">
                  {{ snap.session?.logged_in ? '已登录' : '未登录' }}
                </span>
              </td>
              <td data-label="sysUsername"><code>{{ snap.session?.sys_username ?? '-' }}</code></td>
              <td data-label="预约状态">
                <code>{{ snap.session?.user_info?.currentReservationStatus ?? '-' }}</code>
              </td>
              <td data-label="签到">
                <code>{{ snap.session?.user_info?.userCheckedIn ?? '-' }}</code>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  CalendarClock,
  CalendarRange,
  CheckCircle2,
  KeyRound,
  Megaphone,
  RefreshCw,
  Server,
  Users,
} from '@lucide/vue'

import AccountPicker from '@/components/AccountPicker.vue'
import { getHealth } from '@/api/client'
import { fetchAnnouncement, fetchSession, type SessionStatus } from '@/api/library'
import { useUsersStore } from '@/stores/users'
import type { LibraryUser } from '@/api/users'

type Snapshot = {
  user: LibraryUser
  session: SessionStatus | null
}

const users = useUsersStore()
const health = ref<'checking' | 'ok' | 'failed'>('checking')
const userId = ref<number | null>(null)
const session = ref<SessionStatus | null>(null)
const announcement = ref<string | null>(null)
const snapshots = ref<Snapshot[]>([])
const loadingSnapshots = ref(false)

const healthLabel = computed(() => {
  if (health.value === 'ok') return 'ok'
  if (health.value === 'failed') return '不可用'
  return '检查中'
})

const reservationStatusRaw = computed(
  () => String(session.value?.user_info?.currentReservationStatus ?? '-'),
)
const checkInRaw = computed(() => String(session.value?.user_info?.userCheckedIn ?? '-'))
const softModeRaw = computed(() => String(session.value?.user_info?.softMode ?? '-'))

const reservationStatusLabel = computed(() => {
  const raw = session.value?.user_info?.currentReservationStatus
  if (raw === 'NO_RESERVATION') return '无预约'
  if (raw === 'HAVE_RESERVATION') return '有预约'
  if (typeof raw === 'string') return raw
  return userId.value ? '未登录' : '未选账号'
})

const reservationStatusVariant = computed(() => {
  const raw = session.value?.user_info?.currentReservationStatus
  if (raw === 'HAVE_RESERVATION') return 'success'
  if (raw === 'NO_RESERVATION') return ''
  return 'warning'
})

const checkInLabel = computed(() => {
  const raw = session.value?.user_info?.userCheckedIn
  if (raw === true) return '已签到'
  if (raw === false) return '未签到'
  return '-'
})

const checkInVariant = computed(() => {
  const raw = session.value?.user_info?.userCheckedIn
  if (raw === true) return 'success'
  if (raw === false) return ''
  return 'warning'
})

watch(userId, async (value) => {
  session.value = null
  announcement.value = null
  if (!value) return
  await Promise.all([loadSession(), loadAnnouncement()])
})

async function loadSession() {
  if (!userId.value) return
  try {
    session.value = await fetchSession(userId.value)
  } catch {
    session.value = null
  }
}

async function loadAnnouncement() {
  if (!userId.value) return
  try {
    const result = await fetchAnnouncement(userId.value)
    announcement.value = result.roll_text
  } catch {
    announcement.value = null
  }
}

async function loadSnapshots() {
  loadingSnapshots.value = true
  try {
    await users.fetchUsers()
    snapshots.value = await Promise.all(
      users.items.map(async (user) => ({
        user,
        session: await fetchSession(user.id).catch(() => null),
      })),
    )
  } finally {
    loadingSnapshots.value = false
  }
}

onMounted(async () => {
  try {
    await getHealth()
    health.value = 'ok'
  } catch {
    health.value = 'failed'
  }
  await loadSnapshots()
})
</script>

<style scoped>
.announcement {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border: 1px solid #f0d68a;
  border-radius: 8px;
  background: #fff7e6;
  color: #7c4a03;
  font-weight: 600;
  margin-bottom: 14px;
}

.hint {
  display: block;
  margin-top: 2px;
  color: var(--text-muted);
  font-size: 0.78rem;
}
</style>
