import { apiRequest } from './client'

export type LibraryUser = {
  id: number
  username: string
  display_name: string | null
  enabled: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

export type CreateLibraryUserPayload = {
  username: string
  password: string
  display_name?: string | null
  enabled: boolean
  notes?: string | null
}

export type UpdateLibraryUserPayload = {
  username?: string
  password?: string
  display_name?: string | null
  enabled?: boolean
  notes?: string | null
}

export function listUsers() {
  return apiRequest<LibraryUser[]>('/api/users')
}

export function createUser(payload: CreateLibraryUserPayload) {
  return apiRequest<LibraryUser>('/api/users', {
    method: 'POST',
    body: payload,
  })
}

export function updateUser(id: number, payload: UpdateLibraryUserPayload) {
  return apiRequest<LibraryUser>(`/api/users/${id}`, {
    method: 'PUT',
    body: payload,
  })
}

export function deleteUser(id: number) {
  return apiRequest<void>(`/api/users/${id}`, {
    method: 'DELETE',
  })
}
