<script setup>
import { ref, onMounted } from 'vue'
import { listSnapshots, getSnapshot, listEquipments, downloadSnapshot } from '../api.js'
import DiagnosticPanel from '../components/DiagnosticPanel.vue'
import { pushToast } from '../toasts.js'

const snapshots = ref([])
const equipments = ref([])
const filterEquipmentId = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')

const selectedSnapshot = ref(null)
const loading = ref(false)

async function loadEquipments() {
  equipments.value = await listEquipments()
}

async function loadSnapshots() {
  loading.value = true
  try {
    snapshots.value = await listSnapshots({
      equipment_id: filterEquipmentId.value || undefined,
      date_from: filterDateFrom.value || undefined,
      date_to: filterDateTo.value || undefined,
    })
  } finally {
    loading.value = false
  }
}

async function openSnapshot(s) {
  selectedSnapshot.value = await getSnapshot(s.id)
}

function equipmentName(id) {
  return equipments.value.find(e => e.id === id)?.name || `#${id}`
}

async function handleExport(format) {
  if (!selectedSnapshot.value) return
  try {
    await downloadSnapshot(selectedSnapshot.value.id, format)
  } catch (e) {
    pushToast("Échec de l'export.", 'alert')
  }
}

onMounted(async () => {
  await loadEquipments()
  await loadSnapshots()
})
</script>

<template>
  <div class="history-page">
    <div class="filters">
      <select v-model="filterEquipmentId" @change="loadSnapshots">
        <option value="">Tous les équipements</option>
        <option v-for="eq in equipments" :key="eq.id" :value="eq.id">{{ eq.name }}</option>
      </select>
      <input type="date" v-model="filterDateFrom" @change="loadSnapshots" />
      <input type="date" v-model="filterDateTo" @change="loadSnapshots" />
    </div>

    <div class="content">
      <div class="snapshot-list">
        <h2>Snapshots ({{ snapshots.length }})</h2>
        <p v-if="loading" class="empty">Chargement...</p>
        <p v-else-if="snapshots.length === 0" class="empty">Aucun snapshot pour ces filtres.</p>
        <div
          v-for="s in snapshots"
          :key="s.id"
          class="snapshot-row"
          :class="{ active: selectedSnapshot?.id === s.id }"
          @click="openSnapshot(s)"
        >
          <div class="label">{{ s.label }}</div>
          <div class="date">{{ new Date(s.created_at).toLocaleString('fr-FR') }}</div>
        </div>
      </div>

      <div class="snapshot-detail">
        <div v-if="!selectedSnapshot" class="placeholder">
          Sélectionne un snapshot pour voir le détail.
        </div>
        <template v-else>
          <div class="detail-header">
            <h2>{{ selectedSnapshot.label }}</h2>
            <div class="export-actions">
              <button @click="handleExport('pdf')">Export PDF</button>
              <button @click="handleExport('xlsx')">Export XLSX</button>
            </div>
          </div>

          <div v-for="d in selectedSnapshot.diagnostics" :key="d.id" class="equip-block">
            <h3>{{ equipmentName(d.equipment_id) }}</h3>
            <DiagnosticPanel :equipment="{ name: equipmentName(d.equipment_id), hostname: '' }" :diagnostic="d" />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.filters select, .filters input {
  padding: 7px 10px;
  border: 1px solid #d5d9e0;
  border-radius: 6px;
  font-size: 13px;
}
.content {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 20px;
  align-items: start;
}
.snapshot-list, .snapshot-detail {
  background: #fff;
  border: 1px solid #e2e5ea;
  border-radius: 10px;
  padding: 16px;
}
.snapshot-list h2, .detail-header h2 { font-size: 15px; margin: 0 0 10px; color: #1a1d23; }
.empty { color: #888; font-size: 13px; }
.snapshot-row {
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  border-bottom: 1px solid #f0f1f4;
}
.snapshot-row:hover, .snapshot-row.active { background: #eef2fe; }
.label { font-weight: 600; font-size: 13px; color: #1a1d23; }
.date { font-size: 11px; color: #888; }

.placeholder { color: #888; font-size: 14px; text-align: center; padding: 40px 0; }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.export-actions { display: flex; gap: 8px; }
.export-actions button {
  padding: 6px 12px;
  background: #eef2fe;
  color: #3b6fed;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}
.equip-block { border-top: 1px solid #f0f1f4; padding-top: 12px; margin-top: 12px; }
.equip-block h3 { font-size: 13px; color: #555; margin: 0 0 6px; }
</style>
