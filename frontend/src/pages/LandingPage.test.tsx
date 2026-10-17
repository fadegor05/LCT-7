import { screen } from '@testing-library/react'
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

  it('sends a signed-in user straight to the sites', async () => {
    renderRoute('/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Стройки' })).toBeInTheDocument()
  })
})
