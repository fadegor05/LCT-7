/** Настройки сборки. Все значения приходят из VITE_* переменных (см. .env.example). */
export const env = {
  /** true — запросы к API обслуживает MSW (src/mocks), false — реальный backend. */
  useMocks: import.meta.env.VITE_USE_MOCKS === 'true',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api',
}
