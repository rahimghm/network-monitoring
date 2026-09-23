<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isAuthenticated, getRole, logout } from './api.js'
import ToastStack from './components/ToastStack.vue'

const route = useRoute()
const router = useRouter()

const authed = computed(() => isAuthenticated())
const role = computed(() => getRole())
const username = computed(() => localStorage.getItem('auth_username'))

function handleLogout() {
  logout()
  router.push('/login')
}
</script>

<template>
  <div class="app">
    <ToastStack />

    <template v-if="authed && route.path !== '/login'">
      <header>
        <div class="header-inner">
          <h1>Monitoring Réseau</h1>
          <nav>
            <router-link to="/">Dashboard</router-link>
            <router-link to="/history">Historique</router-link>
            <router-link v-if="role === 'admin'" to="/thresholds">Alertes</router-link>
            <router-link to="/grafana">Grafana</router-link>
          </nav>
          <div class="user-info">
            <span class="username">{{ username }}</span>
            <span class="role-badge">{{ role }}</span>
            <button class="logout-btn" @click="handleLogout">Déconnexion</button>
          </div>
        </div>
      </header>

      <main class="main-content">
        <router-view />
      </main>
    </template>

    <template v-else>
      <router-view />
    </template>
  </div>
</template>

<style>
* { box-sizing: border-box; }
body {
  margin: 0;
  background: #f2f3f6;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
</style>

<style scoped>
header {
  background: #fff;
  border-bottom: 1px solid #e2e5ea;
}
.header-inner {
  max-width: 1500px;
  margin: 0 auto;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  gap: 24px;
}
h1 { font-size: 16px; color: #1a1d23; margin: 0; white-space: nowrap; }
nav { display: flex; gap: 16px; flex: 1; }
nav a {
  font-size: 13px;
  color: #666;
  text-decoration: none;
  font-weight: 600;
  padding: 4px 0;
}
nav a.router-link-exact-active { color: #3b6fed; border-bottom: 2px solid #3b6fed; }
.user-info { display: flex; align-items: center; gap: 8px; }
.username { font-size: 13px; color: #1a1d23; font-weight: 600; }
.role-badge {
  font-size: 11px;
  background: #eef2fe;
  color: #3b6fed;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: capitalize;
}
.logout-btn {
  padding: 5px 10px;
  background: transparent;
  border: 1px solid #e2e5ea;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  color: #666;
}
.main-content {
  max-width: 1500px;
  margin: 0 auto;
  padding: 24px;
}
</style>
