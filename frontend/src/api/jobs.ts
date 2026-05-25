import { apiRequest } from './client'

import type { TaskType } from './tasks'

export type JobStatus =
  | 'pending'
  | 'running'
  | 'success'
  | 'partial_success'
  | 'failed'
  | 'cancelled'
  | 'blocked_need_user_confirmation'

export type JobRecord = {
  id: number
  task_id: number | null
  task_type: TaskType
  library_user_id: number
  status: JobStatus
  summary: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export type RunJobPayload =
  | { task_id: number }
  | {
      task_id?: undefined
      task_type: TaskType
      library_user_id: number
      payload?: Record<string, unknown>
    }

export function listJobs() {
  return apiRequest<JobRecord[]>('/api/jobs')
}

export function runJob(payload: RunJobPayload) {
  return apiRequest<JobRecord>('/api/jobs/run', { method: 'POST', body: payload })
}

export function getJob(id: number) {
  return apiRequest<JobRecord>(`/api/jobs/${id}`)
}
