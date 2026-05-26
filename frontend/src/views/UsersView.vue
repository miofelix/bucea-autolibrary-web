<template>
  <section class="content-grid two-columns align-start">
    <div class="panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Library Accounts</span>
          <h2>{{ editingUser ? '编辑账号' : '添加账号' }}</h2>
        </div>
      </div>
      <UserForm
        :saving="users.saving"
        :user="editingUser"
        @cancel="editingUser = null"
        @submit="saveUser"
      />
      <p v-if="users.error" class="notice danger">{{ users.error }}</p>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Encrypted Storage</span>
          <h2>账号列表</h2>
        </div>
        <button class="button muted" type="button" :disabled="users.loading" @click="users.fetchUsers">
          <RefreshCw :size="16" />
          刷新
        </button>
      </div>

      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>账号</th>
              <th>名称</th>
              <th>状态</th>
              <th>更新时间</th>
              <th class="actions-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="users.loading">
              <td colspan="5">加载中</td>
            </tr>
            <tr v-else-if="users.items.length === 0">
              <td colspan="5">暂无账号</td>
            </tr>
            <template v-else>
              <tr v-for="item in users.items" :key="item.id">
                <td data-label="账号">{{ item.username }}</td>
                <td data-label="名称">{{ item.display_name || '-' }}</td>
                <td data-label="状态">
                  <span class="tag" :class="item.enabled ? 'enabled' : 'disabled'">
                    {{ item.enabled ? '启用' : '停用' }}
                  </span>
                </td>
                <td data-label="更新时间">{{ formatTime(item.updated_at) }}</td>
                <td data-label="操作">
                  <div class="row-actions">
                    <button class="icon-button" type="button" title="编辑" @click="editingUser = item">
                      <Pencil :size="16" />
                    </button>
                    <button class="icon-button danger" type="button" title="删除" @click="removeUser(item.id)">
                      <Trash2 :size="16" />
                    </button>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Pencil, RefreshCw, Trash2 } from '@lucide/vue'

import UserForm from '@/components/UserForm.vue'
import type { CreateLibraryUserPayload, LibraryUser, UpdateLibraryUserPayload } from '@/api/users'
import { useUsersStore } from '@/stores/users'

const users = useUsersStore()
const editingUser = ref<LibraryUser | null>(null)

onMounted(() => {
  void users.fetchUsers()
})

async function saveUser(payload: CreateLibraryUserPayload | UpdateLibraryUserPayload) {
  if (editingUser.value) {
    await users.update(editingUser.value.id, payload)
    editingUser.value = null
    return
  }
  await users.create(payload as CreateLibraryUserPayload)
}

async function removeUser(id: number) {
  if (!window.confirm('确认删除该账号？')) return
  await users.remove(id)
  if (editingUser.value?.id === id) {
    editingUser.value = null
  }
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
</script>
