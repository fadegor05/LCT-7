import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderRoute } from '@/test/render'

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

  it('привязка открывает ссылку и показывает канал привязанным', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { user } = renderRoute('/profile')
    await screen.findByRole('button', { name: 'Привязать' })

    await user.click(screen.getByRole('button', { name: 'Привязать' }))

    await waitFor(() => expect(open).toHaveBeenCalled())
    expect(await screen.findByText('…6789')).toBeInTheDocument()
    open.mockRestore()
  })

  it('тумблер выключает доставку', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { user } = renderRoute('/profile')
    await user.click(await screen.findByRole('button', { name: 'Привязать' }))
    const toggle = await screen.findByRole('checkbox', { name: 'Слать сюда' })

    await user.click(toggle)

    await waitFor(() => expect(toggle).not.toBeChecked())
    open.mockRestore()
  })

  it('отвязка убирает канал', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { user } = renderRoute('/profile')
    await user.click(await screen.findByRole('button', { name: 'Привязать' }))
    await screen.findByText('…6789')

    await user.click(screen.getByRole('button', { name: 'Отвязать' }))

    expect(await screen.findByRole('button', { name: 'Привязать' })).toBeInTheDocument()
    open.mockRestore()
  })
})
