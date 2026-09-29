import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ParseModeSwitch } from './ParseModeSwitch'

describe('ParseModeSwitch', () => {
  it('marks the current mode and reports the picked one', async () => {
    const onChange = vi.fn()
    render(<ParseModeSwitch value="auto" onChange={onChange} />)
    expect(screen.getByRole('button', { name: 'Авто' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'LLM' }))
    expect(onChange).toHaveBeenCalledWith('llm')
  })

  it('describes the selected mode and can be disabled', () => {
    render(<ParseModeSwitch value="builtin" onChange={() => {}} disabled />)
    expect(screen.getByTestId('parse-mode-hint')).toHaveTextContent('Только встроенный разбор')
    expect(screen.getByRole('button', { name: 'LLM' })).toBeDisabled()
  })
})
