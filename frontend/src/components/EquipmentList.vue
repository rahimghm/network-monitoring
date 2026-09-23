<script setup>
import { computed } from 'vue'

const props = defineProps({
  equipments: { type: Array, required: true },
  selectedIds: { type: Array, default: () => [] },
  readOnly: { type: Boolean, default: false }
})

const emit = defineEmits(['update:selectedIds', 'delete'])

const allSelected = computed(() =>
  props.equipments.length > 0 && props.selectedIds.length === props.equipments.length
)

function toggleAll() {
  emit('update:selectedIds', allSelected.value ? [] : props.equipments.map(e => e.id))
}

function toggleOne(id) {
  const set = new Set(props.selectedIds)
  set.has(id) ? set.delete(id) : set.add(id)
  emit('update:selectedIds', [...set])
}
</script>

<template>
  <div class="equip-list">
    <div class="list-header">
      <h2>Équipements ({{ equipments.length }})</h2>
      <label class="select-all" v-if="equipments.length && !readOnly">
        <input type="checkbox" :checked="allSelected" @change="toggleAll" />
        Tout sélectionner
      </label>
    </div>

    <p v-if="equipments.length === 0" class="empty">Aucun équipement pour l'instant.</p>

    <div v-for="eq in equipments" :key="eq.id" class="equip-row">
      <input
        v-if="!readOnly"
        type="checkbox"
        :checked="selectedIds.includes(eq.id)"
        @change="toggleOne(eq.id)"
      />
      <div class="status-dot" :class="eq.is_up === true ? 'up' : eq.is_up === false ? 'down' : 'unknown'"></div>

      <div class="info">
        <div class="name">{{ eq.name }}</div>
        <div class="hostname">{{ eq.hostname }}<span v-if="eq.last_ip"> · {{ eq.last_ip }}</span></div>
      </div>

      <button v-if="!readOnly" class="delete-btn" @click.stop="emit('delete', eq)">✕</button>
    </div>
  </div>
</template>

<style scoped>
.equip-list {
  background: #fff;
  border: 1px solid #e2e5ea;
  border-radius: 10px;
  padding: 20px;
}
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.list-header h2 { font-size: 16px; margin: 0; color: #1a1d23; }
.select-all {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #555; cursor: pointer;
}
.empty { color: #888; font-size: 14px; }
.equip-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 8px;
  border-bottom: 1px solid #f0f1f4;
}
.equip-row:hover { background: #f7f8fa; }
.status-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.status-dot.up { background: #2fb344; }
.status-dot.down { background: #d1453b; }
.status-dot.unknown { background: #c7cad1; }

.info { flex: 1; min-width: 0; }
.name { font-weight: 600; font-size: 14px; color: #1a1d23; }
.hostname { font-size: 12px; color: #888; }

.delete-btn {
  padding: 4px 8px;
  background: transparent;
  color: #d1453b;
  border: 1px solid #f0d0ce;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}
</style>
