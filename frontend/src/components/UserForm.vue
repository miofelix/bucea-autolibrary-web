<template>
  <form class="form-grid" @submit.prevent="submit">
    <label class="field">
      <span>图书馆账号</span>
      <input v-model.trim="form.username" autocomplete="username" required maxlength="128" />
    </label>

    <label class="field">
      <span>显示名称</span>
      <input v-model.trim="form.display_name" maxlength="128" placeholder="可选" />
    </label>

    <label class="field field-password">
      <span>{{ user ? '新密码' : '密码' }}</span>
      <div class="password-input">
        <input
          v-model="form.password"
          :required="!user"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="new-password"
          maxlength="256"
          placeholder="留空则不修改"
        />
        <button
          class="icon-button"
          type="button"
          :title="showPassword ? '隐藏密码' : '显示密码'"
          @click="showPassword = !showPassword"
        >
          <EyeOff v-if="showPassword" :size="16" />
          <Eye v-else :size="16" />
        </button>
      </div>
    </label>

    <label class="field">
      <span>备注</span>
      <input v-model.trim="form.notes" maxlength="512" placeholder="可选" />
    </label>

    <label class="switch-row">
      <input v-model="form.enabled" type="checkbox" />
      <span>启用账号</span>
    </label>

    <div class="form-actions">
      <button class="button primary" type="submit" :disabled="saving">
        <Save :size="16" />
        {{ user ? '保存' : '添加' }}
      </button>
      <button v-if="user" class="button muted" type="button" @click="$emit('cancel')">
        <X :size="16" />
        取消
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { Eye, EyeOff, Save, X } from '@lucide/vue'

import type { CreateLibraryUserPayload, LibraryUser, UpdateLibraryUserPayload } from '@/api/users'

const props = defineProps<{
  user?: LibraryUser | null
  saving?: boolean
}>()

const emit = defineEmits<{
  submit: [payload: CreateLibraryUserPayload | UpdateLibraryUserPayload]
  cancel: []
}>()

const showPassword = ref(false)

const form = reactive({
  username: '',
  display_name: '',
  password: '',
  enabled: true,
  notes: '',
})

watch(
  () => props.user,
  (user) => {
    form.username = user?.username ?? ''
    form.display_name = user?.display_name ?? ''
    form.password = ''
    form.enabled = user?.enabled ?? true
    form.notes = user?.notes ?? ''
    showPassword.value = false
  },
  { immediate: true },
)

function submit() {
  const base = {
    username: form.username,
    display_name: form.display_name || null,
    enabled: form.enabled,
    notes: form.notes || null,
  }

  if (props.user) {
    emit('submit', {
      ...base,
      ...(form.password ? { password: form.password } : {}),
    })
    return
  }

  emit('submit', {
    ...base,
    password: form.password,
  })

  form.username = ''
  form.display_name = ''
  form.password = ''
  form.enabled = true
  form.notes = ''
}
</script>
