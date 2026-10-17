import { act, render } from '@testing-library/react'
import { ConstructionScene } from './ConstructionScene'
import { TOWER_STAGES } from './scene/timeline'

function stubMedia(matches: (q: string) => boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((q: string) => ({ matches: matches(q) })),
  )
}

/** Прогоняет кадры сцены виртуальным временем: каждый кадр — 50 мс. */
let now = performance.now()
function playFrames(frames: FrameRequestCallback[], seconds: number) {
  for (let i = 0; i < seconds * 20; i++) {
    const cb = frames.shift()
    if (!cb) break
    now += 50
    act(() => cb(now))
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('ConstructionScene', () => {
  it('draws the tower with a label for every stage and is hidden from screen readers', () => {
    stubMedia((q) => q.includes('reduce'))
    const { container } = render(<ConstructionScene />)
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    for (const stage of TOWER_STAGES) expect(container.textContent).toContain(stage.name)
    // без анимации башня собрана целиком: все подписи видны
    const chips = [...container.querySelectorAll('[data-layer="labels"] > g')]
    expect(chips).toHaveLength(TOWER_STAGES.length)
    expect(chips.every((c) => c.getAttribute('opacity') === '1')).toBe(true)
  })

  it('lets the crane lift a block and set it on the tower', () => {
    stubMedia(() => false)
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const { container, unmount } = render(<ConstructionScene />)
    const chips = () => [...container.querySelectorAll('[data-layer="labels"] > g')]
    playFrames(frames, 1)
    expect(chips().every((c) => c.getAttribute('opacity') === '0')).toBe(true)
    // первый блок встаёт на место примерно на 10-й секунде
    for (let i = 0; i < 4 && chips()[0]?.getAttribute('opacity') === '0'; i++) {
      playFrames(frames, 4)
    }
    expect(Number(chips()[0]!.getAttribute('opacity'))).toBeGreaterThan(0)
    expect(chips()[TOWER_STAGES.length - 1]!.getAttribute('opacity')).toBe('0')
    unmount()
    expect(container.querySelectorAll('[data-layer="blocks"] > g')).toHaveLength(0)
  })

  it('runs a whole cycle, fades out and starts over', () => {
    stubMedia(() => false)
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const { container, unmount } = render(<ConstructionScene />)
    const chips = () => [...container.querySelectorAll('[data-layer="labels"] > g')]
    let seen = 0
    for (let i = 0; i < 40 && frames.length; i++) {
      playFrames(frames, 4)
      seen = Math.max(seen, chips().filter((c) => c.getAttribute('opacity') === '1').length)
    }
    expect(seen).toBe(TOWER_STAGES.length)
    unmount()
  })

  it('stops the animation while scrolled out of view and resumes when it returns', () => {
    stubMedia(() => false)
    let notify: (entries: Partial<IntersectionObserverEntry>[]) => void = () => {}
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        constructor(cb: typeof notify) {
          notify = cb
        }
        observe() {}
        disconnect() {}
      },
    )
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const { unmount } = render(<ConstructionScene />)
    playFrames(frames, 0.2)
    act(() => notify([{ isIntersecting: false }]))
    playFrames(frames, 0.2)
    expect(frames).toHaveLength(0)
    act(() => notify([{ isIntersecting: true }]))
    expect(frames).toHaveLength(1)
    unmount()
  })
})
