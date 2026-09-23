<script setup>
import { ref } from 'vue'

function isExternalUrl(value) {
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) && url.origin !== window.location.origin
  } catch {
    return false
  }
}

const savedUrl = localStorage.getItem('grafana_dashboard_url') || ''
const grafanaUrl = ref(isExternalUrl(savedUrl) ? savedUrl : '')
const error = ref(null)

function save() {
  const value = grafanaUrl.value.trim()
  if (!isExternalUrl(value)) {
    error.value = "Saisis une URL Grafana externe, par exemple http://localhost:3000/..."
    grafanaUrl.value = ''
    localStorage.removeItem('grafana_dashboard_url')
    return
  }

  error.value = null
  grafanaUrl.value = value
  localStorage.setItem('grafana_dashboard_url', grafanaUrl.value)
}
</script>

<template>
  <div class="grafana-page">
    <div class="setup-card">
      <h2>Dashboards Grafana</h2>
      <p class="hint">
        Grafana tourne en dehors de cette app (auto-hébergé, connecté directement à ta base
        PostgreSQL existante). Colle ici l'URL d'un dashboard en mode "embed" pour l'afficher
        ci-dessous. Voir le README (section Grafana) pour l'installation complète.
      </p>
      <div class="row">
        <input
          v-model="grafanaUrl"
          type="text"
          placeholder="http://localhost:3000/d/xxxx/comparaison-cpu?orgId=1&kiosk"
        />
        <button @click="save">Enregistrer</button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div v-if="grafanaUrl" class="embed-wrapper">
      <iframe :src="grafanaUrl" frameborder="0" class="embed-frame"></iframe>
    </div>
    <p v-else class="placeholder">
      Aucun dashboard configuré pour l'instant.
    </p>
  </div>
</template>

<style scoped>
.setup-card {
  background: #fff;
  border: 1px solid #e2e5ea;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
}
h2 { font-size: 15px; margin: 0 0 8px; color: #1a1d23; }
.hint { font-size: 13px; color: #666; margin: 0 0 12px; }
.row { display: flex; gap: 8px; }
input {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid #d5d9e0;
  border-radius: 6px;
  font-size: 13px;
}
button {
  padding: 8px 16px;
  background: #3b6fed;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.embed-wrapper {
  background: #fff;
  border: 1px solid #e2e5ea;
  border-radius: 10px;
  overflow: hidden;
  height: 70vh;
}
.embed-frame { width: 100%; height: 100%; border: none; }
.placeholder { color: #888; font-size: 14px; text-align: center; padding: 40px 0; }
.error { color: #d1453b; font-size: 13px; margin: 8px 0 0; }
</style>
