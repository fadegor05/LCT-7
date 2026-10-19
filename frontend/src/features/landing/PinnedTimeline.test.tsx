import { fireEvent, render, screen, within } from '@testing-library/react'
import { PinnedTimeline } from './PinnedTimeline'
import { STEPS } from './demo/timeline'

/** Секция высотой 4000 px в окне 800 px: прогресс равен смещению вверх, делённому на 3200. */
function scrollTo(progress: number) {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    top: -progress * 3200,
    height: 4000,
  } as DOMRect)
  fireEvent.scroll(window)
}

function media(wide: boolean, reduce = false) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((q: string) => ({
      matches: q.includes('reduce') ? reduce : wide,
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  )
}

beforeEach(() => {
  vi.stubGlobal('innerHeight', 800)
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
    cb(0)
    return 1
  })
})

afterEach(() => vi.unstubAllGlobals())

describe('PinnedTimeline', () => {
  it('starts on the plan: step one, no photo lit yet', () => {
    media(true)
    const { container } = render(<PinnedTimeline />)
    expect(screen.getByText(/Шаг 1 из 5/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: STEPS[0]!.title })).toBeInTheDocument()
    expect(container.querySelectorAll('.cardOn')).toHaveLength(0)
    expect(container.querySelector('.cursor')).not.toBeInTheDocument()
  })

  it('moves the cut line and lights up the photos while scrolling', () => {
    media(true)
    const { container } = render(<PinnedTimeline />)
    scrollTo(0.6)
    expect(screen.getByText(/Шаг 3 из 5/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: STEPS[2]!.title })).toBeInTheDocument()
    expect(container.querySelectorAll('.cardOn')).toHaveLength(2)
    expect(container.querySelector('.cursor')?.textContent).toMatch(/срез \d{2}\.\d{2}\.2023/)
    expect(container.querySelector('.lag')).toBeInTheDocument()
    expect(screen.getByText('Отставание 14–43 дня')).toBeInTheDocument()
    expect(screen.queryByText('Не начат')).toBeNull()
  })

  it('ends on the limits with the status of the second stage', () => {
    media(true)
    const { container } = render(<PinnedTimeline />)
    scrollTo(1)
    expect(screen.getByText(/Шаг 5 из 5/)).toBeInTheDocument()
    expect(screen.getByText('Не начат')).toBeInTheDocument()
    expect(container.querySelectorAll('.cardOn')).toHaveLength(3)
    expect(screen.getByText(/не доказывает, что работы не ведутся/)).toBeInTheDocument()
  })

  it('shows the same story as a plain list on a phone', () => {
    media(false)
    render(<PinnedTimeline />)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(STEPS.length)
    expect(within(items[2]!).getByRole('img')).toHaveAttribute('src', '/landing/p03/piles-1.jpg')
    expect(within(items[3]!).getByRole('img')).toHaveAttribute('src', '/landing/p03/sheet-1.jpg')
    expect(screen.queryByText(/Шаг 1 из 5/)).toBeNull()
  })

  it('does not pin when the system asks for less motion', () => {
    media(true, true)
    render(<PinnedTimeline />)
    expect(screen.getAllByRole('listitem')).toHaveLength(STEPS.length)
  })
})
