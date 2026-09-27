import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { createTestQueryClient } from '@/test/render'
import { useDetectBacklog } from './frames'

describe('useDetectBacklog', () => {
  it('sends POST /sites/{id}/photos/detect and returns counts', async () => {
    const client = createTestQueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useDetectBacklog('site-berezniki'), { wrapper })

    result.current.mutate(undefined)

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
      expect(result.current.data).toBeDefined()
      expect(result.current.data?.processed).toBeDefined()
      expect(result.current.data?.done).toBeDefined()
      expect(result.current.data?.failed).toBeDefined()
      expect(result.current.data?.skipped).toBeDefined()
    })
  })

  it('accepts optional statuses parameter', async () => {
    const client = createTestQueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useDetectBacklog('site-berezniki'), { wrapper })

    result.current.mutate(['pending', 'failed'])

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
      expect(result.current.data).toBeDefined()
      expect(result.current.data?.processed).toBeDefined()
      expect(result.current.data?.done).toBeDefined()
      expect(result.current.data?.failed).toBeDefined()
      expect(result.current.data?.skipped).toBeDefined()
    })
  })
})
