<template>
  <section class="content-grid two-columns align-start">
    <div class="panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Task Runner</span>
          <h2>{{ editing ? '编辑任务' : '新建任务' }}</h2>
        </div>
        <button v-if="editing" class="button muted" type="button" @click="resetForm">
          <X :size="16" />
          取消编辑
        </button>
      </div>

      <ol class="wizard">
        <li>
          <span class="step-num">1</span>
          <div class="step-body">
            <strong>选择操作</strong>
            <div class="kind-grid">
              <button
                v-for="kind in TASK_CATALOG"
                :key="kind.value"
                type="button"
                class="kind-card"
                :class="{ active: form.task_type === kind.value, write: kind.risk === 'write' }"
                @click="onPickKind(kind.value)"
              >
                <component :is="kind.icon" :size="20" />
                <strong>{{ kind.label }}</strong>
                <small>{{ kind.description }}</small>
              </button>
            </div>
          </div>
        </li>

        <li>
          <span class="step-num">2</span>
          <div class="step-body">
            <strong>选择账号</strong>
            <AccountPicker v-model="form.library_user_id" />
            <p v-if="!form.library_user_id" class="hint">先到「账号管理」添加图书馆账号。</p>
          </div>
        </li>

        <li>
          <span class="step-num">3</span>
          <div class="step-body">
            <strong>触发方式</strong>
            <div class="seg">
              <button
                type="button"
                class="seg-btn"
                :class="{ active: form.mode === 'manual' }"
                @click="form.mode = 'manual'"
              >
                手动执行
              </button>
              <button
                type="button"
                class="seg-btn"
                :class="{ active: form.mode === 'scheduled' }"
                @click="form.mode = 'scheduled'"
              >
                定时执行
              </button>
            </div>

            <template v-if="form.mode === 'scheduled'">
              <label class="field">
                <span>触发频率</span>
                <select v-model="cronPreset" @change="onCronPresetChange">
                  <option v-for="p in CRON_PRESETS" :key="p.label" :value="p.value">
                    {{ p.label }} <span v-if="p.value">({{ p.example }})</span>
                  </option>
                </select>
              </label>
              <label class="field">
                <span>Cron 表达式</span>
                <input v-model.trim="form.cron" placeholder="0 22 * * *" maxlength="128" />
                <small class="hint">5 字段：分 时 日 月 周。例如 <code>0 22 * * *</code> = 每天 22:00。</small>
              </label>
            </template>
            <p v-else class="hint">创建后到「任务列表」点 ▶ 立即触发。</p>
          </div>
        </li>

        <li v-if="kind.fields.length > 0">
          <span class="step-num">4</span>
          <div class="step-body">
            <strong>参数</strong>

            <label v-if="kind.fields.includes('date') && form.task_type === 'reserve'" class="field">
              <span>日期</span>
              <select v-model="reserveDateMode" @change="onReserveDateModeChange">
                <option v-for="opt in RESERVE_DATE_OPTIONS" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
              <small class="hint">
                T = 任务触发那一天；定时任务以 cron 实际触发当日为基准。当前预览：
                <code>{{ resolvedReserveDateLabel }}</code>
              </small>
            </label>

            <label v-else-if="kind.fields.includes('date')" class="field">
              <span>日期</span>
              <input v-model="payload.date" type="date" @change="onDateChange" />
              <small class="hint">未选择则执行当天。</small>
            </label>

            <label v-if="kind.fields.includes('building')" class="field">
              <span>场馆 ID</span>
              <input v-model.trim="payload.building" placeholder="1" maxlength="8" />
            </label>

            <label v-if="kind.fields.includes('room')" class="field">
              <span>阅览室 ID（可选）</span>
              <input v-model.trim="payload.room" placeholder="留空 = 全部" maxlength="8" />
            </label>

            <div v-if="kind.fields.includes('seat_id')" class="seat-pick">
              <strong>选择座位</strong>

              <div class="seat-search-row">
                <label class="field" style="flex:1">
                  <span>场馆 ID</span>
                  <input v-model.trim="seatBuilding" placeholder="1" maxlength="8" />
                </label>
                <button class="button muted" type="button" :disabled="!form.library_user_id" @click="loadRoomsForTask">
                  <RefreshCw :size="14" />
                  加载阅览室
                </button>
              </div>

              <label class="field">
                <span>阅览室</span>
                <select v-model="seatRoom">
                  <option value="">— 不限 —</option>
                  <option v-for="r in seatRooms" :key="r.room_id" :value="r.room_id">
                    {{ r.name }} ({{ r.room_id }})
                  </option>
                </select>
              </label>

              <button class="button primary" type="button" :disabled="!form.library_user_id || seatLoading" @click="searchSeatsForTask">
                <Search :size="14" />
                搜索座位
              </button>

              <p v-if="seatError" class="notice danger" style="margin-top:8px;">{{ seatError }}</p>

              <p v-if="payload.seat_id" class="notice success" style="margin-top:8px;">
                已选座位 ID：<strong>{{ payload.seat_id }}</strong>
              </p>

              <p v-if="form.task_type === 'reserve' && seatResults.length > 0" class="hint" style="margin-top:8px;">
                状态按
                <strong>{{ form.task_type === 'reserve' ? resolvedReserveDate || '今天' : '今天' }}</strong>
                查询，仅供参考——任务触发时会按计划日期实时下单，<strong>任何状态的座位都可以选</strong>，到点若被占则任务记为失败。
              </p>

              <ul v-if="seatResults.length > 0" class="seat-grid" style="margin-top:8px;">
                <li
                  v-for="seat in seatResults"
                  :key="seat.seat_id"
                  class="seat-card"
                  :class="[
                    { active: String(seat.seat_id) === payload.seat_id, warn: seat.status !== 'free' },
                    seat.status,
                  ]"
                  :title="seat.status !== 'free' ? `查询日期该座位状态：${seat.status}（仍可作为目标，下单时再实时尝试）` : ''"
                  @click="selectSeat(seat)"
                >
                  <strong>{{ seat.name }}</strong>
                  <span class="seat-room">{{ seat.room_name ?? '-' }}</span>
                  <span class="tag" :class="seat.status">{{ seat.status }}</span>
                </li>
              </ul>
            </div>

            <div v-if="kind.fields.includes('start') || kind.fields.includes('end')" class="time-row">
              <label v-if="kind.fields.includes('start')" class="field">
                <span>开始时间</span>
                <select v-model="payload.start" :disabled="!payload.seat_id || loadingStart" @change="onStartChange">
                  <option value="">{{ startPlaceholder }}</option>
                  <option v-for="opt in startTimes" :key="opt.raw_value" :value="opt.raw_value">
                    {{ opt.label }}
                  </option>
                </select>
              </label>
              <label v-if="kind.fields.includes('end')" class="field">
                <span>结束时间</span>
                <select v-model="payload.end" :disabled="!payload.start || loadingEnd">
                  <option value="">{{ endPlaceholder }}</option>
                  <option v-for="opt in endTimes" :key="opt.raw_value" :value="opt.raw_value">
                    {{ opt.label }}
                  </option>
                </select>
              </label>
            </div>

            <label v-if="kind.fields.includes('reservation_id')" class="field">
              <span>预约 ID</span>
              <input v-model.trim="payload.reservation_id" placeholder="1230935" maxlength="32" />
              <small class="hint">在「我的预约」页面凭证 ID 列复制。</small>
            </label>
          </div>
        </li>

        <li>
          <span class="step-num">{{ kind.fields.length > 0 ? 5 : 4 }}</span>
          <div class="step-body">
            <strong>命名 + 启用</strong>
            <label class="field">
              <span>任务名称</span>
              <input v-model.trim="form.name" :placeholder="defaultName" required maxlength="128" />
            </label>
            <label class="switch-row">
              <input v-model="form.enabled" type="checkbox" />
              <span>启用（关闭则定时不会触发，仍可手动运行）</span>
            </label>
          </div>
        </li>
      </ol>

      <div class="form-actions" style="margin-top: 18px;">
        <button class="button primary" type="button" :disabled="!canSave || saving" @click="submit">
          <Save :size="16" />
          {{ editing ? '保存' : '创建' }}
        </button>
        <button v-if="editing" class="button muted" type="button" @click="resetForm">放弃</button>
      </div>

      <p v-if="error" class="notice danger">{{ error }}</p>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Saved</span>
          <h2>任务列表</h2>
        </div>
        <button class="button muted" type="button" @click="loadTasks">
          <RefreshCw :size="16" />
          刷新
        </button>
      </div>

      <div v-if="tasks.length === 0" class="empty-state">
        <ListChecks :size="24" />
        <strong>暂无任务</strong>
        <span>用左侧向导新建一个，例如「每天 22:00 自动签到」。</span>
      </div>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>任务</th>
              <th>操作</th>
              <th>触发</th>
              <th>账号</th>
              <th>状态</th>
              <th class="actions-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in tasks" :key="task.id">
              <td data-label="任务">
                <strong>{{ task.name }}</strong>
              </td>
              <td data-label="操作">
                <component :is="taskKind(task.task_type).icon" :size="14" class="row-icon" />
                {{ taskKind(task.task_type).label }}
              </td>
              <td data-label="触发">
                <span v-if="task.mode === 'scheduled'" class="tag">
                  定时 · <code>{{ task.cron }}</code>
                </span>
                <span v-else class="tag">手动</span>
              </td>
              <td data-label="账号">{{ userLabel(task.library_user_id) }}</td>
              <td data-label="状态">
                <span class="tag" :class="task.enabled ? 'enabled' : 'disabled'">
                  {{ task.enabled ? '启用' : '停用' }}
                </span>
              </td>
              <td data-label="操作">
                <div class="row-actions">
                  <button class="icon-button" type="button" title="立即运行" @click="runTask(task)">
                    <Play :size="16" />
                  </button>
                  <button class="icon-button" type="button" title="编辑" @click="editTask(task)">
                    <Pencil :size="16" />
                  </button>
                  <button class="icon-button danger" type="button" title="删除" @click="removeTask(task.id)">
                    <Trash2 :size="16" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ListChecks, Pencil, Play, RefreshCw, Save, Search, Trash2, X } from '@lucide/vue'

import {
  createTask,
  deleteTask,
  listTasks,
  updateTask,
  type CreateTaskPayload,
  type TaskMode,
  type TaskRecord,
  type TaskType,
} from '@/api/tasks'
import { runJob } from '@/api/jobs'
import { fetchEndTimes, fetchRooms, fetchStartTimes, searchSeats, type Room, type SeatItem, type SearchResult, type TimeOption } from '@/api/library'
import { CRON_PRESETS, TASK_CATALOG, parseTimeLabel, taskKind } from '@/lib/taskCatalog'
import AccountPicker from '@/components/AccountPicker.vue'
import { useUsersStore } from '@/stores/users'

const users = useUsersStore()
const tasks = ref<TaskRecord[]>([])
const editing = ref<TaskRecord | null>(null)
const saving = ref(false)
const error = ref('')
const cronPreset = ref('')

interface FormState {
  name: string
  task_type: TaskType
  mode: TaskMode
  enabled: boolean
  cron: string
  library_user_id: number
}

const form = reactive<FormState>({
  name: '',
  task_type: 'search',
  mode: 'manual',
  enabled: true,
  cron: '',
  library_user_id: 0,
})

interface PayloadState {
  date: string
  building: string
  room: string
  seat_id: string
  start: string
  end: string
  reservation_id: string
}

const payload = reactive<PayloadState>({
  date: '',
  building: '1',
  room: '',
  seat_id: '',
  start: '',
  end: '',
  reservation_id: '',
})

const seatRooms = ref<Room[]>([])
const seatResults = ref<SeatItem[]>([])
const seatLoading = ref(false)
const seatError = ref('')
const seatBuilding = ref('1')
const seatRoom = ref('')

const startTimes = ref<TimeOption[]>([])
const endTimes = ref<TimeOption[]>([])
const loadingStart = ref(false)
const loadingEnd = ref(false)

const RESERVE_DATE_OPTIONS: { value: string; label: string; offset: number }[] = [
  // T = 任务触发那一天 (基准日)。沿用结算/排期里 T+N 的标准写法，
  // 让用户从标签就能看出日期是相对而非绝对。
  { value: '0', label: 'T+0  执行当日', offset: 0 },
  { value: '1', label: 'T+1  次日', offset: 1 },
  { value: '2', label: 'T+2', offset: 2 },
  { value: '3', label: 'T+3', offset: 3 },
  { value: '4', label: 'T+4', offset: 4 },
  { value: '5', label: 'T+5', offset: 5 },
]

// reserveDateMode 总是 RESERVE_DATE_OPTIONS 里的 value (字符串化的偏移天数)
const reserveDateMode = ref<string>('0')

const reserveDateOffset = computed(() => Number(reserveDateMode.value))

function isoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function dateForOffset(offset: number): string {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() + offset)
  return isoDate(d)
}

// 当前 reserve 任务实际生效的日期 (传给 fetchStartTimes 等)
const resolvedReserveDate = computed(() => {
  if (form.task_type !== 'reserve') return payload.date
  return dateForOffset(reserveDateOffset.value)
})

const resolvedReserveDateLabel = computed(() => {
  const iso = resolvedReserveDate.value
  if (!iso) return '—'
  const d = new Date(iso + 'T00:00:00')
  const weekday = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  return `${iso} (周${weekday})`
})

function onReserveDateModeChange(): void {
  // 把映射到实际日期的字符串同步进 payload.date，让兼容 absolute date
  // 的 effectiveDate() 也能拿到正确值；座位时段需要按新日期重算。
  payload.date = resolvedReserveDate.value
  if (payload.seat_id) {
    payload.start = ''
    payload.end = ''
    endTimes.value = []
    loadStartTimesForTask()
  }
}

const kind = computed(() => taskKind(form.task_type))
const defaultName = computed(() => `${kind.value.label}任务`)
const canSave = computed(() => !!form.library_user_id && (form.mode !== 'scheduled' || !!form.cron))

const startPlaceholder = computed(() => {
  if (!payload.seat_id) return '— 请先选座位 —'
  if (loadingStart.value) return '— 加载中… —'
  if (startTimes.value.length === 0) return '— 该座位暂无可选时段 —'
  return '— 请选择开始时间 —'
})

const endPlaceholder = computed(() => {
  if (!payload.seat_id) return '— 请先选座位 —'
  if (!payload.start) return '— 请先选开始时间 —'
  if (loadingEnd.value) return '— 加载中… —'
  if (endTimes.value.length === 0) return '— 该开始时间无可选时段 —'
  return '— 请选择结束时间 —'
})

onMounted(async () => {
  await users.fetchUsers()
  if (users.defaultUserId !== null && form.library_user_id === 0) {
    form.library_user_id = users.defaultUserId
  }
  await loadTasks()
})

watch(
  () => form.task_type,
  () => {
    if (!form.name || form.name.endsWith('任务')) {
      form.name = defaultName.value
    }
  },
  { immediate: true },
)

async function loadTasks(): Promise<void> {
  tasks.value = await listTasks()
}

function userLabel(id: number): string {
  const u = users.items.find((x) => x.id === id)
  return u ? u.username : `#${id}`
}

function onPickKind(value: TaskType): void {
  form.task_type = value
}

function onCronPresetChange(): void {
  if (cronPreset.value) form.cron = cronPreset.value
}

async function loadRoomsForTask(): Promise<void> {
  if (!form.library_user_id) return
  seatError.value = ''
  try {
    seatRooms.value = await fetchRooms(form.library_user_id, seatBuilding.value)
  } catch (err) {
    seatError.value = err instanceof Error ? err.message : '加载阅览室失败'
  }
}

async function searchSeatsForTask(): Promise<void> {
  if (!form.library_user_id) return
  seatError.value = ''
  seatLoading.value = true
  try {
    const result = await searchSeats(form.library_user_id, {
      // For reserve tasks query the target date so statuses reflect that
      // day instead of "now"; the seat picker no longer gates on status,
      // but at least the badge stops lying about a different day.
      on_date: form.task_type === 'reserve' ? effectiveDate() || undefined : undefined,
      building: seatBuilding.value || undefined,
      room: seatRoom.value || undefined,
      offset: 1,
    })
    seatResults.value = result.seats
  } catch (err) {
    seatError.value = err instanceof Error ? err.message : '搜索座位失败'
  } finally {
    seatLoading.value = false
  }
}

async function selectSeat(seat: SeatItem): Promise<void> {
  // 任务向导承诺的是「未来某个时刻去抢这个座位」，不是即时下单，所以
  // 不再用 status 拦截。`SeatSearchView` 一次性预约场景仍保留 free-only。
  seatError.value = ''
  payload.seat_id = String(seat.seat_id)
  payload.start = ''
  payload.end = ''
  startTimes.value = []
  endTimes.value = []
  await loadStartTimesForTask()
}

function effectiveDate(): string {
  // 给上游传的日期：T+0 时返回空字符串，让上游按它自己的「今天」逻辑解析；
  // 否则给具体的 YYYY-MM-DD。这里有一段经验：从干净会话直接对
  // /freeBook/ajaxSearch 或 /freeBook/ajaxGetTime 显式传 today 的 ISO 串，
  // 上游会返回空时段（用户报告的 bug 现象）；改传空串后稳定。猜测上游有
  // 一段「先按默认状态被点过一次」的隐式 prime 需求，对 T+0 我们绕过它。
  if (form.task_type === 'reserve') {
    return reserveDateOffset.value === 0 ? '' : resolvedReserveDate.value
  }
  return payload.date
}

async function loadStartTimesForTask(): Promise<void> {
  if (!payload.seat_id || !form.library_user_id) return
  loadingStart.value = true
  try {
    const result = await fetchStartTimes(
      form.library_user_id,
      Number(payload.seat_id),
      effectiveDate(),
    )
    startTimes.value = result.options
  } catch (err) {
    seatError.value = err instanceof Error ? err.message : '加载开始时间失败'
  } finally {
    loadingStart.value = false
  }
}

async function loadEndTimesForTask(): Promise<void> {
  if (!payload.start || !payload.seat_id || !form.library_user_id) return
  loadingEnd.value = true
  try {
    endTimes.value = await fetchEndTimes(
      form.library_user_id,
      Number(payload.seat_id),
      payload.start,
      effectiveDate(),
    )
  } catch (err) {
    seatError.value = err instanceof Error ? err.message : '加载结束时间失败'
  } finally {
    loadingEnd.value = false
  }
}

function onDateChange(): void {
  if (payload.seat_id) {
    payload.start = ''
    payload.end = ''
    endTimes.value = []
    loadStartTimesForTask()
  }
}

function onStartChange(): void {
  payload.end = ''
  endTimes.value = []
  loadEndTimesForTask()
}

function buildPayload(): Record<string, unknown> | null {
  const out: Record<string, unknown> = {}
  for (const field of kind.value.fields) {
    if (field === 'date' && form.task_type === 'reserve') {
      // Reserve 任务永远用相对偏移，后端在运行时算出实际日期，避免到点
      // 跑的还是创建时那天的硬编码值。
      out.date_offset = reserveDateOffset.value
      continue
    }
    const v = payload[field as keyof PayloadState]
    if (!v) continue
    if (field === 'seat_id') {
      const n = Number(v)
      if (!Number.isFinite(n)) {
        error.value = '座位 ID 必须是数字'
        return null
      }
      out.seat_id = n
    } else if (field === 'start' || field === 'end') {
      const str = String(v)
      const fieldLabel = field === 'start' ? '开始' : '结束'
      if (/^\d+$/.test(str)) {
        const minutes = Number(str)
        if (minutes < 0 || minutes >= 24 * 60) {
          error.value = `${fieldLabel}时间超出范围`
          return null
        }
        out[field] = str
      } else {
        const minutes = parseTimeLabel(str)
        if (minutes === null) {
          error.value = `${fieldLabel}时间格式应为 HH:MM`
          return null
        }
        out[field] = String(minutes)
      }
    } else {
      out[field] = v
    }
  }
  if (out.start !== undefined && out.end !== undefined) {
    if (Number(out.end) <= Number(out.start)) {
      error.value = '结束时间必须晚于开始时间'
      return null
    }
  }
  return out
}

function resetForm(): void {
  editing.value = null
  form.name = defaultName.value
  form.task_type = 'search'
  form.mode = 'manual'
  form.enabled = true
  form.cron = ''
  form.library_user_id = users.defaultUserId ?? 0
  cronPreset.value = ''
  payload.date = ''
  payload.building = '1'
  payload.room = ''
  payload.seat_id = ''
  payload.start = ''
  payload.end = ''
  payload.reservation_id = ''
  reserveDateMode.value = '0'
  seatRooms.value = []
  seatResults.value = []
  seatError.value = ''
  seatBuilding.value = '1'
  seatRoom.value = ''
  startTimes.value = []
  endTimes.value = []
  loadingStart.value = false
  loadingEnd.value = false
  error.value = ''
}

async function editTask(task: TaskRecord): Promise<void> {
  editing.value = task
  form.name = task.name
  form.task_type = task.task_type
  form.mode = task.mode
  form.enabled = task.enabled
  form.cron = task.cron ?? ''
  form.library_user_id = task.library_user_id
  cronPreset.value = CRON_PRESETS.find((p) => p.value === (task.cron ?? ''))?.value ?? ''
  const p = task.payload ?? {}
  payload.date = String(p.date ?? '')
  if (task.task_type === 'reserve') {
    // 新 schema：reserve 永远走相对偏移；老任务里可能存的是绝对 date 或
    // 超过 +5 的 offset，统一回退到「当天」并清掉绝对日期。
    const offsetRaw = p.date_offset
    const offset = Number(offsetRaw)
    const matched = RESERVE_DATE_OPTIONS.find((o) => o.offset === offset)
    reserveDateMode.value = matched ? matched.value : '0'
    payload.date = resolvedReserveDate.value
  } else {
    reserveDateMode.value = '0'
  }
  payload.building = String(p.building ?? '1')
  payload.room = String(p.room ?? '')
  payload.seat_id = p.seat_id !== undefined ? String(p.seat_id) : ''
  const startVal = p.start
  payload.start =
    typeof startVal === 'string' && /^\d+$/.test(startVal)
      ? startVal
      : String(startVal ?? '')
  const endVal = p.end
  payload.end =
    typeof endVal === 'string' && /^\d+$/.test(endVal)
      ? endVal
      : String(endVal ?? '')
  payload.reservation_id = String(p.reservation_id ?? '')
  seatRooms.value = []
  seatResults.value = []
  seatError.value = ''
  startTimes.value = []
  endTimes.value = []
  error.value = ''
  if (payload.seat_id && form.library_user_id) {
    try {
      const st = await fetchStartTimes(form.library_user_id, Number(payload.seat_id), payload.date)
      startTimes.value = st.options
      if (payload.start && payload.seat_id) {
        endTimes.value = await fetchEndTimes(
          form.library_user_id,
          Number(payload.seat_id),
          payload.start,
          payload.date,
        )
      }
    } catch { /* ignore — user can re-trigger by re-selecting seat */ }
  }
}

async function submit(): Promise<void> {
  error.value = ''
  if (!form.library_user_id) {
    error.value = '请选择账号'
    return
  }
  const built = buildPayload()
  if (built === null) return
  const body: CreateTaskPayload = {
    name: form.name || defaultName.value,
    task_type: form.task_type,
    mode: form.mode,
    enabled: form.enabled,
    cron: form.mode === 'scheduled' ? form.cron || null : null,
    library_user_id: form.library_user_id,
    payload: Object.keys(built).length > 0 ? built : null,
  }
  saving.value = true
  try {
    if (editing.value) {
      await updateTask(editing.value.id, {
        name: body.name,
        task_type: body.task_type,
        mode: body.mode,
        enabled: body.enabled,
        cron: body.cron,
        payload: body.payload,
      })
    } else {
      await createTask(body)
    }
    resetForm()
    await loadTasks()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function removeTask(id: number): Promise<void> {
  if (!window.confirm('删除该任务？')) return
  await deleteTask(id)
  await loadTasks()
}

async function runTask(task: TaskRecord): Promise<void> {
  const k = taskKind(task.task_type)
  const accountLabel = userLabel(task.library_user_id)
  const lines = [`将以「${accountLabel}」执行「${k.label}」？`]
  if (k.risk === 'write') {
    lines.push('该操作会调用真实写接口，未开启 ALLOW_MUTATION_TEST 时会被 blocked。')
  }
  if (!window.confirm(lines.join('\n'))) return
  try {
    await runJob({ task_id: task.id })
    window.alert('已触发，到「运行历史」/「实时日志」查看。')
  } catch (err) {
    const msg = err instanceof Error ? err.message : '执行失败'
    window.alert(msg)
  }
}
</script>

<style scoped>
.wizard {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 16px;
}

.wizard li {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.step-num {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--primary);
  color: #ffffff;
  font-weight: 700;
  font-size: 0.82rem;
}

.step-body {
  display: grid;
  gap: 8px;
}

.step-body > strong {
  font-size: 0.92rem;
}

.kind-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
}

.kind-card {
  display: grid;
  gap: 4px;
  padding: 12px;
  text-align: left;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel-muted);
  color: var(--text);
  cursor: pointer;
}

.kind-card small {
  color: var(--text-muted);
  font-size: 0.78rem;
}

.kind-card.active {
  border-color: var(--primary);
  background: #eaf7f4;
  box-shadow: 0 0 0 2px rgb(15 118 110 / 16%);
}

.kind-card.write::after {
  content: '写';
  position: relative;
  align-self: flex-start;
  padding: 1px 6px;
  border-radius: 4px;
  background: #fff3d8;
  color: #86520b;
  font-size: 0.7rem;
  font-weight: 700;
}

.seg {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.seg-btn {
  padding: 6px 14px;
  border: none;
  background: var(--panel-muted);
  color: var(--text-muted);
  font-size: 0.84rem;
  font-weight: 600;
}

.seg-btn.active {
  background: var(--primary);
  color: #ffffff;
}

.time-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.hint {
  margin: 4px 0 0;
  color: var(--text-muted);
  font-size: 0.78rem;
}

.row-icon {
  vertical-align: middle;
  margin-right: 4px;
}

.seat-pick {
  display: grid;
  gap: 8px;
}

.seat-search-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.seat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.seat-card {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel-muted);
  cursor: pointer;
}

.seat-card.active {
  border-color: var(--primary);
  background: #eaf7f4;
  box-shadow: 0 0 0 2px rgb(15 118 110 / 24%);
}

.seat-card.free {
  border-color: #b7dfd7;
  background: #eaf7f4;
}

.seat-card.warn {
  /* Non-free seat for a future task — still selectable, just visually
     muted so the user knows the displayed status was just a snapshot. */
  opacity: 0.72;
  border-style: dashed;
}

.seat-card.warn.active {
  opacity: 1;
  border-style: solid;
}

.seat-room {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.notice.success {
  color: #0f684d;
  background: #e6f6ef;
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.84rem;
}

@media (max-width: 640px) {
  .wizard li {
    grid-template-columns: 26px minmax(0, 1fr);
    gap: 10px;
  }

  .kind-grid {
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .kind-card {
    padding: 10px;
  }

  .kind-card small {
    display: none;
  }

  .time-row {
    grid-template-columns: 1fr;
  }

  .seat-search-row {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .seat-search-row .button {
    align-self: flex-start;
  }

  .seat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .seg {
    width: 100%;
  }

  .seg-btn {
    flex: 1;
    padding: 10px 0;
    font-size: 0.92rem;
  }
}
</style>
