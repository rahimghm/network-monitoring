<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAuthStatus, login, registerFirstAdmin } from '../api.js'
import logoUrl from '../photos/Sonatrach.svg'

const router = useRouter()
const mode = ref('login')  // 'login' | 'register'
const canRegister = ref(false)
const username = ref('')
const password = ref('')
const error = ref(null)
const loading = ref(false)

onMounted(async () => {
  try {
    const status = await getAuthStatus()
    canRegister.value = status.admin_exists === false
  } catch (e) {
    canRegister.value = false
  }
})

function toggleMode() {
  if (!canRegister.value) return
  mode.value = mode.value === 'login' ? 'register' : 'login'
}

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
      <div class="login-brand">
        <img :src="logoUrl" alt="Sonatrach" />
        <div><strong>Sonatrach</strong><span>Network Operations</span></div>
      </div>
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

      <button class="ui-btn ui-btn-primary" type="submit" :disabled="loading">
        {{ loading ? '...' : (mode === 'login' ? 'Se connecter' : 'Créer le compte') }}
      </button>

      <button v-if="canRegister" type="button" class="link-btn" @click="toggleMode">
        {{ mode === 'login' ? 'Créer le compte administrateur' : 'Retour à la connexion' }}
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
  position: relative;
  padding: 28px 16px;
  background-image: linear-gradient(90deg, rgba(3, 52, 28, .82), rgba(0, 86, 45, .38)), url('../photos/SON00597.jpg');
  background-position: center;
  background-size: cover;
}
.login-card {
  position: relative;
  width: min(410px, 100%);
  padding: 34px;
  background: rgba(255, 255, 255, .96);
  border: 1px solid rgba(255, 255, 255, .72);
  border-top: 5px solid #d52b1e;
  border-radius: 14px;
  box-shadow: 0 24px 70px rgba(0, 35, 18, .3);
  backdrop-filter: blur(8px);
}
.login-brand { display: flex; align-items: center; gap: 10px; margin-bottom: 24px; }
.login-brand img { width: 38px; height: 48px; object-fit: contain; }
.login-brand div { display: grid; gap: 2px; }
.login-brand strong { color: #005b2e; font-size: 17px; }
.login-brand span { color: #69756e; font-size: 9px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
h1 { font-size: 24px; margin: 0 0 4px; color: #14231b; letter-spacing: -.02em; }
.subtitle { font-size: 13px; color: #68746c; margin: 0 0 24px; }
.field { margin-bottom: 14px; display: flex; flex-direction: column; gap: 4px; }
label { font-size: 13px; color: #555; font-weight: 600; }
input {
  padding: 8px 10px;
  border: 1px solid #cfdcd3;
  border-radius: 6px;
  font-size: 14px;
}
input:focus { outline: none; border-color: #007a3d; box-shadow: 0 0 0 3px rgba(0, 122, 61, .12); }
button[type="submit"] {
  width: 100%;
  padding: 9px;
  background: #007a3d;
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
  color: #007a3d;
  font-size: 12px;
  cursor: pointer;
  margin-top: 10px;
}
.error { color: #d1453b; font-size: 13px; margin: 4px 0; }
@media (max-width: 420px) {
  .login-card { padding: 26px 20px; }
}
</style>
