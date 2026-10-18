import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test/render'
import { createTestNotification } from '@/mocks/db'
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

  it('пустая лента: шторка показывает заглушку', async () => {
    /** Review Focus 5. */
    const { user } = renderWithProviders(<NotificationBell />)

    await user.click(screen.getByRole('button', { name: /Уведомления/ }))

    expect(await screen.findByText('Пока ничего не произошло')).toBeInTheDocument()
  })
})
