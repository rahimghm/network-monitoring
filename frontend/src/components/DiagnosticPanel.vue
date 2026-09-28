<script setup>
const props = defineProps({
  equipment: { type: Object, default: null },
  diagnostic: { type: Object, default: null },
  breaches: { type: Object, default: () => ({ cpu_usage: false, ram_percent: false, temperature_c: false }) }
})

function formatBytes(kb) {
  if (kb == null) return '—'
  if (kb < 1024) return `${kb} Ko`
  return `${(kb / 1024).toFixed(1)} Mo`
}

function formatSpeed(bps) {
  if (bps == null) return '—'
  if (bps >= 1_000_000_000) return `${(bps / 1_000_000_000).toFixed(1)} Gbps`
  if (bps >= 1_000_000) return `${(bps / 1_000_000).toFixed(0)} Mbps`
  return `${bps} bps`
}

function formatOctets(o) {
  if (o == null) return '—'
  if (o >= 1_000_000_000) return `${(o / 1_000_000_000).toFixed(2)} Go`
  if (o >= 1_000_000) return `${(o / 1_000_000).toFixed(1)} Mo`
  if (o >= 1_000) return `${(o / 1_000).toFixed(1)} Ko`
  return `${o} o`
}

function formatPackets(value) {
  if (value == null) return '—'
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)} G`
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)} k`
  return value.toLocaleString('fr-FR')
}

function formatUptime(seconds100) {
  if (seconds100 == null) return '—'
  const totalSeconds = Math.floor(seconds100 / 100)
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  return `${days}j ${hours}h ${minutes}m`
}

</script>

<template>
  <div class="panel">
    <div v-if="!equipment" class="placeholder">
      Sélectionne un équipement et clique sur "Diagnostiquer".
    </div>

    <div v-else-if="!diagnostic" class="placeholder">
      Aucun diagnostic encore lancé pour <strong>{{ equipment.name }}</strong>.
    </div>

    <div v-else>
      <div class="header">
        <h2>{{ equipment.name }}</h2>
        <span class="badge" :class="diagnostic.is_up ? 'up' : 'down'">
          {{ diagnostic.is_up ? 'UP' : 'DOWN' }}
        </span>
      </div>

      <p class="ip-line">
        {{ equipment.hostname }}
        <span v-if="diagnostic.resolved_ip"> → {{ diagnostic.resolved_ip }}</span>
      </p>

      <p v-if="diagnostic.error_message" class="error-msg">
        {{ diagnostic.error_message }}
      </p>

      <template v-else>
        <div class="metrics-grid">
          <div class="metric-card" :class="{ breached: breaches.cpu_usage }">
            <div class="metric-label">CPU</div>
            <div class="metric-value">{{ diagnostic.cpu_usage != null ? diagnostic.cpu_usage + ' %' : '—' }}</div>
          </div>
          <div class="metric-card" :class="{ breached: breaches.ram_percent }">
            <div class="metric-label">RAM utilisée</div>
            <div class="metric-value">
              {{ formatBytes(diagnostic.ram_used_kb) }} / {{ formatBytes(diagnostic.ram_total_kb) }}
            </div>
          </div>
          <div class="metric-card" :class="{ breached: breaches.temperature_c }">
            <div class="metric-label">Température</div>
            <div class="metric-value">
              {{ diagnostic.temperature_c != null ? diagnostic.temperature_c + ' °C' : 'N/A' }}
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Uptime</div>
            <div class="metric-value">{{ formatUptime(diagnostic.sys_uptime) }}</div>
          </div>
        </div>

        <p class="sys-descr" v-if="diagnostic.sys_descr">{{ diagnostic.sys_descr }}</p>

        <h3>Interfaces ({{ diagnostic.interfaces.length }})</h3>
        <div class="table-scroll">
          <table class="if-table ui-table">
            <thead>
            <tr>
              <th>Port</th>
              <th>Admin</th>
              <th>Statut</th>
              <th>STP</th>
              <th>Vitesse</th>
              <th>Octets entrants</th>
              <th>Octets sortants</th>
              <th>Paquets entrants</th>
              <th>Paquets sortants</th>
              <th>Erreurs entrantes</th>
              <th>Erreurs sortantes</th>
              <th>Rejets entrants</th>
              <th>Rejets sortants</th>
            </tr>
            </thead>
            <tbody>
              <tr v-for="iface in diagnostic.interfaces" :key="iface.if_index">
                <td>{{ iface.if_descr || `#${iface.if_index}` }}</td>
                <td>{{ iface.admin_status || '—' }}</td>
                <td>
                  <span class="if-status" :class="iface.oper_status">{{ iface.oper_status }}</span>
                </td>
                <td>{{ iface.stp_state || '—' }}</td>
                <td>{{ formatSpeed(iface.speed_bps) }}</td>
                <td :title="iface.in_octets?.toLocaleString('fr-FR')">{{ formatOctets(iface.in_octets) }}</td>
                <td :title="iface.out_octets?.toLocaleString('fr-FR')">{{ formatOctets(iface.out_octets) }}</td>
                <td :title="iface.in_packets?.toLocaleString('fr-FR')">{{ formatPackets(iface.in_packets) }}</td>
                <td :title="iface.out_packets?.toLocaleString('fr-FR')">{{ formatPackets(iface.out_packets) }}</td>
                <td :title="iface.in_errors?.toLocaleString('fr-FR')">{{ formatPackets(iface.in_errors) }}</td>
                <td :title="iface.out_errors?.toLocaleString('fr-FR')">{{ formatPackets(iface.out_errors) }}</td>
                <td :title="iface.in_discards?.toLocaleString('fr-FR')">{{ formatPackets(iface.in_discards) }}</td>
                <td :title="iface.out_discards?.toLocaleString('fr-FR')">{{ formatPackets(iface.out_discards) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

      </template>
    </div>
  </div>
</template>

<style scoped>
.panel {
  background: transparent;
  padding: 4px 2px;
  min-height: 0;
}
.placeholder {
  color: #888;
  font-size: 14px;
  padding: 40px 0;
  text-align: center;
}
.header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header h2 { margin: 0; font-size: 18px; color: #1a1d23; }
.badge {
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.3px;
}
.badge.up { background: #e5f7e8; color: #2fb344; }
.badge.down { background: #fbe7e6; color: #d1453b; }

.ip-line { color: #888; font-size: 13px; margin: 4px 0 16px; }
.error-msg {
  background: #fbe7e6;
  color: #a12a22;
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 14px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.metric-card {
  background: #f7f8fa;
  border-radius: 8px;
  padding: 12px 14px;
  border: 2px solid transparent;
  transition: border-color 0.2s, background 0.2s;
}
.metric-card.breached {
  background: #fdecea;
  border-color: #d1453b;
}
.metric-label { font-size: 12px; color: #888; margin-bottom: 4px; }
.metric-value { font-size: 18px; font-weight: 700; color: #1a1d23; }
.metric-card.breached .metric-value { color: #d1453b; }

.sys-descr {
  font-size: 12px;
  color: #aaa;
  font-family: monospace;
  margin-bottom: 18px;
  word-break: break-word;
}

h3 { font-size: 14px; margin: 0 0 10px; color: #1a1d23; }
.table-scroll { overflow-x: auto; max-width: 100%; }
.if-table { width: max-content; min-width: 100%; border-collapse: collapse; font-size: 13px; }
.if-table th {
  text-align: left;
  color: #888;
  font-weight: 600;
  padding: 8px 10px;
  border-bottom: 1px solid #e2e5ea;
}
.if-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #f0f1f4;
  color: #1a1d23;
}
.mac-address { font-family: monospace; }
.if-status {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}
.if-status.up { background: #e5f7e8; color: #2fb344; }
.if-status.down { background: #fbe7e6; color: #d1453b; }
</style>
