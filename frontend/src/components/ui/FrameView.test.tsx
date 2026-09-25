import { render, screen } from '@testing-library/react'
import { FrameView } from './FrameView'

describe('FrameView', () => {
  it('shows a placeholder and a caption without an image', () => {
    render(<FrameView imageUrl={null} caption="IMG_0001.jpg" alt="Снимок IMG_0001" />)
    expect(screen.getByRole('img', { name: 'Снимок IMG_0001' })).toBeInTheDocument()
    expect(screen.getByText('Снимок')).toBeInTheDocument()
    expect(screen.getByText('IMG_0001.jpg').tagName).toBe('FIGCAPTION')
  })

  it('uses the server-annotated image', () => {
    render(<FrameView imageUrl="/api/sites/s/photos/p/annotated" />)
    expect(screen.getByRole('img', { name: 'Снимок' })).toHaveStyle({
      backgroundImage: 'url(/api/sites/s/photos/p/annotated)',
    })
    expect(screen.queryByText('Снимок')).not.toBeInTheDocument()
  })
})
