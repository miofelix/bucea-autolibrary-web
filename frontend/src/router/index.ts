import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: '仪表盘' },
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('@/views/UsersView.vue'),
    meta: { title: '账号管理' },
  },
  {
    path: '/library',
    name: 'library-console',
    component: () => import('@/views/LibraryConsoleView.vue'),
    meta: { title: '账号会话' },
  },
  {
    path: '/seats',
    name: 'seats',
    component: () => import('@/views/SeatSearchView.vue'),
    meta: { title: '座位查询' },
  },
  {
    path: '/reservations',
    name: 'reservations',
    component: () => import('@/views/MyReservationsView.vue'),
    meta: { title: '我的预约' },
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: () => import('@/views/TasksView.vue'),
    meta: { title: '任务管理' },
  },
  {
    path: '/jobs',
    name: 'jobs',
    component: () => import('@/views/JobsView.vue'),
    meta: { title: '运行历史' },
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('@/views/LogsView.vue'),
    meta: { title: '实时日志' },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '系统设置' },
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title ?? '控制台')} - AutoLibrary`
})

export default router
