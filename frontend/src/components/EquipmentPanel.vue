<script setup>
import DiagnosticPanel from './DiagnosticPanel.vue'
import MetricsChart from './MetricsChart.vue'

const props = defineProps({
  equipment: { type: Object, required: true },
  diagnostic: { type: Object, default: null },
  isDiagnosing: { type: Boolean, default: false },
  breaches: { type: Object, default: () => ({ cpu_usage: false, ram_percent: false, temperature_c: false }) }
})

const emit = defineEmits(['close', 'diagnose'])
</script>

<template>
  <div class="panel-card">
    <div class="panel-card-header">
      <div class="title-group">
        <span class="status-dot" :class="equipment.is_up === true ? 'up' : equipment.is_up === false ? 'down' : 'unknown'"></span>
        <span class="title">{{ equipment.name }}</span>
      </div>
      <div class="header-actions">
        <button class="mini-btn" :disabled="isDiagnosing" @click="emit('diagnose', equipment)">
          {{ isDiagnosing ? '...' : 'Re-diagnostiquer' }}
        </button>
        <button class="close-btn" @click="emit('close', equipment.id)" title="Fermer ce panneau">✕</button>
      </div>
    </div>

    <DiagnosticPanel :equipment="equipment" :diagnostic="diagnostic" :breaches="breaches" />
    <MetricsChart :equipment-id="equipment.id" />
  </div>
</template>

<style scoped>
.panel-card {
  background: #fff;
  border: 1px solid #e2e5ea;
  border-radius: 10px;
  padding: 16px;
}
.panel-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 0 2px;
}
.title-group { display: flex; align-items: center; gap: 8px; }
.title { font-weight: 700; font-size: 14px; color: #1a1d23; }
.status-dot {
  width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0;
}
.status-dot.up { background: #2fb344; }
.status-dot.down { background: #d1453b; }
.status-dot.unknown { background: #c7cad1; }

.header-actions { display: flex; gap: 6px; }
.mini-btn {
  padding: 4px 10px;
  background: #eef2fe;
  color: #3b6fed;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}
.mini-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.close-btn {
  padding: 4px 8px;
  background: transparent;
  color: #888;
  border: 1px solid #e2e5ea;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}
.close-btn:hover { background: #fbe7e6; color: #d1453b; border-color: #f0d0ce; }
</style>
