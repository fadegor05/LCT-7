import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { AuthBackdrop } from './AuthBackdrop'
import { afterBackdrop, cellSize, setBackdropProgress, signalBackdrop } from './backdrop'

/** Детерминированный генератор вместо Math.random. */
function seeded(seed = 1) {
  let s = seed
  return () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
}

class FakeObserver {
  static last: FakeObserver | null = null
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
  constructor(readonly callback: ResizeObserverCallback) {
    FakeObserver.last = this
  }
  fire() {
    this.callback([], this)
  }
}

let size = { width: 960, height: 640 }
let hidden = false
let frames = new Map<number, FrameRequestCallback>()
let images: HTMLImageElement[] = []
const imageProps = ['complete', 'naturalWidth'] as const
const originalImageProps = imageProps.map((p) =>
  Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, p),
)

/** Canvas, кадры анимации, размеры и картинки — всё, чего нет в jsdom. */
function setup({ reduced = false, resizeObserver = true } = {}) {
  const ctx = {
    setTransform: vi.fn(),
    clearRect: vi.fn(),
    drawImage: vi.fn(),
    fillRect: vi.fn(),
    globalAlpha: 1,
    fillStyle: '',
  }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx as never)
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(
    () =>
      ({ ...size, x: 0, y: 0, top: 0, left: 0, right: size.width, bottom: size.height }) as DOMRect,
  )
  vi.spyOn(Math, 'random').mockImplementation(seeded(5))

  const motion = {
    matches: reduced,
    listener: null as null | (() => void),
    addEventListener: vi.fn((_: string, l: () => void) => (motion.listener = l)),
    removeEventListener: vi.fn(),
  }
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => motion),
  )

  let id = 0
  const requestFrame = vi.fn((cb: FrameRequestCallback) => {
    frames.set(++id, cb)
    return id
  })
  const cancelFrame = vi.fn((handle: number) => frames.delete(handle))
  vi.stubGlobal('requestAnimationFrame', requestFrame)
  vi.stubGlobal('cancelAnimationFrame', cancelFrame)
  vi.stubGlobal('ResizeObserver', resizeObserver ? FakeObserver : undefined)

  const RealImage = Image
  vi.stubGlobal(
    'Image',
    vi.fn(function () {
      const img = new RealImage()
      images.push(img)
      return img
    }),
  )

  return { ctx, motion, requestFrame, cancelFrame }
}

/** Прокручивает кадры анимации с шагом `stepMs`. */
function runFrames(count: number, stepMs = 450) {
  let t = performance.now() + stepMs
  for (let i = 0; i < count; i++) {
    const due = [...frames.values()]
    frames.clear()
    for (const cb of due) cb(t)
    t += stepMs
  }
}

beforeEach(() => {
  size = { width: 960, height: 640 }
  hidden = false
  frames = new Map()
  images = []
  FakeObserver.last = null
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden })
  Object.defineProperty(HTMLImageElement.prototype, 'complete', {
    configurable: true,
    get: () => true,
  })
  Object.defineProperty(HTMLImageElement.prototype, 'naturalWidth', {
    configurable: true,
    get: () => 96,
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  Reflect.deleteProperty(document, 'hidden')
  imageProps.forEach((p, i) => {
    const original = originalImageProps[i]
    if (original) Object.defineProperty(HTMLImageElement.prototype, p, original)
    else Reflect.deleteProperty(HTMLImageElement.prototype, p)
  })
})

describe('cellSize', () => {
  it('matches the input height on wide screens and shrinks on narrow ones', () => {
    expect(cellSize(1440)).toBe(48)
    expect(cellSize(700)).toBe(40)
    expect(cellSize(375)).toBe(32)
  })
})

describe('AuthBackdrop', () => {
  it('renders a decorative canvas and stays idle without canvas support', () => {
    const { container } = render(<AuthBackdrop />)
    const canvas = container.querySelector('canvas')
    expect(canvas).toHaveAttribute('aria-hidden', 'true')
    expect(canvas!.width).toBe(300)
  })

  it('starts with a stack and keeps dropping machines', () => {
    const { ctx, requestFrame } = setup()
    const { container } = render(<AuthBackdrop />)
    expect(container.querySelector('canvas')!.width).toBe(960)
    expect(ctx.drawImage).toHaveBeenCalled()
    expect(images).toHaveLength(7)
    expect(requestFrame).toHaveBeenCalledTimes(1)

    runFrames(3000)
    // Ряды заполняются и вспыхивают акцентом перед исчезновением.
    expect(ctx.fillRect).toHaveBeenCalled()
    expect(ctx.globalAlpha).toBe(1)
  })

  it('draws a still stack when the system asks for less motion', () => {
    const { ctx, motion, requestFrame, cancelFrame } = setup({ reduced: true })
    render(<AuthBackdrop />)
    expect(requestFrame).not.toHaveBeenCalled()
    const calls = ctx.drawImage.mock.calls.length
    expect(calls).toBeGreaterThan(0)

    images[0]!.onload?.(new Event('load'))
    expect(ctx.drawImage.mock.calls.length).toBeGreaterThan(calls)

    motion.matches = false
    motion.listener?.()
    expect(requestFrame).toHaveBeenCalledTimes(1)

    motion.matches = true
    motion.listener?.()
    expect(cancelFrame).toHaveBeenCalled()
  })

  it('pauses on a hidden tab and resumes when it is shown again', () => {
    const { requestFrame, cancelFrame } = setup()
    render(<AuthBackdrop />)
    hidden = true
    document.dispatchEvent(new Event('visibilitychange'))
    expect(cancelFrame).toHaveBeenCalled()
    hidden = false
    document.dispatchEvent(new Event('visibilitychange'))
    expect(requestFrame).toHaveBeenCalledTimes(2)
  })

  it('rebuilds the well when the page is resized', () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    setup()
    const { container } = render(<AuthBackdrop />)
    const canvas = container.querySelector('canvas')!

    FakeObserver.last!.fire()
    vi.advanceTimersByTime(200)
    expect(canvas.width).toBe(960)

    size = { width: 375, height: 700 }
    FakeObserver.last!.fire()
    vi.advanceTimersByTime(200)
    expect(canvas.width).toBe(375)
    expect(canvas.height).toBe(700)
  })

  it('falls back to the window resize event without ResizeObserver', () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    setup({ resizeObserver: false })
    const { container } = render(<AuthBackdrop />)
    size = { width: 700, height: 500 }
    window.dispatchEvent(new Event('resize'))
    vi.advanceTimersByTime(200)
    expect(container.querySelector('canvas')!.width).toBe(700)
  })

  it('answers typing, submit, errors and success', () => {
    const { ctx } = setup()
    render(
      <form aria-label="Вход">
        <AuthBackdrop />
        <input aria-label="Логин" />
      </form>,
    )
    runFrames(10)
    const input = screen.getByLabelText('Логин')
    fireEvent.input(input, { target: { value: 'i' } })
    fireEvent.submit(screen.getByRole('form', { name: 'Вход' }))
    act(() => signalBackdrop('error'))
    runFrames(5)
    expect(ctx.fillRect).toHaveBeenCalled()

    const before = ctx.drawImage.mock.calls.length
    act(() => signalBackdrop('success'))
    runFrames(3, 300)
    // Стопка погасла волной, затем строится заново каскадом.
    runFrames(20, 300)
    expect(ctx.drawImage.mock.calls.length).toBeGreaterThan(before)
  })

  it('fades and slows down while a field has focus', async () => {
    setup()
    const { container } = render(
      <div>
        <AuthBackdrop />
        <input aria-label="Пароль" />
      </div>,
    )
    const canvas = container.querySelector('canvas')!
    act(() => screen.getByLabelText('Пароль').focus())
    expect(canvas.dataset.calm).toBe('true')
    act(() => screen.getByLabelText('Пароль').blur())
    await waitFor(() => expect(canvas.dataset.calm).toBe('false'))
  })

  it('builds the registration site field by field', () => {
    const { ctx } = setup()
    render(<AuthBackdrop mode="build" />)
    runFrames(10)
    const before = ctx.drawImage.mock.calls.length
    runFrames(5)
    const idle = ctx.drawImage.mock.calls.length - before

    act(() => setBackdropProgress(4))
    runFrames(5)
    const grown = ctx.drawImage.mock.calls.length - before - idle
    // Четыре слоя сверху фундамента: за те же кадры рисуется больше клеток.
    expect(grown).toBeGreaterThan(idle)
    act(() => setBackdropProgress(2))
    runFrames(2)
  })

  it('builds the registration site at once when motion is reduced', () => {
    const { ctx } = setup({ reduced: true })
    render(<AuthBackdrop mode="build" />)
    const before = ctx.drawImage.mock.calls.length
    act(() => setBackdropProgress(3))
    expect(ctx.drawImage.mock.calls.length).toBeGreaterThan(before)
  })

  it('lets the page navigate after the success wave', () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const navigate = vi.fn()
    afterBackdrop(navigate)
    expect(navigate).toHaveBeenCalledTimes(1)

    setup()
    render(<AuthBackdrop />)
    const later = vi.fn()
    afterBackdrop(later)
    expect(later).not.toHaveBeenCalled()
    vi.advanceTimersByTime(700)
    expect(later).toHaveBeenCalled()
  })

  it('shows the demo controls only with ?demo in development', () => {
    const { unmount } = render(<AuthBackdrop />)
    expect(screen.queryByRole('group', { name: 'Демо эффектов фона' })).not.toBeInTheDocument()
    unmount()

    window.history.pushState({}, '', '/login?demo')
    render(<AuthBackdrop />)
    expect(screen.getByRole('group', { name: 'Демо эффектов фона' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Успех' }))
    fireEvent.click(screen.getByRole('button', { name: 'Ошибка' }))
    window.history.pushState({}, '', '/')
  })

  it('stops the animation and listeners on unmount', () => {
    const { cancelFrame, motion } = setup()
    const { unmount } = render(<AuthBackdrop />)
    const observer = FakeObserver.last!
    unmount()
    expect(cancelFrame).toHaveBeenCalled()
    expect(observer.disconnect).toHaveBeenCalled()
    expect(motion.removeEventListener).toHaveBeenCalled()
  })
})
