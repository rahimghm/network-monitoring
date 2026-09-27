<script setup>
import { ref, onMounted } from 'vue'
import { listSnapshots, getSnapshot, updateSnapshot, deleteSnapshot, listEquipments, downloadSnapshot, getRole } from '../api.js'
import DiagnosticPanel from '../components/DiagnosticPanel.vue'
import SnapshotChart from '../components/SnapshotChart.vue'
import { pushToast } from '../toasts.js'

const snapshots = ref([])
const equipments = ref([])
const filterEquipmentId = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')

const selectedSnapshot = ref(null)
const loading = ref(false)
const openMenuId = ref(null)
const editingSnapshotId = ref(null)
const editingLabel = ref('')
const canManageSnapshots = ['admin', 'supervisor'].includes(getRole())
const canDeleteSnapshots = ['admin', 'supervisor'].includes(getRole())

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

function equipmentById(id) {
  return equipments.value.find(e => e.id === id) || { name: `#${id}`, hostname: '' }
}

function metricsFor(id) {
  return selectedSnapshot.value?.metrics?.filter(point => point.equipment_id === id) || []
}

function resetFilters() {
  filterEquipmentId.value = ''
  filterDateFrom.value = ''
  filterDateTo.value = ''
  loadSnapshots()
}

function toggleSnapshotMenu(event, snapshotId) {
  event.stopPropagation()
  openMenuId.value = openMenuId.value === snapshotId ? null : snapshotId
}

function editSnapshot(snapshot) {
  editingSnapshotId.value = snapshot.id
  editingLabel.value = snapshot.label
  openMenuId.value = null
}

async function saveSnapshotLabel(snapshot) {
  const label = editingLabel.value.trim()
  if (!label) return
  try {
    const updated = await updateSnapshot(snapshot.id, { label })
    snapshot.label = updated.label
    if (selectedSnapshot.value?.id === snapshot.id) selectedSnapshot.value.label = updated.label
    editingSnapshotId.value = null
  } catch (error) {
    pushToast(error.response?.data?.detail || 'Impossible de modifier le snapshot.', 'alert')
  }
}

async function removeSnapshot(snapshot) {
  if (!window.confirm(`Supprimer le snapshot « ${snapshot.label} » ?`)) return
  try {
    await deleteSnapshot(snapshot.id)
    snapshots.value = snapshots.value.filter(item => item.id !== snapshot.id)
    if (selectedSnapshot.value?.id === snapshot.id) selectedSnapshot.value = null
    pushToast('Snapshot supprimé.', 'success')
  } catch (error) {
    pushToast(error.response?.data?.detail || 'Impossible de supprimer le snapshot.', 'alert')
  }
}

function exportFilename(format) {
  const label = selectedSnapshot.value?.label || 'snapshot'
  const safeLabel = label.replace(/[<>:"/\\|?*]+/g, '-').trim()
  return `snapshot ${safeLabel || 'snapshot'}.${format}`
}

async function handleExport(format) {
  if (!selectedSnapshot.value) return
  try {
    await downloadSnapshot(selectedSnapshot.value.id, format, exportFilename(format))
  } catch (e) {
    pushToast(e.response?.data?.detail || "Échec de l'export.", 'alert')
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
      <div class="filter-heading">
        <span class="filter-kicker">Historique</span>
        <strong>Filtrer les snapshots</strong>
      </div>
      <label>
        Équipement
        <select v-model="filterEquipmentId" @change="loadSnapshots">
          <option value="">Tous les équipements</option>
          <option v-for="eq in equipments" :key="eq.id" :value="eq.id">{{ eq.name }}</option>
        </select>
      </label>
      <label>
        Du
        <input type="date" v-model="filterDateFrom" @change="loadSnapshots" />
      </label>
      <label>
        Au
        <input type="date" v-model="filterDateTo" @change="loadSnapshots" />
      </label>
      <button class="reset-filter" type="button" @click="resetFilters">Réinitialiser</button>
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
          <div v-if="editingSnapshotId === s.id" class="edit-snapshot" @click.stop>
            <input v-model="editingLabel" @keyup.enter="saveSnapshotLabel(s)" />
            <button class="menu-save" @click="saveSnapshotLabel(s)">Enregistrer</button>
            <button class="menu-cancel" @click="editingSnapshotId = null">Annuler</button>
          </div>
          <div v-else class="snapshot-row-main">
            <div class="label">{{ s.label }}</div>
            <div v-if="canManageSnapshots" class="snapshot-menu" @click.stop>
              <button class="more-button" title="Actions" @click="toggleSnapshotMenu($event, s.id)">...</button>
              <div v-if="openMenuId === s.id" class="menu-actions">
                <button @click="editSnapshot(s)">Modifier</button>
                <button v-if="canDeleteSnapshots" class="danger-action" @click="removeSnapshot(s)">Supprimer</button>
              </div>
            </div>
          </div>
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
            <h3>{{ d.equipment_name || equipmentById(d.equipment_id).name }}</h3>
            <p class="equipment-hostname">{{ d.equipment_hostname || equipmentById(d.equipment_id).hostname }}</p>
            <DiagnosticPanel :equipment="{ name: d.equipment_name || equipmentById(d.equipment_id).name, hostname: d.equipment_hostname || equipmentById(d.equipment_id).hostname }" :diagnostic="d" />
            <SnapshotChart :points="metricsFor(d.equipment_id)" />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  align-items: end;
  flex-wrap: wrap;
  gap: 12px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e2e5ea;
  border-radius: 10px;
  margin-bottom: 16px;
}
.filter-heading { display: grid; gap: 3px; min-width: 180px; margin-right: auto; color: #1a1d23; font-size: 13px; }
.filter-kicker { color: var(--brand-green); font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.filters label { display: grid; gap: 5px; color: #656d79; font-size: 11px; font-weight: 700; }
.filters select, .filters input {
  min-width: 150px;
  padding: 7px 10px;
  border: 1px solid #d5d9e0;
  border-radius: 6px;
  font-size: 13px;
}
.reset-filter { padding: 8px 11px; border: 1px solid #d5d9e0; border-radius: 6px; background: #fff; color: #5f6671; font-size: 12px; font-weight: 600; cursor: pointer; }
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
.snapshot-row:hover, .snapshot-row.active { background: var(--brand-green-soft); }
.snapshot-row-main { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.label { font-weight: 600; font-size: 13px; color: #1a1d23; }
.date { font-size: 11px; color: #888; }
.snapshot-menu { position: relative; }
.more-button { padding: 1px 7px; border: 1px solid #d5d9e0; border-radius: 5px; background: #fff; color: #656d79; font-weight: 700; letter-spacing: 2px; cursor: pointer; }
.menu-actions { position: absolute; right: 0; top: 26px; z-index: 3; min-width: 110px; padding: 4px; background: #fff; border: 1px solid #e2e5ea; border-radius: 6px; box-shadow: 0 5px 14px rgba(25, 32, 45, .12); }
.menu-actions button { display: block; width: 100%; padding: 7px 8px; border: 0; border-radius: 4px; background: transparent; color: #444; text-align: left; font-size: 12px; cursor: pointer; }
.menu-actions button:hover { background: #f5f7fa; }
.menu-actions .danger-action { color: #c03932; }
.edit-snapshot { display: flex; flex-wrap: wrap; gap: 5px; }
.edit-snapshot input { min-width: 0; flex: 1 1 100%; padding: 6px; border: 1px solid #d5d9e0; border-radius: 5px; font-size: 12px; }
.menu-save, .menu-cancel { padding: 5px 7px; border: 0; border-radius: 4px; font-size: 11px; cursor: pointer; }
.menu-save { background: var(--brand-green); color: #fff; }
.menu-cancel { background: #f0f1f4; color: #555; }

.placeholder { color: #888; font-size: 14px; text-align: center; padding: 40px 0; }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.export-actions { display: flex; gap: 8px; }
.export-actions button {
  padding: 6px 12px;
  background: var(--brand-green-soft);
  color: var(--brand-green-dark);
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}
.equip-block { border-top: 1px solid #f0f1f4; padding-top: 12px; margin-top: 12px; }
.equip-block h3 { font-size: 13px; color: #555; margin: 0 0 6px; }
.equipment-hostname { margin: -3px 0 8px; color: #858b95; font-size: 12px; }
@media (max-width: 800px) {
  .filter-heading { width: 100%; }
  .filters label { flex: 1 1 150px; }
  .filters select, .filters input { width: 100%; }
  .content { grid-template-columns: 1fr; }
  .detail-header { align-items: flex-start; flex-wrap: wrap; }
}
</style>
