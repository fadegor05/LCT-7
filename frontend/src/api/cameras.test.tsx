import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { setToken } from '@/lib/authStorage'
import { createTestQueryClient } from '@/test/render'
import { BEREZNIKI } from '@/mocks/fixtures'
import { useCameras, useDeleteCamera, useSaveCamera, type CameraInput } from './cameras'

const input: CameraInput = {
  name: 'Въезд',
  stream_url: 'rtsp://cam/live',
  capture_every_s: 300,
  zone: null,
}

function setup() {
  setToken('mock-token')
  const client = createTestQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, wrapper }
}

/** Список и три мутации в одном хуке: одна подписка на кэш, без гонок между хуками. */
function useCameraApi(siteId: string) {
  return { list: useCameras(siteId), save: useSaveCamera(siteId), remove: useDeleteCamera(siteId) }
}

describe('camera hooks', () => {
  it('lists the cameras of a site, empty at first', async () => {
    const { wrapper } = setup()
    const { result } = renderHook(() => useCameras(BEREZNIKI), { wrapper })
    await waitFor(() => expect(result.current.data).toEqual([]))
  })

  it('creates a camera, then edits and deletes it', async () => {
    const { wrapper } = setup()
    const { result } = renderHook(() => useCameraApi(BEREZNIKI), { wrapper })
    await waitFor(() => expect(result.current.list.isSuccess).toBe(true))

    let created: { id: string } | undefined
    await act(async () => {
      created = await result.current.save.mutateAsync({ cameraId: null, data: input })
    })
    await waitFor(() => expect(result.current.list.data).toHaveLength(1))
    expect(result.current.list.data?.[0]).toMatchObject({
      name: 'Въезд',
      stream_url: 'rtsp://cam/live',
      capture_every_s: 300,
      zone: null,
      frames_count: 0,
    })

    await act(async () => {
      await result.current.save.mutateAsync({
        cameraId: created!.id,
        data: {
          ...input,
          name: 'Выезд',
          zone: [
            [0, 0],
            [1, 0],
            [0, 1],
          ],
        },
      })
    })
    await waitFor(() => expect(result.current.list.data?.[0]?.name).toBe('Выезд'))
    expect(result.current.list.data?.[0]?.zone).toEqual([
      [0, 0],
      [1, 0],
      [0, 1],
    ])

    await act(async () => {
      await result.current.remove.mutateAsync(created!.id)
    })
    await waitFor(() => expect(result.current.list.data).toEqual([]))
  })

  it('shows the backend reason for a stream link with a wrong scheme', async () => {
    const { wrapper } = setup()
    const { result } = renderHook(() => useCameraApi(BEREZNIKI), { wrapper })
    await act(async () => {
      await expect(
        result.current.save.mutateAsync({
          cameraId: null,
          data: { ...input, stream_url: 'ftp://cam' },
        }),
      ).rejects.toThrow('ссылка на стрим')
    })
  })
})
