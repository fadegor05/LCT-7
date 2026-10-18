import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test/render'
import { createTestNotification } from '@/mocks/db'
import { server } from '@/mocks/server'
import { NotificationBell } from './NotificationBell'

describe('NotificationBell', () => {
  it('без непрочитанных бейджа нет', async () => {
    renderWithProviders(<NotificationBell />)

    await waitFor(() => expect(screen.getByRole('button', { name: /Уведомления/ })).toBeEnabled())
    expect(screen.queryByTestId('unread-badge')).not.toBeInTheDocument()
  })

  it('показывает число непрочитанных', async () => {
    createTestNotification({ title: 'Первое' })
    createTestNotification({ title: 'Второе' })
    renderWithProviders(<NotificationBell />)

    await waitFor(() => expect(screen.getByTestId('unread-badge')).toHaveTextContent('2'))
  })

  it('открытие шторки гасит бейдж, но оставляет пометки «новое»', async () => {
    createTestNotification({ title: 'Отклонение на объекте' })
    const { user } = renderWithProviders(<NotificationBell />)
    expect(await screen.findByTestId('unread-badge')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Уведомления/ }))

    expect(await screen.findByText('Отклонение на объекте')).toBeInTheDocument()
    expect(screen.getByText('новое')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByTestId('unread-badge')).not.toBeInTheDocument())
  })

  it('после закрытия и повторного открытия пометок «новое» нет', async () => {
    createTestNotification({ title: 'Отклонение на объекте' })
    const { user } = renderWithProviders(<NotificationBell />)
    expect(await screen.findByTestId('unread-badge')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Уведомления/ }))
    await screen.findByText('новое')
    await user.click(screen.getByRole('button', { name: 'Закрыть' }))
    await user.click(screen.getByRole('button', { name: /Уведомления/ }))

    expect(await screen.findByText('Отклонение на объекте')).toBeInTheDocument()
    expect(screen.queryByText('новое')).not.toBeInTheDocument()
  })

  it('уведомление, пришедшее после последнего опроса, тоже помечено «новым»', async () => {
    // staleTime и refetchInterval равны 30 с, поэтому открытие шторки рисует
    // кэш. Если снимок непрочитанных снять с него, то уведомление, созданное
    // после последнего опроса, будет помечено прочитанным на сервере и при этом
    // покажется без пометки «новое» — ровно то, ради чего шторка существует.
    createTestNotification({ title: 'Старое' })
    const { user } = renderWithProviders(<NotificationBell />)
    await waitFor(() => expect(screen.getByTestId('unread-badge')).toHaveTextContent('1'))

    // Пришло уже после опроса, клиент о нём ещё не знает
    createTestNotification({ title: 'Свежее' })

    await user.click(screen.getByRole('button', { name: /Уведомления/ }))

    expect(await screen.findByText('Свежее')).toBeInTheDocument()
    expect(screen.getAllByText('новое')).toHaveLength(2)
  })

  it('пустая лента не шлёт запрос на пометку прочитанным', async () => {
    // Review Focus 5: помечать нечего, лишний POST не нужен
    let readCalls = 0
    server.use(
      http.post('/api/notifications/read', () => {
        readCalls += 1
        return HttpResponse.json({ marked: 0 })
      }),
    )
    const { user } = renderWithProviders(<NotificationBell />)
    await waitFor(() => expect(screen.getByRole('button', { name: /Уведомления/ })).toBeEnabled())

    await user.click(screen.getByRole('button', { name: /Уведомления/ }))
    await screen.findByText('Пока ничего не произошло')

    expect(readCalls).toBe(0)
  })

  it('пустая лента: шторка показывает заглушку', async () => {
    /** Review Focus 5. */
    const { user } = renderWithProviders(<NotificationBell />)

    await user.click(screen.getByRole('button', { name: /Уведомления/ }))

    expect(await screen.findByText('Пока ничего не произошло')).toBeInTheDocument()
  })
})
