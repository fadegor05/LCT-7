import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { Hero } from './Hero'

describe('Hero', () => {
  it('names the result in one headline and leads to the example', () => {
    render(
      <MemoryRouter>
        <Hero />
      </MemoryRouter>,
    )
    expect(
      screen.getByRole('heading', { level: 1, name: 'Видно, где стройка отстаёт от графика' }),
    ).toBeInTheDocument()
    expect(screen.queryByText('не нужен')).toBeNull()
    expect(screen.queryByText(/Контроль строительства по снимкам/)).toBeNull()
    expect(screen.getByRole('link', { name: 'Посмотреть пример' })).toHaveAttribute(
      'href',
      '#timeline',
    )
  })

  it('shows the overview of p03 with the same statuses as the product', () => {
    render(
      <MemoryRouter>
        <Hero />
      </MemoryRouter>,
    )
    const window = screen.getByRole('img', { name: /Экран «Обзор» Вехи/ })
    expect(
      within(window).getByText('Отставание 14–43 дня', { selector: 'strong' }),
    ).toBeInTheDocument()
    expect(within(window).getByText('Не начат')).toBeInTheDocument()
    expect(within(window).getByText('Устройство свай')).toBeInTheDocument()
    expect(within(window).getByText('snmpsh.ru / sites / p03')).toBeInTheDocument()
  })

  it('shows the crane only on a wide screen and hides it from screen readers', () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn((q: string) => ({ matches: q.includes('1100px') })),
    )
    const { container, unmount } = render(
      <MemoryRouter>
        <Hero />
      </MemoryRouter>,
    )
    const scene = container.querySelector('[data-layer="crane"]')?.closest('svg')
    expect(scene).toHaveAttribute('aria-hidden', 'true')
    unmount()

    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: false })),
    )
    const view = render(
      <MemoryRouter>
        <Hero />
      </MemoryRouter>,
    )
    expect(view.container.querySelector('[data-layer="crane"]')).toBeNull()
    vi.unstubAllGlobals()
  })
})
