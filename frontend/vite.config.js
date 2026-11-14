import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev the SPA is served by Vite on :5173 while the API runs on :8000. With
// VITE_API_URL unset the app calls the same origin, so proxy API paths through.
const backend = process.env.VITE_DEV_BACKEND || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': backend,
      '/auth': backend,
    },
  },
})
