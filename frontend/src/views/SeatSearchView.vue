<template>
  <section class="content-grid two-columns align-start">
    <div class="panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Seat Search</span>
          <h2>查询条件</h2>
        </div>
      </div>

      <form class="form-grid" @submit.prevent="search">
        <AccountPicker v-model="state.userId" />

        <label class="field">
          <span>日期</span>
          <input v-model="state.date" type="date" />
          <small class="hint">未选择则默认今日。</small>
        </label>

        <label class="field">
          <span>场馆 ID</span>
          <input v-model.trim="state.building" placeholder="1" maxlength="8" />
        </label>

        <label class="field">
          <span>阅览室</span>
          <select v-model="state.room" :disabled="rooms.length === 0">
            <option value="">— 不限 —</option>
            <option v-for="room in rooms" :key="room.room_id" :value="room.room_id">
              {{ room.name }} ({{ room.room_id }})
            </option>
          </select>
        </label>

        <div class="form-actions">
          <button class="button muted" type="button" :disabled="!canLoadRooms" @click="loadRooms">
            <RefreshCw :size="16" />
            加载阅览室
          </button>
          <button class="button primary" type="submit" :disabled="!state.userId">
            <Search :size="16" />
            搜索
          </button>
        </div>

        <p v-if="error" class="notice danger">{{ error }}</p>
      </form>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <span class="eyebrow">Results</span>
          <h2>座位结果</h2>
        </div>
        <span class="tag">{{ result?.seat_num ?? 0 }} 个</span>
      </div>

      <div v-if="!result || result.seats.length === 0" class="empty-state">
        <Search :size="24" />
        <strong>暂无结果</strong>
        <span>选择条件后点击搜索。</span>
      </div>

      <ul v-else class="seat-grid">
        <li
          v-for="seat in result.seats"
          :key="seat.seat_id"
          class="seat-card"
          :class="seat.status"
        >
          <strong>{{ seat.name }}</strong>
          <span>{{ seat.room_name ?? '-' }}</span>
          <span class="tag" :class="seat.status">{{ seat.status }}</span>
          <button
            class="button muted small"
            type="button"
            :disabled="seat.status !== 'free' || !state.userId"
            @click="openReservation(seat)"
          >
            预约
          </button>
        </li>
      </ul>
    </div>
  </section>

  <ReservationDialog
    v-if="reserving"
    :user-id="state.userId!"
    :seat="reserving"
    :date="state.date"
    @close="reserving = null"
    @reserved="onReserved"
  />
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { RefreshCw, Search } from '@lucide/vue'

import {
  fetchRooms,
  searchSeats,
  type Room,
  type SeatItem,
  type SearchResult,
} from '@/api/library'
import AccountPicker from '@/components/AccountPicker.vue'
import ReservationDialog from '@/components/ReservationDialog.vue'

const state = reactive({
  userId: null as number | null,
  date: '',
  building: '1',
  room: '',
})

const rooms = ref<Room[]>([])
const result = ref<SearchResult | null>(null)
const error = ref('')
const reserving = ref<SeatItem | null>(null)

const canLoadRooms = computed(() => !!state.userId && !!state.building)

watch(
  () => state.userId,
  () => {
    rooms.value = []
    result.value = null
    state.room = ''
  },
)

async function loadRooms(): Promise<void> {
  if (!state.userId || !state.building) return
  error.value = ''
  try {
    rooms.value = await fetchRooms(state.userId, state.building)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载阅览室失败'
  }
}

async function search(): Promise<void> {
  if (!state.userId) return
  error.value = ''
  try {
    result.value = await searchSeats(state.userId, {
      on_date: state.date || undefined,
      building: state.building || undefined,
      room: state.room || undefined,
      offset: 1,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : '查询失败'
  }
}

function openReservation(seat: SeatItem): void {
  reserving.value = seat
}

function onReserved(message: string): void {
  reserving.value = null
  error.value = message
}
</script>

<style scoped>
.seat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.seat-card {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel-muted);
}

.seat-card.free {
  border-color: #b7dfd7;
  background: #eaf7f4;
}

.seat-card.using {
  border-color: var(--border-strong);
  background: #f1f4f6;
  opacity: 0.7;
}

.button.small {
  min-height: 30px;
  padding: 0 10px;
  font-size: 0.82rem;
}
</style>
