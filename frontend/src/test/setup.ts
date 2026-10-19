import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest'
import { clearImageCache } from '@/api/images'
import { resetDb } from '@/mocks/db'
import { server } from '@/mocks/server'

// jsdom не умеет canvas и без заглушки печатает «Not implemented» в каждом тесте страниц входа.
HTMLCanvasElement.prototype.getContext = () => null

// jsdom не умеет blob-адреса, а снимки FrameView показываются через URL.createObjectURL.
URL.createObjectURL = () => 'blob:test'
URL.revokeObjectURL = () => {}
// jsdom не прокручивает; AppLayout открывает новый раздел сверху
window.scrollTo = () => {}

// Тесты ходят в те же MSW-хендлеры, что и браузер в режиме моков.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
// localStorage хранит историю чата ассистента — между тестами она не должна протекать.
beforeEach(() => {
  resetDb()
  localStorage.clear()
})
afterEach(() => {
  server.resetHandlers()
  clearImageCache()
})
afterAll(() => server.close())
