import { render } from '@testing-library/react'
import { Icon } from './Icon'

describe('Icon', () => {
  it('is decorative and sized', () => {
    const { container } = render(<Icon name="camera" size={14} className="x" />)
    const svg = container.querySelector('svg')!
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg).toHaveAttribute('width', '14')
    expect(svg).toHaveClass('x')
    expect(svg.childElementCount).toBeGreaterThan(0)
  })
})
