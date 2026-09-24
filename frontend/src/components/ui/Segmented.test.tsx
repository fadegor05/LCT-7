import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Segmented } from './Segmented'

const options = [
  { value: 'a', label: 'Первый' },
  { value: 'b', label: 'Второй' },
] as const

describe('Segmented', () => {
  it('marks the selected option and reports changes', async () => {
    const onChange = vi.fn()
    render(<Segmented label="Выбор" options={options} value="a" onChange={onChange} />)
    expect(screen.getByRole('group', { name: 'Выбор' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Первый' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Второй' })).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(screen.getByRole('button', { name: 'Второй' }))
    expect(onChange).toHaveBeenCalledWith('b')
  })

  it('can be disabled', () => {
    render(<Segmented label="Выбор" options={options} value="a" onChange={vi.fn()} disabled />)
    expect(screen.getByRole('button', { name: 'Второй' })).toBeDisabled()
  })
})
