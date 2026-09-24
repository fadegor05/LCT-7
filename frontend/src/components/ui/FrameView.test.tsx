import { render, screen } from '@testing-library/react'
import { FrameView } from './FrameView'

const detection = {
  id: 'd1',
  equipment_class: 'excavator',
  confidence: 0.9,
  bbox_x: 0.1,
  bbox_y: 0.2,
  bbox_w: 0.3,
  bbox_h: 0.4,
}

describe('FrameView', () => {
  it('shows a placeholder, boxes with labels and a caption', () => {
    render(
      <FrameView
        imageUrl={null}
        detections={[detection]}
        classLabel={(c) => (c === 'excavator' ? 'Экскаватор' : c)}
        caption="14:20 К-1"
        alt="Кадр К-1"
      />,
    )
    expect(screen.getByRole('img', { name: 'Кадр К-1' })).toBeInTheDocument()
    expect(screen.getByText('Снимок')).toBeInTheDocument()
    const label = screen.getByText('Экскаватор')
    expect(label.parentElement).toHaveStyle({
      left: '10%',
      top: '20%',
      width: '30%',
      height: '40%',
    })
    expect(screen.getByText('14:20 К-1').tagName).toBe('FIGCAPTION')
  })

  it('uses the image and draws the zone polygon', () => {
    const { container } = render(
      <FrameView
        imageUrl="/frame.jpg"
        zone={[
          [0, 0],
          [1, 0],
          [1, 1],
        ]}
      />,
    )
    expect(screen.getByRole('img', { name: 'Снимок' })).toHaveStyle({
      backgroundImage: 'url(/frame.jpg)',
    })
    expect(screen.queryByText('Снимок')).not.toBeInTheDocument()
    expect(container.querySelector('polygon')).toHaveAttribute('points', '0,0 1,0 1,1')
  })

  it('falls back to the class code as label', () => {
    render(<FrameView imageUrl={null} detections={[detection]} />)
    expect(screen.getByText('excavator')).toBeInTheDocument()
  })
})
