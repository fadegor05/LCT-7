import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/render'
import { NotificationDrawer } from './NotificationDrawer'

describe('NotificationDrawer: сводка', () => {
  it('«Отправить сводку сейчас» кладёт сводку в ленту', async () => {
    const { user } = renderWithProviders(<NotificationDrawer onClose={() => {}} />)
    expect(await screen.findByText('Пока ничего не произошло')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Отправить сводку сейчас' }))

    expect(await screen.findByText(/Сводка по объектам на/)).toBeInTheDocument()
  })
})
