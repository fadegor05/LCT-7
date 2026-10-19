import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { env } from '@/lib/env'
import { createTestQueryClient } from '@/test/render'
import { framesApi, originalImageUrl, useDetectBacklog, usePhoto } from './frames'
import { keys } from './keys'

function wrapperWith(client = createTestQueryClient()) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

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

describe('originalImageUrl', () => {
  it('points to the frame without boxes', () => {
    expect(originalImageUrl('site-berezniki', 'ph-1')).toBe(
      `${env.apiBaseUrl}/sites/site-berezniki/photos/ph-1/image`,
    )
  })
})

describe('framesApi.photo', () => {
  it('returns the photo with its detections', async () => {
    const photo = await framesApi.photo('site-berezniki', 'ph-1')
    expect(photo.id).toBe('ph-1')
    expect(photo.detections).toHaveLength(2)
    const [first] = photo.detections
    expect(first?.equipment_title).toEqual(expect.any(String))
    expect(first?.bbox).toHaveLength(4)
  })
})

describe('usePhoto', () => {
  it('loads the photo detail by id', async () => {
    const { result } = renderHook(() => usePhoto('site-berezniki', 'ph-1'), {
      wrapper: wrapperWith(),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.detections).toHaveLength(2)
  })

  it('stays idle without a photo id', () => {
    const { result } = renderHook(() => usePhoto('site-berezniki', null), {
      wrapper: wrapperWith(),
    })
    expect(result.current.fetchStatus).toBe('idle')
  })

  it('is covered by the site-wide invalidation key', () => {
    const detail = keys.photo('site-berezniki', 'ph-1')
    expect(detail.slice(0, 2)).toEqual(keys.site('site-berezniki'))
  })
})
