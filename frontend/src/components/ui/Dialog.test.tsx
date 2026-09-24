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
})
