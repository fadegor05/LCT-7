import { act, render } from '@testing-library/react'
import { GanttBackdrop } from './GanttBackdrop'
import { STAGES, dayLabel, stageAt } from './gantt'

const stage = { name: 'Фундамент', start: 0.2, end: 0.4, lag: 0.05 }

describe('stageAt', () => {
  it('follows the plan, falls behind and finishes', () => {
    expect(stageAt(stage, 0.1)).toEqual({ fact: 0.2, state: 'idle' })
    expect(stageAt(stage, 0.23).state).toBe('ontrack')
    expect(stageAt(stage, 0.3)).toEqual({ fact: 0.25, state: 'behind' })
    expect(stageAt(stage, 0.5)).toEqual({ fact: 0.4, state: 'done' })
    expect(stageAt({ ...stage, lag: 0 }, 0.3).state).toBe('ontrack')
  })
})

describe('dayLabel', () => {
  it('names the day and month of the year share', () => {
    expect(dayLabel(0)).toBe('1 января')
    expect(dayLabel(0.5)).toBe('1 июля')
    expect(dayLabel(0.999)).toBe('28 декабря')
  })
})

function stubMedia(matches: (q: string) => boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((q: string) => ({ matches: matches(q) })),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('GanttBackdrop', () => {
  it('draws every stage of the schedule and the today line', () => {
    const { container } = render(<GanttBackdrop />)
    expect(container.firstChild).toHaveAttribute('aria-hidden', 'true')
    expect(container.textContent).toContain(STAGES[0]!.name)
    expect(container.textContent).toMatch(/сегодня · \d+ \S+/)
  })

  it('moves the today line over time', () => {
    vi.useFakeTimers()
    stubMedia(() => false)
    const { container } = render(<GanttBackdrop />)
    const first = container.textContent
    act(() => {
      vi.advanceTimersByTime(6000)
    })
    expect(container.textContent).not.toBe(first)
  })

  it('stays still when the system asks for less motion', () => {
    vi.useFakeTimers()
    stubMedia((q) => q.includes('reduce'))
    const { container } = render(<GanttBackdrop />)
    const first = container.textContent
    act(() => {
      vi.advanceTimersByTime(6000)
    })
    expect(container.textContent).toBe(first)
  })

  it('shifts the layers after the mouse pointer', () => {
    stubMedia((q) => q.includes('pointer: fine'))
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const { container, unmount } = render(<GanttBackdrop />)
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 0, clientY: 0 }))
    for (let i = 0; i < 200 && frames.length; i++) frames.shift()!(0)
    const layer = container.querySelector<HTMLElement>('[data-depth="1"]')!
    expect(layer.style.transform).toMatch(/translate3d\(\d/)
    unmount()
  })
})
