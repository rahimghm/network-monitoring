<script setup>
import { ref, onMounted } from 'vue'
import { listThresholds, createThreshold, deleteThreshold, listEquipments } from '../api.js'
import { pushToast } from '../toasts.js'

const thresholds = ref([])
const equipments = ref([])

const form = ref({
  equipment_id: '',   // '' = global
  metric: 'cpu_usage',
  operator: 'gt',
  threshold_value: 90,
})

async function refresh() {
  thresholds.value = await listThresholds()
  equipments.value = await listEquipments()
}

function equipmentName(id) {
  if (id == null) return 'Global (tous équipements)'
  return equipments.value.find(e => e.id === id)?.name || `#${id}`
}

async function submit() {
  try {
    await createThreshold({
      equipment_id: form.value.equipment_id === '' ? null : Number(form.value.equipment_id),
      metric: form.value.metric,
      operator: form.value.operator,
      threshold_value: Number(form.value.threshold_value),
    })
    await refresh()
    pushToast('Seuil ajouté.', 'success')
  } catch (e) {
    pushToast("Échec de l'ajout du seuil.", 'alert')
  }
}

async function remove(id) {
  await deleteThreshold(id)
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div class="thresholds-page">
    <form class="threshold-form" @submit.prevent="submit">
      <h2>Ajouter un seuil</h2>
      <div class="row">
        <select v-model="form.equipment_id">
          <option value="">Global (tous équipements)</option>
          <option v-for="eq in equipments" :key="eq.id" :value="eq.id">{{ eq.name }}</option>
        </select>
        <select v-model="form.metric">
          <option value="cpu_usage">CPU (%)</option>
          <option value="ram_percent">RAM (%)</option>
          <option value="temperature_c">Température (°C)</option>
        </select>
        <select v-model="form.operator">
          <option value="gt">supérieur à</option>
          <option value="lt">inférieur à</option>
        </select>
        <input type="number" v-model="form.threshold_value" step="0.1" />
        <button type="submit">Ajouter</button>
      </div>
    </form>

    <div class="threshold-list">
      <h2>Seuils configurés ({{ thresholds.length }})</h2>
      <table>
        <thead>
          <tr>
            <th>Équipement</th><th>Métrique</th><th>Condition</th><th>Statut</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in thresholds" :key="t.id">
            <td>{{ equipmentName(t.equipment_id) }}</td>
            <td>{{ t.metric }}</td>
            <td>{{ t.operator === 'gt' ? '>' : '<' }} {{ t.threshold_value }}</td>
            <td>{{ t.enabled ? 'Actif' : 'Désactivé' }}</td>
            <td><button class="delete-btn" @click="remove(t.id)">✕</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.threshold-form, .threshold-list {
  background: #fff;
  border: 1px solid #e2e5ea;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 20px;
}
h2 { font-size: 15px; margin: 0 0 12px; color: #1a1d23; }
.row { display: flex; gap: 8px; flex-wrap: wrap; }
select, input {
  padding: 7px 10px;
  border: 1px solid #d5d9e0;
  border-radius: 6px;
  font-size: 13px;
}
button[type="submit"] {
  padding: 7px 14px;
  background: #3b6fed;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; color: #888; padding: 8px; border-bottom: 1px solid #e2e5ea; }
td { padding: 8px; border-bottom: 1px solid #f0f1f4; }
.delete-btn {
  padding: 3px 8px;
  background: transparent;
  color: #d1453b;
  border: 1px solid #f0d0ce;
  border-radius: 6px;
  cursor: pointer;
}
</style>
