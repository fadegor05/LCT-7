import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { createTestQueryClient } from '@/test/render'
import { useMe } from './sites'

describe('useMe', () => {
  it('loads the single stand user who signs decisions', async () => {
    const client = createTestQueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useMe(), { wrapper })
    await waitFor(() => expect(result.current.data?.full_name).toBe('инженер [ФИО]'))
  })
})
