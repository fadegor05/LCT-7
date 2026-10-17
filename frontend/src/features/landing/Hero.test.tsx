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
})
