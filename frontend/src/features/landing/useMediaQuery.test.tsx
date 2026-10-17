import { act, render, screen } from '@testing-library/react'
import { useMediaQuery } from './useMediaQuery'

function Probe() {
  return <p>{useMediaQuery('(width >= 1100px)') ? 'wide' : 'narrow'}</p>
}

afterEach(() => vi.unstubAllGlobals())

describe('useMediaQuery', () => {
  it('follows the media query and unsubscribes on unmount', () => {
    let listener = () => {}
    const remove = vi.fn()
    const list = {
      matches: true,
      addEventListener: (_: string, cb: () => void) => (listener = cb),
      removeEventListener: remove,
    }
    vi.stubGlobal('matchMedia', () => list)
    const { unmount } = render(<Probe />)
    expect(screen.getByText('wide')).toBeInTheDocument()
    list.matches = false
    act(() => listener())
    expect(screen.getByText('narrow')).toBeInTheDocument()
    unmount()
    expect(remove).toHaveBeenCalled()
  })

  it('assumes the query holds where matchMedia is missing', () => {
    vi.stubGlobal('matchMedia', undefined)
    render(<Probe />)
    expect(screen.getByText('wide')).toBeInTheDocument()
  })
})
