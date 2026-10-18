import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DEMO_FINDINGS } from './demo/p03'
import { LiveDemo } from './LiveDemo'

const list = () => screen.getByRole('list', { name: 'Выводы по площадке' })

describe('LiveDemo', () => {
  it('opens the first finding with the frame, the rule and the limits', () => {
    render(<LiveDemo />)
    const card = screen.getByRole('article', { name: 'Карточка: Устройство свай' })
    expect(within(card).getByText('Ожидалось по правилу')).toBeInTheDocument()
    expect(within(card).getByText(/ГЭСН 05-01-028-01/)).toBeInTheDocument()
    expect(within(card).getByText('Чего это не доказывает.')).toBeInTheDocument()
    expect(within(card).getAllByRole('img').length).toBe(2)
    expect(within(card).getByText(/Буровая установка 0\.91/)).toBeInTheDocument()
    expect(within(card).getByText('Критично')).toBeInTheDocument()
    expect(within(list()).getAllByRole('button')).toHaveLength(DEMO_FINDINGS.length)
  })

  it('switches the card on click and marks hypotheses', async () => {
    const user = userEvent.setup()
    render(<LiveDemo />)
    await user.click(within(list()).getByRole('button', { name: /Ограждение котлована: шпунт/ }))
    const sheet = screen.getByRole('article', { name: /шпунт/ })
    expect(within(sheet).getByText(/Отсутствие техники в кадре не доказывает/)).toBeInTheDocument()

    await user.click(within(list()).getByRole('button', { name: /Лишняя техника/ }))
    const extra = screen.getByRole('article', { name: /Лишняя техника/ })
    expect(within(extra).getByText('Гипотеза')).toBeInTheDocument()
    expect(within(extra).getByText('Внимание')).toBeInTheDocument()
    expect(within(extra).getByText(/Уверенность: Низкая/)).toBeInTheDocument()
  })

  it('moves between findings with the arrow keys', async () => {
    const user = userEvent.setup()
    render(<LiveDemo />)
    const [first, second, third] = within(list()).getAllByRole('button')
    first!.focus()
    await user.keyboard('{ArrowDown}')
    expect(second).toHaveFocus()
    expect(second).toHaveAttribute('aria-pressed', 'true')
    await user.keyboard('{ArrowUp}{ArrowUp}')
    expect(third).toHaveFocus()
    expect(third).toHaveAttribute('aria-pressed', 'true')
    await user.keyboard('{Tab}')
    expect(first).not.toHaveFocus()
  })
})
