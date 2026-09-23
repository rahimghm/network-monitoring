<script setup>
import { ref } from 'vue'

const props = defineProps({
  selectedCount: { type: Number, required: true },
  status: { type: String, required: true }  // idle | started | paused | stopped
})

const emit = defineEmits(['start', 'pause', 'resume', 'stop', 'snapshot'])

const snapshotLabel = ref('')

function doSnapshot() {
  emit('snapshot', snapshotLabel.value || `Snapshot ${new Date().toLocaleString('fr-FR')}`)
  snapshotLabel.value = ''
}
</script>

<template>
  <div class="controls">
    <span class="count">{{ selectedCount }} sélectionné(s)</span>

    <button
      v-if="status !== 'started'"
      class="btn primary"
      :disabled="selectedCount === 0"
      @click="status === 'paused' ? emit('resume') : emit('start')"
    >
      {{ status === 'paused' ? 'Reprendre' : 'Démarrer' }}
    </button>

    <button v-else class="btn" @click="emit('pause')">Pause</button>

    <button class="btn danger" :disabled="status === 'idle' || status === 'stopped'" @click="emit('stop')">
      Stop
    </button>

    <input
      v-model="snapshotLabel"
      type="text"
      placeholder="Nom du snapshot (optionnel)"
      class="snapshot-input"
    />
    <button class="btn" :disabled="status !== 'started' && status !== 'paused'" @click="doSnapshot">
      Snapshot
    </button>
  </div>
</template>

<style scoped>
.controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  background: #fff;
  border: 1px solid #e2e5ea;
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 16px;
}
.count { font-size: 12px; color: #888; margin-right: 4px; }
.btn {
  padding: 7px 14px;
  background: #eef2fe;
  color: #3b6fed;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn.primary { background: #3b6fed; color: #fff; }
.btn.danger { background: #fbe7e6; color: #d1453b; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.snapshot-input {
  flex: 1;
  min-width: 160px;
  padding: 7px 10px;
  border: 1px solid #d5d9e0;
  border-radius: 6px;
  font-size: 13px;
}
</style>
