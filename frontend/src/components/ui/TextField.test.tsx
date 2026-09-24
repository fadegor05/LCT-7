import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SelectField } from './SelectField'
import { TextField } from './TextField'

describe('TextField', () => {
  it('links label, hint and value', async () => {
    const onChange = vi.fn()
    render(<TextField label="Название" hint="Подсказка" onChange={onChange} />)
    const input = screen.getByLabelText('Название')
    expect(input).toHaveAccessibleDescription('Подсказка')
    await userEvent.type(input, 'К-5')
    expect(onChange).toHaveBeenCalled()
  })

  it('shows an error instead of the hint', () => {
    render(<TextField label="Название" hint="Подсказка" error="Укажите название" id="f" />)
    const input = screen.getByLabelText('Название')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Укажите название')
    expect(screen.queryByText('Подсказка')).not.toBeInTheDocument()
  })

  it('has no description without hint or error', () => {
    render(<TextField label="Адрес" />)
    expect(screen.getByLabelText('Адрес')).not.toHaveAttribute('aria-describedby')
  })
})

describe('SelectField', () => {
  it('renders options and reports the selection', async () => {
    const onChange = vi.fn()
    render(
      <SelectField
        label="Камера"
        defaultValue="a"
        onChange={onChange}
        options={[
          { value: 'a', label: 'К-1' },
          { value: 'b', label: 'К-2' },
        ]}
      />,
    )
    await userEvent.selectOptions(screen.getByLabelText('Камера'), 'К-2')
    expect(onChange).toHaveBeenCalled()
    expect(screen.getByLabelText('Камера')).toHaveValue('b')
  })
})
