import axios from 'axios'
import { reactive } from 'vue'

export const API_BASE = 'http://localhost:8000'
export const WS_BASE = 'ws://localhost:8000'

const api = axios.create({ baseURL: API_BASE })

export const authState = reactive({
  token: localStorage.getItem('auth_token'),
  role: localStorage.getItem('auth_role'),
  username: localStorage.getItem('auth_username'),
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Si le token est expiré/invalide, on nettoie et on renvoie vers /login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_role')
      localStorage.removeItem('auth_username')
      authState.token = null
      authState.role = null
      authState.username = null
      if (location.pathname !== '/login') location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ---------- Auth ----------

export const getAuthStatus = () => api.get('/auth/status').then(r => r.data)

export const registerFirstAdmin = (payload) =>
  api.post('/auth/register', payload).then(r => r.data)

export const login = async (username, password) => {
  const form = new URLSearchParams()
  form.append('username', username)
  form.append('password', password)
  const { data } = await api.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  })
  localStorage.setItem('auth_token', data.access_token)
  localStorage.setItem('auth_role', data.role)
  localStorage.setItem('auth_username', data.username)
  authState.token = data.access_token
  authState.role = data.role
  authState.username = data.username
  return data
}

export const logout = async () => {
  try { await api.post('/auth/logout') } catch (error) { /* local logout still succeeds */ }
  localStorage.removeItem('auth_token')
  localStorage.removeItem('auth_role')
  localStorage.removeItem('auth_username')
  authState.token = null
  authState.role = null
  authState.username = null
}

export const getToken = () => localStorage.getItem('auth_token')
export const getRole = () => localStorage.getItem('auth_role')
export const isAuthenticated = () => !!getToken()
export const changePassword = (payload) => api.patch('/auth/password', payload)

export const listUsers = () => api.get('/users').then(r => r.data)
export const createUser = (payload) => api.post('/users', payload).then(r => r.data)
export const updateUser = (id, payload) => api.patch(`/users/${id}`, payload).then(r => r.data)
export const deleteUser = (id) => api.delete(`/users/${id}`)
export const listAuditLogs = (filters = {}) =>
  api.get('/audit-logs', { params: { limit: 200, ...filters } }).then(r => r.data)

// ---------- Équipements ----------

export const listEquipments = () => api.get('/equipments').then(r => r.data)
export const createEquipment = (payload) => api.post('/equipments', payload).then(r => r.data)
export const updateEquipment = (id, payload) => api.patch(`/equipments/${id}`, payload).then(r => r.data)
export const deleteEquipment = (id) => api.delete(`/equipments/${id}`)
export const diagnoseEquipment = (id) => api.post(`/equipments/${id}/diagnose`).then(r => r.data)

export const getEquipmentHistory = (id, limit = 20) =>
  api.get(`/equipments/${id}/diagnostics`, { params: { limit } }).then(r => r.data)

export const getLatestDiagnostic = async (id) => {
  const history = await getEquipmentHistory(id, 1)
  return history.length ? history[0] : null
}

export const getMetricsTimeseries = (id, limit = 50) =>
  api.get(`/equipments/${id}/metrics/timeseries`, { params: { limit } }).then(r => r.data)

export const getConfig = () => api.get('/config').then(r => r.data)

// ---------- Alertes / seuils (Feature 4) ----------

export const listThresholds = () => api.get('/thresholds').then(r => r.data)
export const createThreshold = (payload) => api.post('/thresholds', payload).then(r => r.data)
export const deleteThreshold = (id) => api.delete(`/thresholds/${id}`)

// ---------- Snapshots / historique (Feature 3) ----------

export const listSnapshots = (filters = {}) =>
  api.get('/snapshots', { params: filters }).then(r => r.data)

export const getSnapshot = (id) => api.get(`/snapshots/${id}`).then(r => r.data)
export const updateSnapshot = (id, payload) => api.patch(`/snapshots/${id}`, payload).then(r => r.data)
export const deleteSnapshot = (id) => api.delete(`/snapshots/${id}`)

// Téléchargement authentifié (le header Authorization ne peut pas être joint
// à un simple lien <a href>, donc on récupère le fichier en blob puis on
// déclenche le téléchargement nous-mêmes).
export const downloadSnapshot = async (id, format, filename) => {
  let res
  try {
    res = await api.get(`/snapshots/${id}/export/${format}`, { responseType: 'blob' })
  } catch (error) {
    if (error.response?.data instanceof Blob) {
      const text = await error.response.data.text()
      try { error.response.data = JSON.parse(text) } catch { error.response.data = { detail: text } }
    }
    throw error
  }
  const url = window.URL.createObjectURL(new Blob([res.data]))
  const link = document.createElement('a')
  link.href = url
  link.download = filename || `snapshot_${id}.${format}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export default api
