import { defineStore } from 'pinia'

import {
  createUser,
  deleteUser,
  listUsers,
  updateUser,
  type CreateLibraryUserPayload,
  type LibraryUser,
  type UpdateLibraryUserPayload,
} from '@/api/users'

const DEFAULT_USER_KEY = 'autolibrary:default-user-id'

function readDefaultUserId(): number | null {
  if (typeof localStorage === 'undefined') return null
  const raw = localStorage.getItem(DEFAULT_USER_KEY)
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function writeDefaultUserId(value: number | null): void {
  if (typeof localStorage === 'undefined') return
  if (value === null) {
    localStorage.removeItem(DEFAULT_USER_KEY)
  } else {
    localStorage.setItem(DEFAULT_USER_KEY, String(value))
  }
}

interface UsersState {
  items: LibraryUser[]
  loading: boolean
  saving: boolean
  error: string | null
  defaultUserId: number | null
}

export const useUsersStore = defineStore('users', {
  state: (): UsersState => ({
    items: [],
    loading: false,
    saving: false,
    error: null,
    defaultUserId: readDefaultUserId(),
  }),
  getters: {
    enabledCount: (state): number => state.items.filter((user) => user.enabled).length,
    defaultUser(state): LibraryUser | null {
      if (state.defaultUserId === null) return null
      return state.items.find((u) => u.id === state.defaultUserId) ?? null
    },
  },
  actions: {
    async fetchUsers(): Promise<void> {
      this.loading = true
      this.error = null
      try {
        this.items = await listUsers()
        if (
          this.defaultUserId !== null &&
          !this.items.some((u) => u.id === this.defaultUserId)
        ) {
          this.setDefaultUser(null)
        }
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载账号失败'
      } finally {
        this.loading = false
      }
    },
    async create(payload: CreateLibraryUserPayload): Promise<void> {
      this.saving = true
      this.error = null
      try {
        const created = await createUser(payload)
        this.items.unshift(created)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '保存账号失败'
        throw error
      } finally {
        this.saving = false
      }
    },
    async update(id: number, payload: UpdateLibraryUserPayload): Promise<void> {
      this.saving = true
      this.error = null
      try {
        const updated = await updateUser(id, payload)
        this.items = this.items.map((item) => (item.id === id ? updated : item))
      } catch (error) {
        this.error = error instanceof Error ? error.message : '更新账号失败'
        throw error
      } finally {
        this.saving = false
      }
    },
    async remove(id: number): Promise<void> {
      this.saving = true
      this.error = null
      try {
        await deleteUser(id)
        this.items = this.items.filter((item) => item.id !== id)
        if (this.defaultUserId === id) {
          this.setDefaultUser(null)
        }
      } catch (error) {
        this.error = error instanceof Error ? error.message : '删除账号失败'
        throw error
      } finally {
        this.saving = false
      }
    },
    setDefaultUser(id: number | null): void {
      this.defaultUserId = id
      writeDefaultUserId(id)
    },
  },
})
