import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Detection } from '@/api/schemas'
import { DetectionOverlay } from './DetectionOverlay'

const detections: Detection[] = [
  {
    id: 'd1',
    equipment_type_id: 't1',
    equipment_code: 'CRANE',
    equipment_title: 'Кран',
    bbox: [0.1, 0.2, 0.5, 0.6],
    score: 0.91,
    model_version: 'v1',
  },
  {
    id: 'd2',
    equipment_type_id: 't2',
    equipment_code: 'EXCAV',
    equipment_title: 'Экскаватор',
    bbox: [0.6, 0.02, 0.9, 0.4],
    score: 0.5,
    model_version: 'v1',
  },
]

describe('DetectionOverlay', () => {
  it('рендерит рамку с подписью для каждой детекции', () => {
    render(<DetectionOverlay detections={detections} activeId={null} onActive={() => {}} />)

    expect(screen.getByLabelText('Кран, 91%')).toBeInTheDocument()
    expect(screen.getByLabelText('Экскаватор, 50%')).toBeInTheDocument()
  })

  it('наведение на рамку передаёт её id в onActive', async () => {
    const onActive = vi.fn()
    const user = userEvent.setup()
    render(<DetectionOverlay detections={detections} activeId={null} onActive={onActive} />)

    await user.hover(screen.getByLabelText('Кран, 91%'))

    expect(onActive).toHaveBeenCalledWith('d1')
  })

  it('при активной рамке у остальных класс muted и показана подпись активной', () => {
    render(<DetectionOverlay detections={detections} activeId="d1" onActive={() => {}} />)

    expect(screen.getByLabelText('Экскаватор, 50%')).toHaveClass('muted')
    expect(screen.getByLabelText('Кран, 91%')).not.toHaveClass('muted')
    expect(screen.getByText('Кран · 91%')).toBeInTheDocument()
  })

  it('уход курсора с рамки передаёт null в onActive', async () => {
    const onActive = vi.fn()
    const user = userEvent.setup()
    render(<DetectionOverlay detections={detections} activeId={null} onActive={onActive} />)
    const box = screen.getByLabelText('Кран, 91%')

    await user.hover(box)
    await user.unhover(box)

    expect(onActive).toHaveBeenLastCalledWith(null)
  })

  it('без наведения подпись показана у детекции с наибольшей уверенностью', () => {
    render(<DetectionOverlay detections={detections} activeId={null} onActive={() => {}} />)

    expect(screen.getByText('Кран · 91%')).toBeInTheDocument()
    expect(screen.queryByText('Экскаватор · 50%')).not.toBeInTheDocument()
  })

  it('без наведения остальные рамки не приглушены', () => {
    render(<DetectionOverlay detections={detections} activeId={null} onActive={() => {}} />)

    expect(screen.getByLabelText('Кран, 91%')).not.toHaveClass('muted')
    expect(screen.getByLabelText('Экскаватор, 50%')).not.toHaveClass('muted')
  })

  it('у каждой рамки есть светлая подложка, чтобы контур был виден на любом фоне', () => {
    const { container } = render(
      <DetectionOverlay detections={detections} activeId={null} onActive={() => {}} />,
    )

    expect(container.querySelectorAll('rect.halo')).toHaveLength(detections.length)
  })

  it('при наведении подложка чужой рамки приглушается вместе с ней', () => {
    const { container } = render(
      <DetectionOverlay detections={detections} activeId="d2" onActive={() => {}} />,
    )

    const halos = container.querySelectorAll('rect.halo')
    expect(halos[0]).toHaveClass('muted')
    expect(halos[1]).not.toHaveClass('muted')
  })

  it('при наведении подпись переходит к активной рамке', () => {
    render(<DetectionOverlay detections={detections} activeId="d2" onActive={() => {}} />)

    expect(screen.getByText('Экскаватор · 50%')).toBeInTheDocument()
    expect(screen.queryByText('Кран · 91%')).not.toBeInTheDocument()
  })
})
