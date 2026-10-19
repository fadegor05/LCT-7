import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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

  describe('анимация ухода', () => {
    // В jsdom нет Web Animations: подкладываем уход фона, который завершает тест, и
    // бесконечный «спиннер» в содержимом, который ждать нельзя
    function stubExitAnimation() {
      let finish = () => {}
      const finished = new Promise<void>((resolve) => {
        finish = resolve
      })
      const spinner = { finished: new Promise(() => {}), effect: { target: document.body } }
      Element.prototype.getAnimations = vi.fn(function (this: Element) {
        return [{ finished, effect: { target: this } }, spinner] as unknown as Animation[]
      })
      return () => finish()
    }

    afterEach(() => {
      // @ts-expect-error -- убираем заглушку: в jsdom метода нет
      delete Element.prototype.getAnimations
    })

    it('зовёт onClose только после того, как уход доигран', async () => {
      const finish = stubExitAnimation()
      const onClose = vi.fn()
      const user = userEvent.setup()
      render(
        <Drawer title="Уведомления" onClose={onClose}>
          <p>Пусто</p>
        </Drawer>,
      )

      await user.click(screen.getByRole('button', { name: 'Закрыть' }))

      expect(screen.getByRole('presentation')).toHaveAttribute('data-closing')
      expect(onClose).not.toHaveBeenCalled()
      finish()
      await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
    })

    it('повторный Escape во время ухода не зовёт onClose дважды', async () => {
      const finish = stubExitAnimation()
      const onClose = vi.fn()
      const user = userEvent.setup()
      render(
        <Drawer title="Уведомления" onClose={onClose}>
          <p>Пусто</p>
        </Drawer>,
      )

      await user.keyboard('{Escape}')
      await user.keyboard('{Escape}')
      finish()

      await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
    })

    it('не зовёт onClose, если шторку сняли раньше конца анимации', async () => {
      const finish = stubExitAnimation()
      const onClose = vi.fn()
      const user = userEvent.setup()
      const { unmount } = render(
        <Drawer title="Уведомления" onClose={onClose}>
          <p>Пусто</p>
        </Drawer>,
      )

      await user.keyboard('{Escape}')
      unmount()
      finish()
      await Promise.resolve()

      expect(onClose).not.toHaveBeenCalled()
    })
  })
})
