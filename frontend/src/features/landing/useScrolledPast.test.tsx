import { useRef } from 'react'
import { act, render, screen } from '@testing-library/react'
import { useScrolledPast } from './useScrolledPast'

function Probe() {
  const ref = useRef<HTMLDivElement>(null)
  return (
    <>
      <div ref={ref} />
      <p>{useScrolledPast(ref) ? 'past' : 'visible'}</p>
    </>
  )
}

afterEach(() => vi.unstubAllGlobals())

function stubObserver() {
  let notify: (entries: Partial<IntersectionObserverEntry>[]) => void = () => {}
  const disconnect = vi.fn()
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      constructor(cb: typeof notify) {
        notify = cb
      }
      observe() {}
      disconnect = disconnect
    },
  )
  return { push: (e: Partial<IntersectionObserverEntry>) => act(() => notify([e])), disconnect }
}

describe('useScrolledPast', () => {
  it('is true only once the element has left through the top edge', () => {
    const io = stubObserver()
    const { unmount } = render(<Probe />)
    expect(screen.getByText('visible')).toBeInTheDocument()
    io.push({ isIntersecting: false, boundingClientRect: { top: -40 } as DOMRectReadOnly })
    expect(screen.getByText('past')).toBeInTheDocument()
    io.push({ isIntersecting: false, boundingClientRect: { top: 900 } as DOMRectReadOnly })
    expect(screen.getByText('visible')).toBeInTheDocument()
    io.push({ isIntersecting: true, boundingClientRect: { top: 10 } as DOMRectReadOnly })
    expect(screen.getByText('visible')).toBeInTheDocument()
    unmount()
    expect(io.disconnect).toHaveBeenCalled()
  })

  it('stays false where IntersectionObserver is missing', () => {
    vi.stubGlobal('IntersectionObserver', undefined)
    render(<Probe />)
    expect(screen.getByText('visible')).toBeInTheDocument()
  })
})
