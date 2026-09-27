<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authState, logout } from './api.js'
import ToastStack from './components/ToastStack.vue'
import logoUrl from './photos/Sonatrach.svg'

const route = useRoute()
const router = useRouter()

const authed = computed(() => !!authState.token)
const role = computed(() => authState.role)
const username = computed(() => authState.username)

async function handleLogout() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <div class="app">
    <ToastStack />

    <template v-if="authed && route.path !== '/login'">
      <header class="app-header">
        <div class="header-inner">
          <router-link to="/" class="brand" aria-label="Accueil Monitoring Réseau">
            <span class="brand-mark"><img :src="logoUrl" alt="Sonatrach" /></span>
            <span class="brand-copy">
              <strong>Sonatrach</strong>
              <small>Network Operations</small>
            </span>
          </router-link>
          <nav>
            <router-link to="/">Dashboard</router-link>
            <router-link to="/history">Historique</router-link>
            <router-link v-if="role === 'admin' || role === 'supervisor' || role === 'technician'" to="/thresholds">Alertes</router-link>
            <router-link v-if="role === 'admin'" to="/users">Comptes</router-link>
            <router-link v-if="role === 'admin'" to="/audit-logs">Journal</router-link>
            <router-link to="/account">Mon compte</router-link>
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
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
:root {
  --brand-green: #007a3d;
  --brand-green-dark: #005b2e;
  --brand-green-soft: #e5f3eb;
  --brand-red: #d52b1e;
  --brand-yellow: #f4c542;
  --ink: #14231b;
  --muted: #66736b;
  --line: #dce7e0;
  --canvas: #f3f7f4;
  --surface: #ffffff;
  --shadow: 0 12px 30px rgba(24, 72, 45, .08);
}
* { box-sizing: border-box; }
html, body, #app { min-height: 100%; }
body {
  margin: 0;
  background: var(--canvas);
  color: var(--ink);
  font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
  font-size: 14px;
}
button, input, select { font-family: inherit; }
button { transition: background .18s ease, border-color .18s ease, color .18s ease, transform .18s ease; }
button:not(:disabled):hover { transform: translateY(-1px); }
</style>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(255, 255, 255, .96);
  border-bottom: 1px solid var(--line);
  box-shadow: 0 4px 18px rgba(24, 72, 45, .05);
}
.app-header::before { content: ''; display: block; height: 3px; background: linear-gradient(90deg, var(--brand-green) 0 72%, var(--brand-yellow) 72% 86%, var(--brand-red) 86%); }
.header-inner {
  width: min(1500px, 100%);
  margin: 0 auto;
  padding: 10px 24px;
  display: flex;
  align-items: center;
  gap: 22px;
}
.brand { display: flex; align-items: center; gap: 10px; color: var(--ink); text-decoration: none; flex-shrink: 0; }
.brand-mark { width: 40px; height: 40px; display: grid; place-items: center; overflow: hidden; }
.brand-mark img { width: 30px; height: 38px; object-fit: contain; }
.brand-copy { display: grid; gap: 1px; line-height: 1.05; }
.brand-copy strong { color: var(--brand-green-dark); font-size: 15px; letter-spacing: .02em; }
.brand-copy small { color: var(--muted); font-size: 9px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; }
nav { display: flex; align-items: center; gap: 5px; flex: 1; min-width: 0; }
nav a {
  font-size: 12px;
  color: var(--muted);
  text-decoration: none;
  font-weight: 600;
  padding: 8px 10px;
  border-radius: 6px;
  white-space: nowrap;
}
nav a:hover { color: var(--brand-green-dark); background: var(--brand-green-soft); }
nav a.router-link-exact-active { color: var(--brand-green-dark); background: var(--brand-green-soft); }
.user-info { display: flex; align-items: center; gap: 8px; margin-left: auto; flex-shrink: 0; }
.username { max-width: 120px; overflow: hidden; text-overflow: ellipsis; font-size: 12px; color: var(--ink); font-weight: 600; }
.role-badge {
  font-size: 11px;
  background: var(--brand-green-soft);
  color: var(--brand-green-dark);
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: capitalize;
}
.logout-btn {
  padding: 5px 10px;
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  color: var(--muted);
}
.logout-btn:hover { border-color: var(--brand-green); color: var(--brand-green-dark); }
.main-content {
  width: min(1500px, 100%);
  margin: 0 auto;
  padding: 26px 24px 42px;
}
@media (max-width: 980px) {
  .header-inner { flex-wrap: wrap; gap: 8px 14px; }
  nav { order: 3; flex-basis: 100%; overflow-x: auto; padding-bottom: 2px; }
  .user-info { margin-left: auto; }
}
@media (max-width: 560px) {
  .header-inner { padding: 9px 14px; }
  .brand-copy small { display: none; }
  .user-info .username { display: none; }
  .main-content { padding: 18px 12px 30px; }
  nav a { padding: 7px 8px; font-size: 11px; }
}
</style>
