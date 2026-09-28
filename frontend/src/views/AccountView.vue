<script setup>
import { ref } from 'vue'
import { changePassword } from '../api.js'
import { pushToast } from '../toasts.js'

const form = ref({ current_password: '', new_password: '', confirmation: '' })
const saving = ref(false)

async function submit() {
  if (form.value.new_password !== form.value.confirmation) {
    pushToast('Les nouveaux mots de passe ne correspondent pas.', 'alert')
    return
  }
  saving.value = true
  try {
    await changePassword({ current_password: form.value.current_password, new_password: form.value.new_password })
    form.value = { current_password: '', new_password: '', confirmation: '' }
    pushToast('Mot de passe modifié.', 'success')
  } catch (error) {
    pushToast(error.response?.data?.detail || 'Impossible de modifier le mot de passe.', 'alert')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="account-page ui-page">
    <div class="heading ui-heading">
      <p class="eyebrow ui-eyebrow">Compte personnel</p>
      <h2 class="ui-title">Modifier mon mot de passe</h2>
    </div>
    <form class="password-panel ui-panel" @submit.prevent="submit">
      <label>Mot de passe actuel
        <input class="ui-field" v-model="form.current_password" type="password" required autocomplete="current-password" />
      </label>
      <label>Nouveau mot de passe
        <input class="ui-field" v-model="form.new_password" type="password" required minlength="6" autocomplete="new-password" />
      </label>
      <label>Confirmer le nouveau mot de passe
        <input class="ui-field" v-model="form.confirmation" type="password" required minlength="6" autocomplete="new-password" />
      </label>
      <button class="ui-btn ui-btn-primary" type="submit" :disabled="saving">{{ saving ? 'Enregistrement...' : 'Enregistrer' }}</button>
    </form>
  </div>
</template>

<style scoped>
.account-page { max-width: 560px; color: #1a1d23; }
.heading { margin-bottom: 20px; }
.eyebrow { margin: 0 0 4px; color: var(--brand-green); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
h2 { margin: 0; font-size: 22px; }
.password-panel { display: grid; gap: 14px; background: #fff; border: 1px solid #e2e5ea; border-radius: 10px; padding: 20px; }
label { display: grid; gap: 6px; color: #555; font-size: 13px; font-weight: 600; }
input { padding: 9px 10px; border: 1px solid #d5d9e0; border-radius: 6px; font: inherit; font-size: 14px; }
button { width: max-content; padding: 9px 14px; background: var(--brand-green); color: #fff; border: 0; border-radius: 6px; font-weight: 600; cursor: pointer; }
button:disabled { opacity: .6; cursor: not-allowed; }
</style>