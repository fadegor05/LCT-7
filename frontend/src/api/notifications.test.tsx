import { describe, expect, it } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { createTestQueryClient } from '@/test/render'
import {
  useChannels,
  useCreateTestNotification,
  useMarkAllRead,
  useNotifications,
} from './notifications'

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
}

describe('api уведомлений', () => {
  it('лента приходит пустой и валидируется схемой', async () => {
    const { result } = renderHook(() => useNotifications(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual({ items: [], unread_count: 0 })
  })

  it('созданное уведомление попадает в ленту', async () => {
    const { result: create } = renderHook(() => useCreateTestNotification(), { wrapper })
    create.current.mutate({})
    await waitFor(() => expect(create.current.isSuccess).toBe(true))

    const { result: feed } = renderHook(() => useNotifications(), { wrapper })
    await waitFor(() => expect(feed.current.data?.unread_count).toBe(1))
  })

  it('пометка прочитанным обнуляет счётчик', async () => {
    const { result: create } = renderHook(() => useCreateTestNotification(), { wrapper })
    create.current.mutate({})
    await waitFor(() => expect(create.current.isSuccess).toBe(true))

    const { result: read } = renderHook(() => useMarkAllRead(), { wrapper })
    read.current.mutate()
    await waitFor(() => expect(read.current.isSuccess).toBe(true))

    const { result: feed } = renderHook(() => useNotifications(), { wrapper })
    await waitFor(() => expect(feed.current.data?.unread_count).toBe(0))
  })

  it('список каналов приходит пустым', async () => {
    const { result } = renderHook(() => useChannels(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([])
  })
})
