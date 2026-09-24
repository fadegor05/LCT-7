/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// В dev браузер ходит через Traefik: `/` → этот dev-сервер, `/api` → backend.
// Прямой прокси ниже нужен только при запуске фронта без Traefik (pnpm dev на хосте).
// При VITE_USE_MOCKS=true запросы к /api перехватывает MSW прямо в браузере — бэкенд не нужен.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    rollupOptions: {
      output: {
        // Вендоры отдельными чанками: они меняются реже кода экранов и дольше живут в кэше.
        manualChunks: {
          react: ['react', 'react-dom', 'react-router'],
          query: ['@tanstack/react-query'],
          forms: ['zod', 'react-hook-form', '@hookform/resolvers'],
        },
      },
    },
  },
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
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: { modules: { classNameStrategy: 'non-scoped' } },
    restoreMocks: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/main.tsx',
        'src/mocks/browser.ts',
        'src/test/**',
        'src/**/*.test.{ts,tsx}',
        'src/**/index.ts',
        'src/vite-env.d.ts',
      ],
      thresholds: { statements: 90, branches: 85, functions: 90, lines: 90 },
    },
  },
})
