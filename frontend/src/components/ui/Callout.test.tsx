import { render, screen } from '@testing-library/react'
import { Callout } from './Callout'
import { Card } from './Card'

describe('Callout', () => {
  it('neutral is a note', () => {
    render(<Callout title="Чего это не доказывает">Текст</Callout>)
    expect(screen.getByRole('note')).toHaveTextContent('Чего это не доказываетТекст')
  })

  it('caution and behind are alerts', () => {
    render(
      <>
        <Callout tone="caution" title="Осторожно" />
        <Callout tone="behind">Ошибка</Callout>
      </>,
    )
    expect(screen.getAllByRole('alert')).toHaveLength(2)
  })
})

describe('Card', () => {
  it('renders the requested element', () => {
    render(
      <Card as="aside" muted aria-label="Панель">
        содержимое
      </Card>,
    )
    const card = screen.getByRole('complementary', { name: 'Панель' })
    expect(card.className).toMatch(/muted/)
  })
})
