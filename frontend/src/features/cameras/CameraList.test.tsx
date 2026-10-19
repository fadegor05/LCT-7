import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Camera } from '@/api/schemas'
import { CameraList } from './CameraList'

const camera = (patch: Partial<Camera>): Camera => ({
  id: 'camera-1',
  name: 'Въезд',
  stream_url: 'rtsp://cam/live',
  capture_every_s: 300,
  last_capture_at: null,
  last_capture_error: null,
  zone: null,
  frames_count: 1,
  created_at: '2026-09-01T10:00:00',
  ...patch,
})

describe('CameraList', () => {
  it('shows the stream state of each camera and opens its settings', async () => {
    const onEdit = vi.fn()
    const list = [
      camera({ id: 'a', name: 'Въезд', last_capture_at: '2026-09-18T14:20:00' }),
      camera({
        id: 'b',
        name: 'Склад',
        stream_url: null,
        zone: [
          [0, 0],
          [1, 0],
          [0, 1],
        ],
        frames_count: 3,
      }),
      camera({ id: 'c', name: 'Кран', last_capture_error: 'нет связи' }),
    ]
    render(<CameraList cameras={list} onEdit={onEdit} />)

    const first = screen.getByText('Въезд').closest('li')!
    expect(first).toHaveTextContent('Стрим · снимок')
    expect(first).toHaveTextContent('Зона не задана')
    expect(first).toHaveTextContent('1 кадр')

    const second = screen.getByText('Склад').closest('li')!
    expect(second).toHaveTextContent('Без стрима, только загрузка')
    expect(second).toHaveTextContent('Зона задана')
    expect(second).toHaveTextContent('3 кадра')

    expect(screen.getByText('Стрим недоступен: нет связи')).toBeInTheDocument()

    await userEvent.setup().click(screen.getByRole('button', { name: 'Настроить камеру Склад' }))
    expect(onEdit).toHaveBeenCalledWith(list[1])
  })

  it('shows the last capture time of a UTC timestamp in Moscow time', () => {
    render(
      <CameraList
        cameras={[camera({ last_capture_at: '2026-09-18T07:24:00+00:00' })]}
        onEdit={() => {}}
      />,
    )
    expect(screen.getByText('Въезд').closest('li')!).toHaveTextContent(
      'Стрим · снимок ПТ 18.09.2026 10:24',
    )
  })

  it('shows a stream without a capture yet as set', () => {
    render(<CameraList cameras={[camera({})]} onEdit={() => {}} />)
    expect(screen.getByText('Стрим задан')).toBeInTheDocument()
  })
})
