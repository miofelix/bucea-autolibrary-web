import { apiRequest } from './client'

export type JobLogLevel = 'info' | 'warning' | 'error' | 'debug'

export type JobLogRecord = {
  id: number | null
  job_id?: number
  level: JobLogLevel
  message: string
  created_at: string
}

export function listLogs(jobId: number) {
  return apiRequest<JobLogRecord[]>(`/api/jobs/${jobId}/logs`)
}

export function logStreamUrl(jobId: number): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? ''
  return `${base}/api/jobs/${jobId}/logs/stream`
}
