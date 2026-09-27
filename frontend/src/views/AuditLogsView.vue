<script setup>
import { onMounted, ref } from 'vue'
import { listAuditLogs } from '../api.js'
import { pushToast } from '../toasts.js'

const logs = ref([])
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    logs.value = await listAuditLogs()
  } catch (error) {
    pushToast(error.response?.data?.detail || 'Impossible de charger le journal.', 'alert')
  } finally {
    loading.value = false
  }
}

function formatDate(value) {
  return new Date(value).toLocaleString('fr-FR')
}

function formatDetails(details) {
  return details ? JSON.stringify(details) : ''
}

onMounted(refresh)
</script>

<template>
  <div class="logs-page">
    <div class="heading">
      <div>
        <p class="eyebrow">Administration</p>
        <h2>Journal des actions</h2>
      </div>
      <button class="refresh-btn" :disabled="loading" @click="refresh">Actualiser</button>
    </div>

    <div class="logs-panel">
      <p v-if="loading" class="empty">Chargement...</p>
      <p v-else-if="!logs.length" class="empty">Aucune action enregistrée.</p>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr><th>Date</th><th>Utilisateur</th><th>Rôle</th><th>Action</th><th>Ressource</th><th>Détails</th></tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id">
              <td>{{ formatDate(log.created_at) }}</td>
              <td>{{ log.username }}</td>
              <td>{{ log.role }}</td>
              <td>{{ log.action }}</td>
              <td>{{ log.resource || '-' }}{{ log.resource_id == null ? '' : ` #${log.resource_id}` }}</td>
              <td class="details">{{ formatDetails(log.details) }}</td>
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
.eyebrow { margin: 0 0 4px; color: #3b6fed; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
h2 { margin: 0; font-size: 22px; }
.refresh-btn { padding: 8px 12px; border: 0; border-radius: 6px; background: #3b6fed; color: #fff; font-weight: 600; cursor: pointer; }
.refresh-btn:disabled { opacity: .6; cursor: not-allowed; }
.logs-panel { overflow: hidden; background: #fff; border: 1px solid #e2e5ea; border-radius: 10px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; white-space: nowrap; }
th { padding: 10px; border-bottom: 1px solid #e2e5ea; color: #858b95; font-size: 11px; text-align: left; text-transform: uppercase; }
td { padding: 11px 10px; border-bottom: 1px solid #f0f1f4; }
.details { max-width: 360px; overflow: hidden; text-overflow: ellipsis; }
.empty { padding: 32px; color: #858b95; text-align: center; }
</style>
