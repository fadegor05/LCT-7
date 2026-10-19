import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderRoute } from '@/test/render'
import { server } from '@/mocks/server'
import { confirmLink } from '@/mocks/db'

describe('Личный кабинет', () => {
  it('показывает ФИО пользователя', async () => {
    renderRoute('/profile')

    // Поле отрисовано сразу, а значение приходит с ответом /users/me
    const field = await screen.findByLabelText('ФИО')
    await waitFor(() => expect(field).toHaveValue('инженер [ФИО]'))
  })

  it('сохраняет новое ФИО', async () => {
    const { user } = renderRoute('/profile')
    const field = await screen.findByLabelText('ФИО')
    await waitFor(() => expect(field).toHaveValue('инженер [ФИО]'))

    await user.clear(field)
    await user.type(field, 'Иванов И. И.')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))

    // Имя в шапке берётся из того же кэша /users/me
    expect(await screen.findByRole('link', { name: 'Иванов И. И.' })).toBeInTheDocument()
  })

  it('пустое ФИО сохранить нельзя', async () => {
    const { user } = renderRoute('/profile')
    const field = await screen.findByLabelText('ФИО')
    await waitFor(() => expect(field).toHaveValue('инженер [ФИО]'))

    await user.clear(field)

    expect(screen.getByRole('button', { name: 'Сохранить' })).toBeDisabled()
  })

  it('канал не привязан — предлагает привязать', async () => {
    renderRoute('/profile')

    expect(await screen.findByText('Телеграм')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Привязать' })).toBeInTheDocument()
  })

  it('вкладка открывается синхронно по клику, а не после ответа сервера', async () => {
    // Иначе Safari и Firefox считают окно не вызванным пользователем и молча
    // его блокируют: кнопка нажата, не происходит ничего, токен сгорел впустую.
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { user } = renderRoute('/profile')
    await screen.findByRole('button', { name: 'Привязать' })

    await user.click(screen.getByRole('button', { name: 'Привязать' }))

    expect(open.mock.calls[0]?.[0]).toBe('')
    // Адрес бота подставляется в уже открытую вкладку; при блокировке — запасной путь
    await waitFor(() =>
      expect(open.mock.calls.some((call) => String(call[0]).includes('t.me/'))).toBe(true),
    )
    open.mockRestore()
  })

  it('адрес бота подставляется в открытую вкладку, а opener обнуляется', async () => {
    // Обычный путь браузера, который не блокирует окно. opener обнуляем, чтобы
    // открытая страница не могла управлять нашей вкладкой.
    const popup = { location: { href: '' }, opener: {} as unknown, close: vi.fn() }
    const open = vi.spyOn(window, 'open').mockReturnValue(popup as unknown as Window)
    const { user } = renderRoute('/profile')
    await screen.findByRole('button', { name: 'Привязать' })

    await user.click(screen.getByRole('button', { name: 'Привязать' }))

    await waitFor(() => expect(popup.location.href).toContain('t.me/'))
    expect(popup.opener).toBeNull()
    open.mockRestore()
  })

  it('ошибка выдачи ссылки закрывает вкладку и показывает текст сервера', async () => {
    const popup = { location: { href: '' }, opener: {} as unknown, close: vi.fn() }
    const open = vi.spyOn(window, 'open').mockReturnValue(popup as unknown as Window)
    server.use(
      http.post('/api/users/me/channels/telegram/link', () =>
        HttpResponse.json({ detail: 'Канал «телеграм» не настроен на сервере' }, { status: 409 }),
      ),
    )
    const { user } = renderRoute('/profile')
    await screen.findByRole('button', { name: 'Привязать' })

    await user.click(screen.getByRole('button', { name: 'Привязать' }))

    expect(await screen.findByText('Канал «телеграм» не настроен на сервере')).toBeInTheDocument()
    expect(popup.close).toHaveBeenCalled()
    open.mockRestore()
  })

  it('канал появляется сам, когда пользователь нажал Start уже после открытия ссылки', async () => {
    // Главный реальный сценарий: между выдачей ссылки и нажатием «Запустить»
    // проходит время. Если экран не опрашивает список, привязка есть на сервере,
    // а на странице по-прежнему кнопка «Привязать», и подсказки перезагрузить нет.
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { user } = renderRoute('/profile')
    await screen.findByRole('button', { name: 'Привязать' })

    await user.click(screen.getByRole('button', { name: 'Привязать' }))
    await waitFor(() => expect(open).toHaveBeenCalled())
    // Пользователь дошёл до телеграма и нажал «Запустить» — уже после refetch
    confirmLink('telegram')

    expect(await screen.findByText('…6789', undefined, { timeout: 5000 })).toBeInTheDocument()
    open.mockRestore()
  })

  it('тумблер выключает доставку', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { user } = renderRoute('/profile')
    await user.click(await screen.findByRole('button', { name: 'Привязать' }))
    confirmLink('telegram')
    const toggle = await screen.findByRole('checkbox', { name: 'Слать сюда' }, { timeout: 5000 })

    await user.click(toggle)

    await waitFor(() => expect(toggle).not.toBeChecked())
    open.mockRestore()
  })

  it('отвязка убирает канал', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { user } = renderRoute('/profile')
    await user.click(await screen.findByRole('button', { name: 'Привязать' }))
    confirmLink('telegram')
    await screen.findByText('…6789', undefined, { timeout: 5000 })

    await user.click(screen.getByRole('button', { name: 'Отвязать' }))

    expect(await screen.findByRole('button', { name: 'Привязать' })).toBeInTheDocument()
    open.mockRestore()
  })
})
