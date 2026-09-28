import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      '^/(auth|users|audit-logs|equipments|thresholds|snapshots|health|config)': {
        target: 'http://localhost:8000',
      },
    },
  }
})
