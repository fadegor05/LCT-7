import { screen, within } from '@testing-library/react'
import { renderRoute } from '@/test/render'

const H1 = 'Видно, где стройка отстаёт от графика'

describe('LandingPage', () => {
  it('explains the product and leads to the example, sign-in and registration', async () => {
    renderRoute('/', { authed: false })
    expect(await screen.findByRole('heading', { level: 1, name: H1 })).toBeInTheDocument()
    // главная кнопка ведёт к примеру без регистрации
    expect(screen.getByRole('link', { name: 'Посмотреть пример' })).toHaveAttribute(
      'href',
      '#timeline',
    )
    expect(screen.getByRole('link', { name: 'Попробовать на своём графике' })).toHaveAttribute(
      'href',
      '/register',
    )
    const header = screen.getAllByRole('banner')[0]!
    expect(within(header).getByRole('link', { name: 'Войти' })).toHaveAttribute('href', '/login')
    expect(within(header).getByRole('link', { name: 'Попробовать' })).toHaveAttribute(
      'href',
      '/register',
    )
  })

  it('shows the product window over a real site photo in the first screen', async () => {
    renderRoute('/', { authed: false })
    await screen.findByRole('heading', { level: 1, name: H1 })
    expect(screen.getByRole('img', { name: /Площадка p03, 19 июня 2023/ })).toHaveAttribute(
      'src',
      '/landing/p03/hero.jpg',
    )
    // то же окно продукта стоит и в финальном призыве
    expect(screen.getAllByRole('img', { name: /Экран «Обзор» Вехи/ })).toHaveLength(2)
  })

  it('tells the whole story from context to the final call', async () => {
    renderRoute('/', { authed: false })
    await screen.findByRole('heading', { level: 1, name: H1 })
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(headings).toEqual([
      'Камеры на стройках уже есть. Ответа «идёт ли по графику» нет',
      'Так отставание видно во времени',
      'Три шага от графика до вывода',
      'Посмотрите на настоящем объекте',
      'Вывод всегда можно проверить',
      'Проверили на настоящих стройках',
      'Чем Веха отличается от привычного и от продуктов рынка',
      'Кому это нужно',
      'Вопросы, которые обычно задают первыми',
      'Покажем на вашем графике',
    ])
  })

  it('puts the tower crane next to the headline and a live schedule under the final call', async () => {
    const { container } = renderRoute('/', { authed: false })
    await screen.findByRole('heading', { level: 1, name: H1 })
    expect(container.querySelector('[data-layer="crane"]')).toBeInTheDocument()
    const pilot = screen.getByRole('region', { name: 'Покажем на вашем графике' })
    expect(within(pilot).getByText(/сегодня · \d+ \S+/)).toBeInTheDocument()
  })

  it('uses the design-system buttons and ends without a footer', async () => {
    renderRoute('/', { authed: false })
    await screen.findByRole('heading', { level: 1, name: H1 })
    expect(screen.getByRole('link', { name: 'Посмотреть пример' })).toHaveClass(
      'btn',
      'primary',
      'lg',
    )
    expect(screen.getByRole('link', { name: 'Попробовать самому' })).toHaveClass('btn', 'primary')
    const header = screen.getAllByRole('banner')[0]!
    expect(within(header).getByRole('link', { name: 'Войти' })).toHaveClass('btn', 'ghost', 'sm')
    expect(screen.queryByRole('contentinfo')).toBeNull()
  })

  it('sends a signed-in user straight to the sites', async () => {
    renderRoute('/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Стройки' })).toBeInTheDocument()
  })

  it('keeps a signed-in user on the landing when it is opened from the app logo', async () => {
    renderRoute('/', { authed: true, state: { landing: true } })
    expect(
      await screen.findByRole('heading', { name: 'Видно, где стройка отстаёт от графика' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Войти' })).toBeNull()
    expect(screen.getAllByRole('link', { name: 'К стройкам' })[0]).toHaveAttribute('href', '/sites')
  })

  it('shows sign-in to a guest and no sites link', async () => {
    renderRoute('/', { authed: false })
    await screen.findByRole('heading', { name: 'Видно, где стройка отстаёт от графика' })
    expect(screen.getAllByRole('link', { name: 'Войти' })[0]).toHaveAttribute('href', '/login')
    expect(screen.queryByRole('link', { name: 'К стройкам' })).toBeNull()
  })

  it('opens the landing from the app logo on the sites page', async () => {
    const { user } = renderRoute('/sites')
    await user.click(await screen.findByRole('link', { name: 'Веха' }))
    expect(
      await screen.findByRole('heading', { name: 'Видно, где стройка отстаёт от графика' }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'К стройкам' })[0]).toHaveAttribute('href', '/sites')
  })
})
