import { reactive, ref } from 'vue'
import { WS_BASE, getToken } from '../api.js'
import { pushToast } from '../toasts.js'

export function useDiagnosisSession() {
  const liveData = reactive({})       // equipment_id -> dernier payload de diagnostic reçu
  const status = ref('idle')          // idle | started | paused | stopped
  const lastSnapshotId = ref(null)
  let socket = null
  let statusWaiter = null

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
          // Resume is an active polling state in the UI.
          status.value = msg.status === 'resumed' ? 'started' : msg.status
          if (statusWaiter?.status === msg.status) {
            statusWaiter.resolve()
            statusWaiter = null
          }
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
    await sendAndWait({
      action: 'start', equipment_ids: equipmentIds, interval_seconds: intervalSeconds
    }, 'started')
  }

  async function pause() {
    await sendAndWait({ action: 'pause' }, 'paused')
  }

  async function resume() {
    await sendAndWait({ action: 'resume' }, 'resumed')
  }

  async function stop() {
    if (socket?.readyState === WebSocket.OPEN) {
      try { await sendAndWait({ action: 'stop' }, 'stopped') } catch (e) { /* socket may already be closed */ }
    }
    disconnect()
  }

  function sendAndWait(message, expectedStatus) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return Promise.resolve()
    return new Promise((resolve, reject) => {
      statusWaiter = { status: expectedStatus, resolve, reject }
      socket.send(JSON.stringify(message))
    })
  }

  function disconnect() {
    socket?.close()
    socket = null
    status.value = 'stopped'
  }

  function snapshot(label) {
    socket?.send(JSON.stringify({ action: 'snapshot', label }))
  }

  return { liveData, status, lastSnapshotId, connect, disconnect, start, pause, resume, stop, snapshot }
}
