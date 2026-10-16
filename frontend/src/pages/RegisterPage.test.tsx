import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { getToken } from '@/lib/authStorage'
import { renderRoute } from '@/test/render'

async function fill(
  user: ReturnType<typeof renderRoute>['user'],
  login: string,
  password: string,
  confirm = password,
) {
  await user.type(screen.getByLabelText(/^логин/i), login)
  await user.type(screen.getByLabelText(/^пароль/i), password)
  await user.type(screen.getByLabelText(/повторите пароль/i), confirm)
  await user.click(screen.getByRole('button', { name: /зарегистрироваться/i }))
}

describe('RegisterPage', () => {
  it('renders the form and a link to login', () => {
    renderRoute('/register', { authed: false })

    expect(screen.getByRole('heading', { name: /регистрация/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /войти/i })).toBeInTheDocument()
  })

  it('login page links to registration', async () => {
    const { user, router } = renderRoute('/login', { authed: false })

    await user.click(screen.getByRole('link', { name: /зарегистрироваться/i }))

    expect(router.state.location.pathname).toBe('/register')
  })

  it('registers, stores the token and opens sites', async () => {
    const { user, router } = renderRoute('/register', { authed: false })

    await fill(user, 'newbie', 'long-enough-password')

    expect(await screen.findByRole('heading', { level: 1, name: /стройки/i })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/sites')
    expect(getToken()).toBe('mock-token')
  })

  it('validates password length and confirmation before sending', async () => {
    const { user } = renderRoute('/register', { authed: false })

    await fill(user, 'newbie', 'short', 'different')

    expect(await screen.findByText(/пароль не короче 8 символов/i)).toBeInTheDocument()
    expect(getToken()).toBe(null)
  })

  it('rejects mismatching passwords', async () => {
    const { user } = renderRoute('/register', { authed: false })

    await fill(user, 'newbie', 'long-enough-password', 'another-long-password')

    expect(await screen.findByText(/пароли не совпадают/i)).toBeInTheDocument()
  })

  it('shows the server error when the login is taken', async () => {
    const { user } = renderRoute('/register', { authed: false })

    await fill(user, 'demo', 'long-enough-password')

    expect(await screen.findByText(/логин уже занят/i)).toBeInTheDocument()
    expect(getToken()).toBe(null)
  })
})
