import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Drawer } from './Drawer'

describe('Drawer', () => {
  it('показывает заголовок и содержимое', () => {
    render(
      <Drawer title="Уведомления" onClose={vi.fn()}>
        <p>Пусто</p>
      </Drawer>,
    )

    expect(screen.getByRole('dialog', { name: 'Уведомления' })).toBeInTheDocument()
    expect(screen.getByText('Пусто')).toBeInTheDocument()
  })

  it('закрывается по Escape', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Drawer title="Уведомления" onClose={onClose}>
        <p>Пусто</p>
      </Drawer>,
    )

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('закрывается по клику на фон', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Drawer title="Уведомления" onClose={onClose}>
        <p>Пусто</p>
      </Drawer>,
    )

    await user.click(screen.getByRole('presentation'))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('не закрывается по клику внутри панели', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Drawer title="Уведомления" onClose={onClose}>
        <p>Пусто</p>
      </Drawer>,
    )

    await user.click(screen.getByText('Пусто'))

    expect(onClose).not.toHaveBeenCalled()
  })

  it('закрывается кнопкой', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Drawer title="Уведомления" onClose={onClose}>
        <p>Пусто</p>
      </Drawer>,
    )

    await user.click(screen.getByRole('button', { name: 'Закрыть' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
