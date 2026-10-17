import { act, screen } from '@testing-library/react'
import { renderRoute } from '@/test/render'

describe('LandingPage', () => {
  it('explains the product and leads to sign-in and registration', async () => {
    renderRoute('/', { authed: false })
    expect(
      await screen.findByRole('heading', { name: 'Видно, где стройка отстаёт от графика' }),
    ).toBeInTheDocument()
    const signIn = screen.getAllByRole('link', { name: 'Войти' })
    expect(signIn[0]).toHaveAttribute('href', '/login')
    expect(screen.getByRole('link', { name: 'Зарегистрироваться' })).toHaveAttribute(
      'href',
      '/register',
    )
  })

  it('shows the building crane next to the offer', async () => {
    const { container } = renderRoute('/', { authed: false })
    await screen.findByRole('heading', { name: 'Видно, где стройка отстаёт от графика' })
    expect(container.querySelector('[data-layer="crane"]')).toBeInTheDocument()
    expect(container.querySelectorAll('[data-depth]').length).toBeGreaterThan(4)
    // график работ — отдельный блок ниже, а не фон под краном
    expect(screen.getByRole('heading', { name: 'Отставание видно на графике' })).toBeInTheDocument()
  })

  it('moves the sign-in buttons to the top corner once the offer is scrolled past', async () => {
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
    const { container } = renderRoute('/', { authed: false })
    await screen.findByRole('heading', { name: 'Видно, где стройка отстаёт от графика' })
    const floating = () => container.querySelector('[class*="floatCta"]')!
    expect(floating()).toHaveAttribute('aria-hidden', 'true')
    act(() =>
      notify([{ isIntersecting: false, boundingClientRect: { top: -50 } as DOMRectReadOnly }]),
    )
    expect(floating()).toHaveAttribute('aria-hidden', 'false')
    expect(screen.getAllByRole('link', { name: 'Зарегистрироваться' })).toHaveLength(2)
    vi.unstubAllGlobals()
  })

  it('layers the crane scene by depth and explains how to read the schedule', async () => {
    const { container } = renderRoute('/', { authed: false })
    await screen.findByRole('heading', { name: 'Видно, где стройка отстаёт от графика' })
    const depths = [...container.querySelectorAll('svg [data-depth]')].map((n) =>
      n.getAttribute('data-depth'),
    )
    expect(new Set(depths).size).toBeGreaterThan(2)
    expect(screen.getByRole('complementary', { name: 'Как читать график' })).toBeInTheDocument()
  })

  it('lets the schedule peek out and scrolls to it on request', async () => {
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    const { user } = renderRoute('/', { authed: false })
    await user.click(await screen.findByRole('button', { name: /Смотреть график/ }))
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth' })
  })

  it('jumps without animation when the system asks for less motion', async () => {
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    vi.stubGlobal(
      'matchMedia',
      vi.fn((q: string) => ({ matches: q.includes('reduce') || q.includes('width') })),
    )
    const { user } = renderRoute('/', { authed: false })
    await user.click(await screen.findByRole('button', { name: /Смотреть график/ }))
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto' })
    vi.unstubAllGlobals()
  })

  it('keeps only the schedule backdrop on a phone: no crane scene', async () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: false })),
    )
    const { container } = renderRoute('/', { authed: false })
    await screen.findByRole('heading', { name: 'Видно, где стройка отстаёт от графика' })
    expect(container.querySelector('[data-layer="crane"]')).not.toBeInTheDocument()
    expect(container.textContent).toMatch(/сегодня/)
    expect(screen.queryByRole('heading', { name: 'Отставание видно на графике' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Смотреть график/ })).toBeNull()
    vi.unstubAllGlobals()
  })

  it('sends a signed-in user straight to the sites', async () => {
    renderRoute('/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Стройки' })).toBeInTheDocument()
  })
})
