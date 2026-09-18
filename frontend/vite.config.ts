import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// В dev браузер ходит через Traefik: `/` → этот dev-сервер, `/api` → backend.
// Прямой прокси ниже нужен только при запуске фронта без Traefik (pnpm dev на хосте).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})
