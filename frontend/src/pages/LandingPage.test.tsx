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
      'Что измерено',
      'Чем Веха отличается от привычного и от продуктов рынка',
      'Кому это нужно',
      'Вопросы, которые обычно задают первыми',
      'Ставится у вас и проверяется вашими людьми',
      'Покажем на вашем графике',
    ])
  })

  it('has no crane and no decorative backdrop any more', async () => {
    const { container } = renderRoute('/', { authed: false })
    await screen.findByRole('heading', { level: 1, name: H1 })
    expect(container.querySelector('[data-layer="crane"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-depth]')).not.toBeInTheDocument()
  })

  it('sends a signed-in user straight to the sites', async () => {
    renderRoute('/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Стройки' })).toBeInTheDocument()
  })
})
