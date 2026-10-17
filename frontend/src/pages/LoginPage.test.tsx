import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { server } from '@/mocks/server'
import { http, HttpResponse } from 'msw'
import { getToken, clearToken } from '@/lib/authStorage'
import { env } from '@/lib/env'
import { renderRoute } from '@/test/render'

describe('LoginPage', () => {
  it('renders login form', () => {
    renderRoute('/login', { authed: false })
    expect(screen.getByRole('heading', { name: /вход/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/логин/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/пароль/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /вход/i })).toBeInTheDocument()
  })

  it('shows error message on failed login', async () => {
    const { user } = renderRoute('/login', { authed: false })
    const loginInput = screen.getByLabelText(/логин/i)
    const passwordInput = screen.getByLabelText(/пароль/i)
    const submitButton = screen.getByRole('button', { name: /вход/i })

    await user.type(loginInput, 'wrong')
    await user.type(passwordInput, 'wrong')
    await user.click(submitButton)

    expect(await screen.findByText(/неверный логин или пароль/i)).toBeInTheDocument()
  })

  it('successful login navigates to sites page', async () => {
    const { user, router } = renderRoute('/login', { authed: false })
    const loginInput = screen.getByLabelText(/логин/i)
    const passwordInput = screen.getByLabelText(/пароль/i)
    const submitButton = screen.getByRole('button', { name: /вход/i })

    await user.type(loginInput, 'demo')
    await user.type(passwordInput, 'demo')
    await user.click(submitButton)

    expect(await screen.findByRole('heading', { level: 1, name: /стройки/i })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/sites')
  })

  it('unauthenticated user opening protected URL lands on login page', () => {
    const { router } = renderRoute('/sites/site-berezniki/observations?date=2026-09-18#section', {
      authed: false,
    })

    expect(screen.getByRole('heading', { name: /вход/i })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('after login, user returns to original URL with query and hash', async () => {
    const { user, router } = renderRoute('/sites/site-berezniki?tab=overview#info', {
      authed: false,
    })

    const loginInput = screen.getByLabelText(/логин/i)
    const passwordInput = screen.getByLabelText(/пароль/i)
    const submitButton = screen.getByRole('button', { name: /вход/i })

    await user.type(loginInput, 'demo')
    await user.type(passwordInput, 'demo')
    await user.click(submitButton)

    // Should navigate to the original URL with query string and hash
    expect(router.state.location.pathname).toBe('/sites/site-berezniki')
    expect(router.state.location.search).toBe('?tab=overview')
    expect(router.state.location.hash).toBe('#info')
  })

  it('logout button clears the token and returns to the landing page', async () => {
    clearToken()
    const { user, router } = renderRoute('/sites', { authed: true })

    // Verify we're on sites page
    expect(await screen.findByRole('heading', { level: 1, name: /стройки/i })).toBeInTheDocument()
    expect(getToken()).toBe('mock-token')

    // Click logout button
    const logoutButton = screen.getByRole('button', { name: /выйти/i })
    await user.click(logoutButton)

    // Токен сброшен, а пользователь на лендинге: сам вышел, поэтому форма входа ему не нужна.
    expect(getToken()).toBe(null)
    expect(localStorage.getItem('lct7.token')).toBe(null)
    await screen.findByRole('heading', { name: 'Видно, где стройка отстаёт от графика' })
    expect(router.state.location.pathname).toBe('/')
  })

  it('401 from a protected request clears the token and sends the user to login', async () => {
    // Токен есть, но сервер его не принимает (просрочен): RequireAuth пропускает, 401 приходит из запроса.
    server.use(
      http.get(`${env.apiBaseUrl}/sites`, () =>
        HttpResponse.json({ detail: 'Требуется авторизация' }, { status: 401 }),
      ),
    )

    renderRoute('/sites', { authed: true })

    expect(await screen.findByRole('heading', { name: /вход/i })).toBeInTheDocument()
    expect(getToken()).toBe(null)
  })
})
