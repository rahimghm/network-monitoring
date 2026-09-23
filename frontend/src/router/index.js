import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated, getRole } from '../api.js'

import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import HistoryView from '../views/HistoryView.vue'
import ThresholdsView from '../views/ThresholdsView.vue'
import GrafanaView from '../views/GrafanaView.vue'

const routes = [
  { path: '/login', component: LoginView, meta: { public: true } },
  { path: '/', component: DashboardView, meta: { roles: ['admin', 'technician', 'supervisor'] } },
  { path: '/history', component: HistoryView, meta: { roles: ['admin', 'technician', 'supervisor'] } },
  { path: '/thresholds', component: ThresholdsView, meta: { roles: ['admin'] } },
  { path: '/grafana', component: GrafanaView, meta: { roles: ['admin', 'technician', 'supervisor'] } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.public) return true

  if (!isAuthenticated()) {
    return { path: '/login' }
  }

  const role = getRole()
  const allowedRoles = to.meta.roles || []
  if (allowedRoles.length && !allowedRoles.includes(role)) {
    return { path: '/' }  // rôle non autorisé pour cette page -> retour au dashboard
  }

  return true
})

export default router
