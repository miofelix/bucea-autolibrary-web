export class ApiError extends Error {
  status: number
  data: unknown

  constructor(message: string, status: number, data: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

type ApiRequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const headers = new Headers()
  const init: RequestInit = {
    method: options.method ?? 'GET',
    credentials: 'include',
    headers,
    signal: options.signal,
  }

  if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json')
    init.body = JSON.stringify(options.body)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, init)
  const contentType = response.headers.get('content-type') ?? ''
  const data = response.status === 204
    ? null
    : contentType.includes('application/json')
      ? await response.json()
      : await response.text()

  if (!response.ok) {
    const message = extractErrorMessage(data) ?? `请求失败：${response.status}`
    throw new ApiError(message, response.status, data)
  }

  return data as T
}

function extractErrorMessage(data: unknown): string | null {
  if (typeof data !== 'object' || data === null) return null
  const obj = data as Record<string, unknown>
  if (obj.error && typeof obj.error === 'object') {
    const err = obj.error as Record<string, unknown>
    const msg = err.message
    if (typeof msg === 'string' && msg.length > 0) return msg
  }
  if (typeof obj.detail === 'string') return obj.detail
  if (Array.isArray(obj.detail)) {
    const first = obj.detail[0]
    if (first && typeof first === 'object' && 'msg' in first) {
      return String((first as { msg: unknown }).msg)
    }
  }
  if (typeof obj.message === 'string') return obj.message
  return null
}

export type HealthResponse = {
  status: string
}

export function getHealth() {
  return apiRequest<HealthResponse>('/api/health')
}
