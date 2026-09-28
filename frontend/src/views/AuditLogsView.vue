<script setup>
import { onMounted, ref } from 'vue'
import { listAuditLogs } from '../api.js'
import { pushToast } from '../toasts.js'

const logs = ref([])
const loading = ref(false)
const filters = ref({
  username: '',
  role: '',
  action: '',
  date_from: '',
  date_to: '',
})

const actions = [
  'auth.register',
  'auth.login',
  'auth.logout',
  'auth.change_password',
  'equipment.create',
  'equipment.update',
  'equipment.delete',
  'diagnostic.run',
  'monitoring.start',
  'monitoring.pause',
  'monitoring.resume',
  'monitoring.stop',
  'monitoring.snapshot',
  'threshold.create',
  'threshold.delete',
  'users.create',
  'users.update',
  'users.delete',
]

async function refresh() {
  loading.value = true
  try {
    const activeFilters = Object.fromEntries(
      Object.entries(filters.value).filter(([, value]) => value !== '')
    )
    logs.value = await listAuditLogs(activeFilters)
  } catch (error) {
    pushToast(error.response?.data?.detail || 'Impossible de charger le journal.', 'alert')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.value = { username: '', role: '', action: '', date_from: '', date_to: '' }
  refresh()
}

function formatDate(value) {
  return new Date(value).toLocaleString('fr-FR')
}

onMounted(refresh)
</script>

<template>
  <div class="logs-page ui-page">
    <div class="heading ui-heading">
      <div>
        <p class="eyebrow ui-eyebrow">Administration</p>
        <h2 class="ui-title">Journal des actions</h2>
      </div>
      <button class="refresh-btn ui-btn ui-btn-primary" :disabled="loading" @click="refresh">Actualiser</button>
    </div>

    <div class="logs-panel ui-panel">
      <form class="filters" @submit.prevent="refresh">
        <label>
          Utilisateur
          <input class="ui-field" v-model.trim="filters.username" type="search" placeholder="Nom d'utilisateur" />
        </label>
        <label>
          Rôle
          <select class="ui-field" v-model="filters.role">
            <option value="">Tous les rôles</option>
            <option value="admin">Admin</option>
            <option value="technician">Technicien</option>
            <option value="supervisor">Superviseur</option>
          </select>
        </label>
        <label>
          Action
          <select class="ui-field" v-model="filters.action">
            <option value="">Toutes les actions</option>
            <option v-for="action in actions" :key="action" :value="action">{{ action }}</option>
          </select>
        </label>
        <label>
          Du
          <input class="ui-field" v-model="filters.date_from" type="date" />
        </label>
        <label>
          Au
          <input class="ui-field" v-model="filters.date_to" type="date" />
        </label>
        <div class="filter-actions">
          <button class="apply-btn ui-btn ui-btn-primary" type="submit" :disabled="loading">Filtrer</button>
          <button class="reset-btn ui-btn ui-btn-quiet" type="button" :disabled="loading" @click="resetFilters">Réinitialiser</button>
        </div>
      </form>
      <p v-if="loading" class="empty">Chargement...</p>
      <p v-else-if="!logs.length" class="empty">Aucune action enregistrée.</p>
      <div v-else class="table-wrap ui-table-wrap">
        <table class="ui-table">
          <thead>
            <tr><th>Date</th><th>Utilisateur</th><th>Rôle</th><th>Action</th><th>Ressource</th></tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id">
              <td>{{ formatDate(log.created_at) }}</td>
              <td>{{ log.username }}</td>
              <td>{{ log.role }}</td>
              <td>{{ log.action }}</td>
              <td>{{ log.resource || '-' }}{{ log.resource_id == null ? '' : ` #${log.resource_id}` }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.logs-page { color: #1a1d23; }
.heading { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.eyebrow { margin: 0 0 4px; color: var(--brand-green); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
h2 { margin: 0; font-size: 22px; }
.refresh-btn { padding: 8px 12px; border: 0; border-radius: 6px; background: var(--brand-green); color: #fff; font-weight: 600; cursor: pointer; }
.refresh-btn:disabled { opacity: .6; cursor: not-allowed; }
.logs-panel { overflow: hidden; background: #fff; border: 1px solid #e2e5ea; border-radius: 10px; }
.filters { display: flex; align-items: end; flex-wrap: wrap; gap: 10px; padding: 14px; border-bottom: 1px solid #e2e5ea; background: #fafbfc; }
.filters label { display: grid; gap: 5px; color: #656d79; font-size: 11px; font-weight: 700; }
.filters input, .filters select { min-width: 145px; padding: 8px 9px; border: 1px solid #d5d9e0; border-radius: 6px; background: #fff; color: #1a1d23; font: inherit; font-size: 12px; }
.filter-actions { display: flex; gap: 6px; }
.apply-btn, .reset-btn { padding: 8px 11px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; }
.apply-btn { border: 0; background: var(--brand-green); color: #fff; }
.reset-btn { border: 1px solid #d5d9e0; background: #fff; color: #5f6671; }
.apply-btn:disabled, .reset-btn:disabled { opacity: .6; cursor: not-allowed; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; white-space: nowrap; }
th { padding: 10px; border-bottom: 1px solid #e2e5ea; color: #858b95; font-size: 11px; text-align: left; text-transform: uppercase; }
td { padding: 11px 10px; border-bottom: 1px solid #f0f1f4; }
.details { max-width: 360px; overflow: hidden; text-overflow: ellipsis; }
.empty { padding: 32px; color: #858b95; text-align: center; }
@media (max-width: 800px) {
  .heading { align-items: start; }
  .filters label, .filters input, .filters select { width: 100%; }
  .filters label { flex: 1 1 180px; }
  .filter-actions { width: 100%; }
}
</style>
