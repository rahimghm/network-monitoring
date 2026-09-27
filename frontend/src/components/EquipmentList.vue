<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  equipments: { type: Array, required: true },
  selectedIds: { type: Array, default: () => [] },
  readOnly: { type: Boolean, default: false },
  canSelect: { type: Boolean, default: true }
})

const emit = defineEmits(['update:selectedIds', 'delete', 'update'])
const openMenuId = ref(null)
const editingId = ref(null)
const editForm = ref({ name: '', hostname: '', community: '' })

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

function toggleMenu(id) {
  openMenuId.value = openMenuId.value === id ? null : id
}

function startEditing(eq) {
  editingId.value = eq.id
  openMenuId.value = null
  editForm.value = { name: eq.name, hostname: eq.hostname, community: eq.community || 'public' }
}

function saveEditing() {
  emit('update', { id: editingId.value, ...editForm.value })
  editingId.value = null
}
</script>

<template>
  <div class="equip-list">
    <div class="list-header">
      <h2>Équipements ({{ equipments.length }})</h2>
      <label class="select-all" v-if="equipments.length && canSelect">
        <input type="checkbox" :checked="allSelected" @change="toggleAll" />
        Tout sélectionner
      </label>
    </div>

    <p v-if="equipments.length === 0" class="empty">Aucun équipement pour l'instant.</p>

    <div v-for="eq in equipments" :key="eq.id" class="equip-row">
      <input
        v-if="canSelect"
        type="checkbox"
        :checked="selectedIds.includes(eq.id)"
        @change="toggleOne(eq.id)"
      />
      <div class="status-dot" :class="eq.is_up === true ? 'up' : eq.is_up === false ? 'down' : 'unknown'"></div>

      <div v-if="editingId !== eq.id" class="info">
        <div class="name">{{ eq.name }}</div>
        <div class="hostname">{{ eq.hostname }}<span v-if="eq.last_ip"> · {{ eq.last_ip }}</span></div>
      </div>

      <div v-if="editingId === eq.id" class="edit-fields">
        <input v-model.trim="editForm.name" aria-label="Nom de l'équipement" />
        <input v-model.trim="editForm.hostname" aria-label="Hostname de l'équipement" />
        <input v-model.trim="editForm.community" aria-label="Communauté SNMP" />
        <div class="edit-actions">
          <button class="save-btn" @click.stop="saveEditing">Enregistrer</button>
          <button class="cancel-btn" @click.stop="editingId = null">Annuler</button>
        </div>
      </div>

      <div v-if="!readOnly && editingId !== eq.id" class="actions">
        <button class="more-btn" title="Actions" @click.stop="toggleMenu(eq.id)">...</button>
        <div v-if="openMenuId === eq.id" class="action-menu">
          <button @click.stop="startEditing(eq)">Modifier</button>
          <button class="danger-action" @click.stop="emit('delete', eq); openMenuId = null">Supprimer</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.equip-list {
  background: #fff;
  border: 1px solid var(--line);
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

.actions { position: relative; }
.more-btn { padding: 3px 8px; background: transparent; color: #666; border: 1px solid var(--line); border-radius: 6px; cursor: pointer; font-weight: 700; letter-spacing: 2px; }
.action-menu { position: absolute; right: 0; top: 30px; z-index: 5; min-width: 120px; padding: 4px; background: #fff; border: 1px solid var(--line); border-radius: 6px; box-shadow: 0 5px 14px rgba(25, 32, 45, .12); }
.action-menu button { display: block; width: 100%; padding: 7px 9px; background: transparent; border: 0; border-radius: 4px; color: #444; text-align: left; cursor: pointer; font-size: 12px; }
.action-menu button:hover { background: #f5f7fa; }
.action-menu .danger-action { color: #c03932; }
.edit-fields { display: grid; flex: 1; grid-template-columns: repeat(3, minmax(100px, 1fr)); gap: 6px; }
.edit-fields input { min-width: 0; padding: 6px 7px; border: 1px solid #d5d9e0; border-radius: 5px; font-size: 12px; }
.edit-actions { display: flex; align-items: center; gap: 4px; grid-column: 1 / -1; }
.edit-actions button { padding: 5px 8px; border: 0; border-radius: 5px; cursor: pointer; font-size: 11px; }
.save-btn { background: var(--brand-green); color: #fff; }
.cancel-btn { background: #f0f1f4; color: #555; }
@media (max-width: 600px) { .edit-fields { grid-template-columns: 1fr; } }
</style>
