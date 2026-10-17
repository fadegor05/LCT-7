import { useRef } from 'react'
import { render, screen } from '@testing-library/react'
import { useCursorParallax } from './useParallax'

function Harness() {
  const root = useRef<HTMLDivElement>(null)
  useCursorParallax(root)
  return (
    <div ref={root}>
      <i data-depth="1" data-testid="near" />
      <i data-depth="0.35" data-testid="far" />
    </div>
  )
}

function stubMedia(matches: (q: string) => boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((q: string) => ({ matches: matches(q) })),
  )
}

afterEach(() => vi.unstubAllGlobals())

function runFrames(frames: FrameRequestCallback[]) {
  for (let i = 0; i < 300 && frames.length; i++) frames.shift()!(0)
}

describe('useCursorParallax', () => {
  it('shifts layers after the mouse pointer, deeper layers further', () => {
    stubMedia((q) => q.includes('pointer: fine'))
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const { unmount } = render(<Harness />)
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 0, clientY: 0 }))
    runFrames(frames)
    const near = screen.getByTestId('near').style.transform
    const far = screen.getByTestId('far').style.transform
    expect(near).toMatch(/translate3d\(\d/)
    expect(parseFloat(near.slice(12))).toBeGreaterThan(parseFloat(far.slice(12)))
    unmount()
  })

  it('cancels a pending frame on unmount', () => {
    stubMedia((q) => q.includes('pointer: fine'))
    const cancel = vi.fn()
    vi.stubGlobal('requestAnimationFrame', () => 7)
    vi.stubGlobal('cancelAnimationFrame', cancel)
    const { unmount } = render(<Harness />)
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 10, clientY: 10 }))
    unmount()
    expect(cancel).toHaveBeenCalledWith(7)
  })

  it('does nothing without a fine pointer or with reduced motion', () => {
    stubMedia(() => false)
    const add = vi.spyOn(window, 'addEventListener')
    render(<Harness />)
    expect(add).not.toHaveBeenCalledWith('pointermove', expect.anything())
    stubMedia((q) => q.includes('pointer: fine') || q.includes('reduce'))
    render(<Harness />)
    expect(add).not.toHaveBeenCalledWith('pointermove', expect.anything())
  })
})
