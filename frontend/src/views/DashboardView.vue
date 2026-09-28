<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import EquipmentForm from '../components/EquipmentForm.vue'
import EquipmentList from '../components/EquipmentList.vue'
import EquipmentPanel from '../components/EquipmentPanel.vue'
import SessionControls from '../components/SessionControls.vue'
import { listEquipments, createEquipment, updateEquipment, deleteEquipment, listThresholds, diagnoseEquipment, getRole } from '../api.js'
import { useDiagnosisSession } from '../composables/useDiagnosisSession.js'
import { computeBreaches } from '../thresholds.js'
import { pushToast } from '../toasts.js'

const equipments = ref([])
const selectedIds = ref([])
const loadError = ref(null)
const thresholds = ref([])
const role = getRole()
const canManageEquipment = role === 'admin' || role === 'supervisor'
const canDiagnose = role !== 'technician'

const { liveData, status, connect, disconnect, snapshot: doSnapshot, start, pause, resume, stop } = useDiagnosisSession()

async function refresh() {
  try {
    equipments.value = await listEquipments()
    loadError.value = null
  } catch (e) {
    loadError.value = "Impossible de contacter l'API (vérifie que le backend tourne sur :8000)."
  }
}

async function loadThresholds() {
  try {
    thresholds.value = await listThresholds()
  } catch (e) {
    // pas bloquant : le highlight rouge sera juste inactif
  }
}

async function handleCreate(payload) {
  await createEquipment(payload)
  await refresh()
}

async function handleDelete(eq) {
  if (!window.confirm(`Supprimer l'équipement « ${eq.name} » ?`)) return
  try {
    await deleteEquipment(eq.id)
    selectedIds.value = selectedIds.value.filter(id => id !== eq.id)
    await refresh()
    pushToast('Équipement supprimé.', 'success')
  } catch (e) {
    pushToast(e.response?.data?.detail || 'Échec de la suppression.', 'alert')
  }
}

async function handleUpdate({ id, ...payload }) {
  if (!payload.name || !payload.hostname) {
    pushToast('Le nom et le hostname sont requis.', 'alert')
    return
  }
  try {
    await updateEquipment(id, payload)
    await refresh()
    pushToast('Équipement modifié.', 'success')
  } catch (e) {
    pushToast(e.response?.data?.detail || 'Échec de la modification.', 'alert')
  }
}

async function handleStart() {
  if (selectedIds.value.length === 0) return
  try {
    await start(selectedIds.value, 5)
  } catch (e) {
    pushToast("Connexion WebSocket impossible.", 'alert')
  }
}

function handleSnapshot(label) {
  if (status.value !== 'started' && status.value !== 'paused') return
  doSnapshot(label)
}

function equipmentById(id) {
  return equipments.value.find(e => e.id === id) || { id, name: '…', hostname: '', is_up: null }
}

// Ferme un panneau : le retire de la sélection et de l'affichage. Le backend
// continue de sonder l'équipement jusqu'au clic sur "Stop" (session globale) —
// limite connue, acceptable pour ce cas d'usage.
function handleClosePanel(id) {
  selectedIds.value = selectedIds.value.filter(i => i !== id)
  delete liveData[id]
}

// Diagnostic ponctuel immédiat (bouton "Re-diagnostiquer" d'un panneau),
// indépendant du rythme 5s de la session WebSocket en cours.
async function handleManualDiagnose(eq) {
  try {
    const result = await diagnoseEquipment(eq.id)
    liveData[eq.id] = result
  } catch (e) {
    pushToast(`Échec du diagnostic pour ${eq.name}.`, 'alert')
  }
}

const openPanelIds = computed(() =>
  Object.keys(liveData).map(Number).filter(id => selectedIds.value.includes(id))
)

function breachesFor(id) {
  return computeBreaches(thresholds.value, id, liveData[id])
}

onMounted(async () => {
  await refresh()
  await loadThresholds()
  try { await connect() } catch (e) { pushToast('Connexion au flux live impossible.', 'alert') }
})

onUnmounted(() => {
  // Stop the shared backend session before closing this page's socket.
  void stop()
})
</script>

<template>
  <div>
    <p v-if="loadError" class="global-error">{{ loadError }}</p>

    <div class="layout">
      <aside>
        <EquipmentForm v-if="canManageEquipment" @created="handleCreate" />
        <EquipmentList
          :equipments="equipments"
          v-model:selected-ids="selectedIds"
          :read-only="!canManageEquipment"
          :can-select="true"
          @delete="handleDelete"
          @update="handleUpdate"
        />
      </aside>

      <main>
        <SessionControls
          :selected-count="selectedIds.length"
          :status="status"
          @start="handleStart"
          @pause="pause"
          @resume="resume"
          @stop="stop"
          @snapshot="handleSnapshot"
        />
        <p v-if="openPanelIds.length === 0" class="placeholder-main">
          Sélectionne un ou plusieurs équipements puis clique sur "Démarrer" pour lancer
          un diagnostic en temps réel (toutes les 5s), simultané pour chacun.
        </p>

        <div class="panels-grid">
          <EquipmentPanel
            v-for="id in openPanelIds"
            :key="id"
            :equipment="equipmentById(id)"
            :diagnostic="liveData[id] || null"
            :breaches="breachesFor(id)"
            :can-diagnose="canDiagnose"
            @close="handleClosePanel"
            @diagnose="handleManualDiagnose"
          />
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.global-error {
  background: #fbe7e6;
  color: #a12a22;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 16px;
}
.layout {
  display: grid;
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
aside {
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: sticky;
  top: 24px;
}
.placeholder-main {
  color: #888;
  font-size: 14px;
  background: #fff;
  border: 1px dashed #d5d9e0;
  border-radius: 10px;
  padding: 30px;
  text-align: center;
}
.supervisor-note {
  background: #fff;
  border: 1px solid #e2e5ea;
  border-radius: 10px;
  padding: 12px 16px;
  font-size: 13px;
  color: #666;
  margin-bottom: 16px;
}
.panels-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
  gap: 20px;
  align-items: start;
}
@media (max-width: 800px) {
  .layout { grid-template-columns: 1fr; }
  aside { position: static; }
  .panels-grid { grid-template-columns: 1fr; }
}
</style>
