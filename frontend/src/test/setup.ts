import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest'
import { resetDb } from '@/mocks/db'
import { server } from '@/mocks/server'

// Тесты ходят в те же MSW-хендлеры, что и браузер в режиме моков.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => resetDb())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
