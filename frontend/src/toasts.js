import { reactive } from 'vue'

let nextId = 1
export const toasts = reactive([])

export function pushToast(message, kind = 'info', durationMs = 6000) {
  const id = nextId++
  toasts.push({ id, message, kind })
  setTimeout(() => {
    const idx = toasts.findIndex(t => t.id === id)
    if (idx !== -1) toasts.splice(idx, 1)
  }, durationMs)
}
