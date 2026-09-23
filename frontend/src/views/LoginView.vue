<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login, registerFirstAdmin } from '../api.js'

const router = useRouter()
const mode = ref('login')  // 'login' | 'register'
const username = ref('')
const password = ref('')
const error = ref(null)
const loading = ref(false)

async function submit() {
  error.value = null
  loading.value = true
  try {
    if (mode.value === 'login') {
      await login(username.value, password.value)
    } else {
      await registerFirstAdmin({ username: username.value, password: password.value, role: 'admin' })
      await login(username.value, password.value)
    }
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || "Échec de l'authentification."
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <form class="login-card" @submit.prevent="submit">
      <h1>Monitoring Réseau</h1>
      <p class="subtitle">
        {{ mode === 'login' ? 'Connexion' : 'Créer le premier compte (Admin)' }}
      </p>

      <div class="field">
        <label>Nom d'utilisateur</label>
        <input v-model="username" type="text" required />
      </div>
      <div class="field">
        <label>Mot de passe</label>
        <input v-model="password" type="password" required minlength="6" />
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <button type="submit" :disabled="loading">
        {{ loading ? '...' : (mode === 'login' ? 'Se connecter' : 'Créer le compte') }}
      </button>

      <button type="button" class="link-btn" @click="mode = mode === 'login' ? 'register' : 'login'">
        {{ mode === 'login' ? "Premier lancement ? Créer le compte admin" : "Retour à la connexion" }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f2f3f6;
}
.login-card {
  background: #fff;
  border: 1px solid #e2e5ea;
  border-radius: 12px;
  padding: 32px;
  width: 320px;
}
h1 { font-size: 18px; margin: 0 0 4px; color: #1a1d23; }
.subtitle { font-size: 13px; color: #888; margin: 0 0 20px; }
.field { margin-bottom: 14px; display: flex; flex-direction: column; gap: 4px; }
label { font-size: 13px; color: #555; font-weight: 600; }
input {
  padding: 8px 10px;
  border: 1px solid #d5d9e0;
  border-radius: 6px;
  font-size: 14px;
}
input:focus { outline: none; border-color: #3b6fed; }
button[type="submit"] {
  width: 100%;
  padding: 9px;
  background: #3b6fed;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  font-size: 14px;
  margin-top: 6px;
}
button:disabled { opacity: 0.6; cursor: not-allowed; }
.link-btn {
  width: 100%;
  background: none;
  border: none;
  color: #3b6fed;
  font-size: 12px;
  cursor: pointer;
  margin-top: 10px;
}
.error { color: #d1453b; font-size: 13px; margin: 4px 0; }
</style>
