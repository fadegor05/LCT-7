import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Dialog } from './Dialog'

describe('Dialog', () => {
  it('is a labelled modal that receives focus', () => {
    render(
      <Dialog title="Новая камера" onClose={vi.fn()} footer={<button>Сохранить</button>}>
        <p>тело</p>
      </Dialog>,
    )
    const dialog = screen.getByRole('dialog', { name: 'Новая камера' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Сохранить' })).toBeInTheDocument()
  })

  it('closes by Escape, the close button and the backdrop', async () => {
    const onClose = vi.fn()
    render(
      <Dialog title="Окно" onClose={onClose}>
        <p>тело</p>
      </Dialog>,
    )
    await userEvent.keyboard('{Escape}')
    await userEvent.click(screen.getByRole('button', { name: 'Закрыть' }))
    await userEvent.click(screen.getByRole('presentation'))
    expect(onClose).toHaveBeenCalledTimes(3)
    await userEvent.click(screen.getByText('тело'))
    expect(onClose).toHaveBeenCalledTimes(3)
  })

  it('keeps focus in a field when the parent re-renders with a new onClose', async () => {
    const first = vi.fn()
    const { rerender } = render(
      <Dialog title="Окно" onClose={first}>
        <input aria-label="Поле" />
      </Dialog>,
    )
    await userEvent.click(screen.getByRole('textbox', { name: 'Поле' }))

    const second = vi.fn()
    rerender(
      <Dialog title="Окно" onClose={second}>
        <input aria-label="Поле" />
      </Dialog>,
    )

    expect(screen.getByRole('textbox', { name: 'Поле' })).toHaveFocus()
    await userEvent.keyboard('{Escape}')
    expect(second).toHaveBeenCalledTimes(1)
    expect(first).not.toHaveBeenCalled()
  })
})
