import { render, screen } from '@testing-library/react'
import type { Camera } from '@/api/schemas'
import { CameraList } from './CameraList'

const camera = (patch: Partial<Camera>): Camera => ({
  id: 'camera-1',
  name: 'Кран',
  stream_url: 'rtsp://cam/live',
  capture_every_s: 300,
  last_capture_at: null,
  last_capture_error: null,
  zone: null,
  frames_count: 0,
  created_at: '2026-09-01T10:00:00',
  ...patch,
})

describe('CameraList stream status', () => {
  it('says that captures are not going after three failures in a row', () => {
    render(
      <CameraList
        cameras={[camera({ last_capture_error: 'нет связи', capture_failures: 3 })]}
        onEdit={() => {}}
      />,
    )
    expect(screen.getByText('Стрим недоступен: нет связи')).toBeInTheDocument()
    expect(screen.getByText('Снимки не идут · сбоев подряд: 3')).toBeInTheDocument()
  })

  it('does not call a single failure a stop', () => {
    render(
      <CameraList
        cameras={[camera({ last_capture_error: 'нет связи', capture_failures: 2 })]}
        onEdit={() => {}}
      />,
    )
    expect(screen.getByText('Стрим недоступен: нет связи')).toBeInTheDocument()
    expect(screen.queryByText(/Снимки не идут/)).not.toBeInTheDocument()
  })
})
