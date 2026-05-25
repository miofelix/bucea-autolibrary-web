import { apiRequest } from './client'

export type TaskType =
  | 'reserve'
  | 'checkin'
  | 'renew'
  | 'cancel'
  | 'search'
  | 'stop_using'
  | 'leave'
  | 'resume'
export type TaskMode = 'manual' | 'scheduled'

export type TaskRecord = {
  id: number
  name: string
  task_type: TaskType
  mode: TaskMode
  enabled: boolean
  cron: string | null
  library_user_id: number
  payload: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type CreateTaskPayload = {
  name: string
  task_type: TaskType
  mode: TaskMode
  enabled: boolean
  cron?: string | null
  library_user_id: number
  payload?: Record<string, unknown> | null
}

export type UpdateTaskPayload = Partial<Omit<CreateTaskPayload, 'library_user_id'>>

export function listTasks() {
  return apiRequest<TaskRecord[]>('/api/tasks')
}

export function createTask(payload: CreateTaskPayload) {
  return apiRequest<TaskRecord>('/api/tasks', { method: 'POST', body: payload })
}

export function updateTask(id: number, payload: UpdateTaskPayload) {
  return apiRequest<TaskRecord>(`/api/tasks/${id}`, { method: 'PUT', body: payload })
}

export function deleteTask(id: number) {
  return apiRequest<void>(`/api/tasks/${id}`, { method: 'DELETE' })
}
