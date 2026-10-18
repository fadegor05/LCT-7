import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { setToken } from '@/lib/authStorage'
import { env } from '@/lib/env'
import { server } from '@/mocks/server'
import { createTestQueryClient } from '@/test/render'
import { BEREZNIKI } from '@/mocks/fixtures'
import { useCameras, useCaptureNow, useSaveCamera, type CameraInput } from './cameras'

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
  return { wrapper }
}

const captureUrl = (cameraId: string) =>
  `${env.apiBaseUrl}/sites/:siteId/cameras/${cameraId}/capture`

describe('useCaptureNow', () => {
  it('takes a frame from the stream into the camera feed and updates the camera', async () => {
    const { wrapper } = setup()
    const { result: api } = renderHook(
      () => ({ list: useCameras(BEREZNIKI), save: useSaveCamera(BEREZNIKI) }),
      { wrapper },
    )
    await waitFor(() => expect(api.current.list.isSuccess).toBe(true))
    let created: { id: string } | undefined
    await act(async () => {
      created = await api.current.save.mutateAsync({ cameraId: null, data: input })
    })

    const { result: capture } = renderHook(() => useCaptureNow(BEREZNIKI, created!.id), {
      wrapper,
    })
    let photo: { date_source: string | null; captured_on: string | null } | undefined
    await act(async () => {
      photo = await capture.current.mutateAsync()
    })
    expect(photo).toMatchObject({ date_source: 'channel' })
    expect(photo?.captured_on).toMatch(/^\d{4}-\d{2}-\d{2}$/)

    await waitFor(() => expect(api.current.list.data?.[0]?.frames_count).toBe(1))
    expect(api.current.list.data?.[0]).toMatchObject({
      last_capture_error: null,
      capture_failures: 0,
    })
    expect(api.current.list.data?.[0]?.last_capture_at).not.toBeNull()
  })

  it('refuses a camera without a stream link with the backend reason', async () => {
    const { wrapper } = setup()
    const { result: save } = renderHook(() => useSaveCamera(BEREZNIKI), { wrapper })
    let created: { id: string } | undefined
    await act(async () => {
      created = await save.current.mutateAsync({
        cameraId: null,
        data: { ...input, stream_url: null, capture_every_s: null },
      })
    })
    const { result: capture } = renderHook(() => useCaptureNow(BEREZNIKI, created!.id), {
      wrapper,
    })
    await act(async () => {
      await expect(capture.current.mutateAsync()).rejects.toThrow('У камеры нет ссылки на стрим')
    })
  })

  it('shows the reason of a failed grab and keeps it on the camera', async () => {
    const { wrapper } = setup()
    const { result: api } = renderHook(
      () => ({ list: useCameras(BEREZNIKI), save: useSaveCamera(BEREZNIKI) }),
      { wrapper },
    )
    await waitFor(() => expect(api.current.list.isSuccess).toBe(true))
    let created: { id: string } | undefined
    await act(async () => {
      created = await api.current.save.mutateAsync({
        cameraId: null,
        data: { ...input, stream_url: 'rtsp://cam/offline' },
      })
    })
    const { result: capture } = renderHook(() => useCaptureNow(BEREZNIKI, created!.id), {
      wrapper,
    })
    await act(async () => {
      await expect(capture.current.mutateAsync()).rejects.toThrow('Камера не ответила за 15 с')
    })
    await waitFor(() =>
      expect(api.current.list.data?.[0]?.last_capture_error).toBe('Камера не ответила за 15 с'),
    )
    expect(api.current.list.data?.[0]?.capture_failures).toBe(1)
  })

  it('passes the server message of a busy stream (409)', async () => {
    const { wrapper } = setup()
    const { result: save } = renderHook(() => useSaveCamera(BEREZNIKI), { wrapper })
    let created: { id: string } | undefined
    await act(async () => {
      created = await save.current.mutateAsync({ cameraId: null, data: input })
    })
    server.use(
      http.post(captureUrl(created!.id), () =>
        HttpResponse.json({ detail: 'Снимок уже идёт, подождите' }, { status: 409 }),
      ),
    )
    const { result: capture } = renderHook(() => useCaptureNow(BEREZNIKI, created!.id), {
      wrapper,
    })
    await act(async () => {
      await expect(capture.current.mutateAsync()).rejects.toThrow('Снимок уже идёт, подождите')
    })
  })
})
