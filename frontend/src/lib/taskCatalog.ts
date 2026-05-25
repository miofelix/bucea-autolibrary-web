import {
  CalendarPlus,
  CheckCircle2,
  PauseCircle,
  PlayCircle,
  RotateCw,
  Search,
  StopCircle,
  XCircle,
} from '@lucide/vue'
import type { Component } from 'vue'

import type { TaskType } from '@/api/tasks'

export type TaskField =
  | 'date'
  | 'building'
  | 'room'
  | 'seat_id'
  | 'start'
  | 'end'
  | 'reservation_id'

export interface TaskKind {
  value: TaskType
  label: string
  short: string
  description: string
  icon: Component
  risk: 'read' | 'write'
  fields: TaskField[]
}

export const TASK_CATALOG: TaskKind[] = [
  {
    value: 'search',
    label: '搜索座位',
    short: '搜索',
    description: '按条件查询可预约座位。只读，不下单。',
    icon: Search,
    risk: 'read',
    fields: ['date', 'building', 'room'],
  },
  {
    value: 'reserve',
    label: '提交预约',
    short: '预约',
    description: '为指定座位提交预约。写操作，受 ALLOW_MUTATION_TEST 门控。',
    icon: CalendarPlus,
    risk: 'write',
    fields: ['date', 'seat_id', 'start', 'end'],
  },
  {
    value: 'cancel',
    label: '取消预约',
    short: '取消',
    description: '按预约 ID 取消已下单的预约。写操作。',
    icon: XCircle,
    risk: 'write',
    fields: ['reservation_id'],
  },
  {
    value: 'checkin',
    label: '签到',
    short: '签到',
    description: '当前预约时段到达后签到。写操作。',
    icon: CheckCircle2,
    risk: 'write',
    fields: [],
  },
  {
    value: 'renew',
    label: '续约',
    short: '续约',
    description: '当前已用时段到期前续时。写操作。',
    icon: RotateCw,
    risk: 'write',
    fields: [],
  },
  {
    value: 'leave',
    label: '暂离',
    short: '暂离',
    description: '标记暂离，保留座位。写操作。',
    icon: PauseCircle,
    risk: 'write',
    fields: [],
  },
  {
    value: 'resume',
    label: '返回',
    short: '返回',
    description: '从暂离恢复使用。写操作。',
    icon: PlayCircle,
    risk: 'write',
    fields: [],
  },
  {
    value: 'stop_using',
    label: '结束使用',
    short: '结束',
    description: '主动释放座位。写操作。',
    icon: StopCircle,
    risk: 'write',
    fields: [],
  },
]

export function taskKind(value: TaskType): TaskKind {
  return TASK_CATALOG.find((k) => k.value === value) ?? TASK_CATALOG[0]
}

export interface CronPreset {
  value: string
  label: string
  example: string
}

export const CRON_PRESETS: CronPreset[] = [
  { value: '', label: '自定义…', example: '* * * * *' },
  { value: '0 8 * * *', label: '每天 08:00', example: '0 8 * * *' },
  { value: '30 8 * * *', label: '每天 08:30', example: '30 8 * * *' },
  { value: '0 12 * * *', label: '每天 12:00', example: '0 12 * * *' },
  { value: '0 22 * * *', label: '每天 22:00', example: '0 22 * * *' },
  { value: '0 8 * * 1-5', label: '工作日 08:00', example: '0 8 * * 1-5' },
  { value: '*/5 * * * *', label: '每 5 分钟', example: '*/5 * * * *' },
]

export function formatTimeMinutes(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

export function parseTimeLabel(label: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(label.trim())
  if (!match) return null
  const h = Number(match[1])
  const m = Number(match[2])
  if (h < 0 || h > 23 || m < 0 || m > 59) return null
  return h * 60 + m
}
