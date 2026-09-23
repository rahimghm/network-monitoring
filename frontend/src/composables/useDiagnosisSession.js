import { reactive, ref } from 'vue'
import { WS_BASE, getToken } from '../api.js'
import { pushToast } from '../toasts.js'

export function useDiagnosisSession() {
  const liveData = reactive({})       // equipment_id -> dernier payload de diagnostic reçu
  const status = ref('idle')          // idle | started | paused | stopped
  const lastSnapshotId = ref(null)
  let socket = null

  function connect() {
    return new Promise((resolve, reject) => {
      const token = getToken()
      socket = new WebSocket(`${WS_BASE}/ws/diagnose?token=${encodeURIComponent(token)}`)

      socket.onopen = () => resolve()
      socket.onerror = (e) => reject(e)

      socket.onmessage = (event) => {
        const msg = JSON.parse(event.data)
        if (msg.type === 'update') {
          liveData[msg.equipment_id] = msg.data
        } else if (msg.type === 'alert') {
          pushToast(`⚠ Équipement #${msg.equipment_id} — ${msg.message}`, 'alert')
        } else if (msg.type === 'status') {
          status.value = msg.status
        } else if (msg.type === 'snapshot_saved') {
          lastSnapshotId.value = msg.snapshot_id
          pushToast('Snapshot enregistré.', 'success')
        }
      }

      socket.onclose = () => { status.value = 'stopped' }
    })
  }

  async function start(equipmentIds, intervalSeconds = 5) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      await connect()
    }
    socket.send(JSON.stringify({
      action: 'start', equipment_ids: equipmentIds, interval_seconds: intervalSeconds
    }))
  }

  function pause() {
    socket?.send(JSON.stringify({ action: 'pause' }))
  }

  function resume() {
    socket?.send(JSON.stringify({ action: 'resume' }))
  }

  function stop() {
    socket?.send(JSON.stringify({ action: 'stop' }))
    socket?.close()
    socket = null
    status.value = 'stopped'
  }

  function snapshot(label) {
    socket?.send(JSON.stringify({ action: 'snapshot', label }))
  }

  return { liveData, status, lastSnapshotId, start, pause, resume, stop, snapshot }
}
