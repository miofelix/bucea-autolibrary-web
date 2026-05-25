<template>
  <div class="app-shell">
    <aside class="sidebar">
      <RouterLink class="brand" to="/dashboard">
        <Library :size="26" />
        <span>AutoLibrary</span>
      </RouterLink>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.to" class="nav-item" :to="item.to">
          <component :is="item.icon" :size="18" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div>
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
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  CalendarClock,
  CalendarRange,
  ClipboardList,
  History,
  KeyRound,
  Library,
  ListChecks,
  ScrollText,
  Settings,
  ShieldCheck,
  Users,
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
</script>
