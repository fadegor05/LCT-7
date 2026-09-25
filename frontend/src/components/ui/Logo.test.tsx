import { render } from '@testing-library/react'
import { Logo } from './Logo'

describe('Logo', () => {
  it('is decorative and sized', () => {
    const { container } = render(<Logo size={32} className="x" />)
    const svg = container.querySelector('svg')!
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg).toHaveAttribute('width', '32')
    expect(svg).toHaveClass('x')
    expect(svg.querySelectorAll('rect')).toHaveLength(4)
  })
})
