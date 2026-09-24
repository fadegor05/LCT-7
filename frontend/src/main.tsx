import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from '@/app/App'
import { env } from '@/lib/env'
import '@/styles/global.css'

/** При VITE_USE_MOCKS=true поднимаем MSW до первого запроса; в сборку без моков он не попадает. */
async function enableMocks() {
  if (!env.useMocks) return
  const { worker } = await import('@/mocks/browser')
  await worker.start({ onUnhandledRequest: 'bypass' })
}

void enableMocks().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
