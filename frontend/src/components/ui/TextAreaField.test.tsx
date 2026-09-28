import { render, screen } from '@testing-library/react'
import { TextAreaField } from './TextAreaField'

describe('TextAreaField', () => {
  it('links label, hint and value', () => {
    render(<TextAreaField label="Описание" hint="Подсказка" />)
    const textarea = screen.getByLabelText('Описание')
    expect(textarea).toHaveAccessibleDescription('Подсказка')
  })

  it('shows an error instead of the hint', () => {
    render(<TextAreaField label="Описание" hint="Подсказка" error="Укажите описание" id="f" />)
    const textarea = screen.getByLabelText('Описание')
    expect(textarea).toHaveAttribute('aria-invalid', 'true')
    expect(textarea).toHaveAccessibleDescription('Укажите описание')
    expect(screen.queryByText('Подсказка')).not.toBeInTheDocument()
  })

  it('has no description without hint or error', () => {
    render(<TextAreaField label="Текст" />)
    expect(screen.getByLabelText('Текст')).not.toHaveAttribute('aria-describedby')
  })
})
