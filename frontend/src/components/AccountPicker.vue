<template>
  <div class="account-picker">
    <label class="field inline-picker">
      <span>图书馆账号</span>
      <select :value="modelValue ?? ''" @change="onChange">
        <option value="">— 选择账号 —</option>
        <option v-for="user in users.items" :key="user.id" :value="String(user.id)">
          {{ user.username }}{{ user.display_name ? ` · ${user.display_name}` : '' }}
          {{ user.id === users.defaultUserId ? ' ★' : '' }}
        </option>
      </select>
    </label>

    <button
      class="icon-button pin-toggle"
      type="button"
      :disabled="modelValue === null"
      :title="isDefault ? '取消设为默认账号' : '设为默认账号'"
      :aria-pressed="isDefault"
      @click="togglePin"
    >
      <Pin v-if="!isDefault" :size="14" />
      <PinOff v-else :size="14" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { Pin, PinOff } from '@lucide/vue'

import { useUsersStore } from '@/stores/users'

interface Props {
  modelValue: number | null
  autoApplyDefault?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  autoApplyDefault: true,
})

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
}>()

const users = useUsersStore()

const isDefault = computed(
  () => props.modelValue !== null && props.modelValue === users.defaultUserId,
)

onMounted(async () => {
  if (users.items.length === 0) {
    await users.fetchUsers()
  }
  if (
    props.autoApplyDefault &&
    props.modelValue === null &&
    users.defaultUserId !== null
  ) {
    emit('update:modelValue', users.defaultUserId)
  }
})

watch(
  () => users.defaultUserId,
  (next) => {
    if (props.autoApplyDefault && props.modelValue === null && next !== null) {
      emit('update:modelValue', next)
    }
  },
)

function onChange(event: Event): void {
  const target = event.target as HTMLSelectElement
  const raw = target.value
  emit('update:modelValue', raw ? Number(raw) : null)
}

function togglePin(): void {
  if (props.modelValue === null) return
  users.setDefaultUser(isDefault.value ? null : props.modelValue)
}
</script>

<style scoped>
.account-picker {
  display: inline-flex;
  align-items: end;
  gap: 8px;
  width: 100%;
  max-width: 360px;
}

.inline-picker {
  flex: 1;
  min-width: 0;
}

.inline-picker select {
  width: 100%;
}

.pin-toggle {
  width: 36px;
  min-width: 36px;
  height: 36px;
  margin-bottom: 2px;
  align-self: end;
}

.pin-toggle[aria-pressed='true'] {
  color: var(--primary-strong);
  border-color: #b7dfd7;
  background: #eaf7f4;
}

@media (max-width: 900px) {
  .account-picker {
    max-width: 100%;
  }

  .pin-toggle {
    width: 44px;
    min-width: 44px;
    height: 44px;
    margin-bottom: 0;
  }
}
</style>
