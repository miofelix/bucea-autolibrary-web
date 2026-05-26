<template>
  <div class="app-shell" :class="{ 'drawer-open': drawerOpen }">
    <header class="mobile-topbar">
      <button
        class="hamburger"
        type="button"
        :aria-expanded="drawerOpen"
        aria-label="切换导航菜单"
        aria-controls="sidebar-nav"
        @click="toggleDrawer"
      >
        <component :is="drawerOpen ? X : Menu" :size="22" />
      </button>
      <RouterLink class="brand mobile-brand" to="/dashboard" @click="closeDrawer">
        <Library :size="22" />
        <span>AutoLibrary</span>
      </RouterLink>
      <span class="status-pill subtle">
        <ShieldCheck :size="14" />
        HTTP-only
      </span>
    </header>

    <aside
      id="sidebar-nav"
      class="sidebar"
      :class="{ open: drawerOpen }"
      :aria-hidden="isMobile && !drawerOpen ? 'true' : 'false'"
    >
      <RouterLink class="brand sidebar-brand" to="/dashboard" @click="closeDrawer">
        <Library :size="26" />
        <span>AutoLibrary</span>
      </RouterLink>
      <nav class="nav-list">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          class="nav-item"
          :to="item.to"
          @click="closeDrawer"
        >
          <component :is="item.icon" :size="18" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>

    <div
      v-if="drawerOpen"
      class="sidebar-backdrop"
      aria-hidden="true"
      @click="closeDrawer"
    ></div>

    <main class="workspace">
      <header class="topbar">
        <div class="topbar-title">
          <span class="eyebrow">Web 管理面板</span>
          <h1>{{ pageTitle }}</h1>
        </div>
        <div class="topbar-actions">
          <span class="status-pill">
            <ShieldCheck :size="15" />
            HTTP-only
          </span>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  CalendarClock,
  CalendarRange,
  ClipboardList,
  History,
  KeyRound,
  Library,
  ListChecks,
  Menu,
  ScrollText,
  Settings,
  ShieldCheck,
  Users,
  X,
} from '@lucide/vue'

const route = useRoute()

const navItems = [
  { to: '/dashboard', label: '仪表盘', icon: ClipboardList },
  { to: '/users', label: '账号管理', icon: Users },
  { to: '/library', label: '账号会话', icon: KeyRound },
  { to: '/seats', label: '座位查询', icon: ListChecks },
  { to: '/reservations', label: '我的预约', icon: CalendarRange },
  { to: '/tasks', label: '任务管理', icon: CalendarClock },
  { to: '/jobs', label: '运行历史', icon: History },
  { to: '/logs', label: '实时日志', icon: ScrollText },
  { to: '/settings', label: '系统设置', icon: Settings },
]

const pageTitle = computed(() => String(route.meta.title ?? '控制台'))

const MOBILE_QUERY = '(max-width: 900px)'
const drawerOpen = ref(false)
const isMobile = ref(false)
let mediaQuery: MediaQueryList | null = null

function syncMobileState(event: MediaQueryList | MediaQueryListEvent): void {
  isMobile.value = event.matches
  if (!event.matches) {
    drawerOpen.value = false
  }
}

function toggleDrawer(): void {
  drawerOpen.value = !drawerOpen.value
}

function closeDrawer(): void {
  if (drawerOpen.value) drawerOpen.value = false
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') closeDrawer()
}

watch(
  () => route.fullPath,
  () => {
    closeDrawer()
  },
)

watch(drawerOpen, (open) => {
  if (typeof document === 'undefined') return
  document.body.classList.toggle('no-scroll', open)
})

onMounted(() => {
  if (typeof window === 'undefined') return
  mediaQuery = window.matchMedia(MOBILE_QUERY)
  syncMobileState(mediaQuery)
  mediaQuery.addEventListener('change', syncMobileState)
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  if (mediaQuery) mediaQuery.removeEventListener('change', syncMobileState)
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', handleKeydown)
  }
  if (typeof document !== 'undefined') {
    document.body.classList.remove('no-scroll')
  }
})
</script>
