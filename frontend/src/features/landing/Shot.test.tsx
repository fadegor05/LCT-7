import { render, screen } from '@testing-library/react'
import { Shot } from './Shot'

describe('Shot', () => {
  it('draws confident finds solid and unsure ones dashed, each with its confidence', () => {
    render(
      <Shot
        src="/landing/p03/piles-1.jpg"
        alt="Площадка"
        boxes={[
          { label: 'Экскаватор', conf: 0.7, box: [0.2, 0.3, 0.4, 0.6] },
          { label: 'Башенный кран', conf: 0.42, box: [0.7, 0.1, 0.8, 0.2] },
        ]}
      />,
    )
    const sure = screen.getByText('Экскаватор 0.70').parentElement!
    const unsure = screen.getByText('Башенный кран 0.42').parentElement!
    expect(sure).toHaveClass('box')
    expect(sure).not.toHaveClass('unsure')
    expect(unsure).toHaveClass('box', 'unsure')
    expect(sure).toHaveStyle({ left: '20%', width: '20%' })
  })
})
