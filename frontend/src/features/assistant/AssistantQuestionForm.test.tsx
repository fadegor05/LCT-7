import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AssistantQuestionForm } from './AssistantQuestionForm'

describe('AssistantQuestionForm', () => {
  it('has valid HTML nesting (no div inside p)', async () => {
    const user = userEvent.setup()
    const { container } = render(
      <AssistantQuestionForm pending={false} onSubmit={vi.fn()} onCancel={vi.fn()} />,
    )
    const textarea = screen.getByLabelText('Вопрос по отчёту')
    await user.type(textarea, 'тест')
    await user.click(screen.getByRole('button', { name: 'Спросить' }))
    expect(container.querySelector('p div')).toBeNull()
  })

  it('submits with trimmed text on click', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<AssistantQuestionForm pending={false} onSubmit={onSubmit} onCancel={vi.fn()} />)
    const textarea = screen.getByLabelText('Вопрос по отчёту')
    await user.type(textarea, '  тест  ')
    await user.click(screen.getByRole('button', { name: 'Спросить' }))
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith('тест')
  })

  it('shows error for too short text and does not submit', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<AssistantQuestionForm pending={false} onSubmit={onSubmit} onCancel={vi.fn()} />)
    const textarea = screen.getByLabelText('Вопрос по отчёту')
    await user.type(textarea, '  ab  ')
    await user.click(screen.getByRole('button', { name: 'Спросить' }))
    expect(screen.getByText('Вопрос должен быть от 3 до 500 символов')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('accepts 500 chars but rejects 501', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<AssistantQuestionForm pending={false} onSubmit={onSubmit} onCancel={vi.fn()} />)
    const textarea = screen.getByLabelText('Вопрос по отчёту')

    // 500 chars
    const text500 = 'a'.repeat(500)
    await user.type(textarea, text500)
    await user.click(screen.getByRole('button', { name: 'Спросить' }))
    expect(onSubmit).toHaveBeenCalledWith(text500)

    // Reset and try 501
    onSubmit.mockClear()
    await user.clear(textarea)
    const text501 = 'a'.repeat(501)
    await user.type(textarea, text501)
    await user.click(screen.getByRole('button', { name: 'Спросить' }))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText('Вопрос должен быть от 3 до 500 символов')).toBeInTheDocument()
  })

  it('submits on Enter without shift', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<AssistantQuestionForm pending={false} onSubmit={onSubmit} onCancel={vi.fn()} />)
    const textarea = screen.getByLabelText('Вопрос по отчёту')
    await user.type(textarea, 'тест')
    await user.keyboard('{Enter}')
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith('тест')
    expect(textarea).toHaveValue('тест')
  })

  it('inserts newline on Shift+Enter without submitting', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<AssistantQuestionForm pending={false} onSubmit={onSubmit} onCancel={vi.fn()} />)
    const textarea = screen.getByLabelText('Вопрос по отчёту')
    await user.type(textarea, 'первая')
    await user.keyboard('{Shift>}{Enter}{/Shift}')
    await user.type(textarea, 'вторая')
    expect(textarea).toHaveValue('первая\nвторая')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('does not submit on Enter during IME composition', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<AssistantQuestionForm pending={false} onSubmit={onSubmit} onCancel={vi.fn()} />)
    const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
    if (!(textarea instanceof HTMLTextAreaElement)) {
      throw new Error('Expected textarea element')
    }
    await user.type(textarea, 'тест')

    // Test that Enter during composition does NOT submit
    const composingEvent = new KeyboardEvent('keydown', {
      key: 'Enter',
      isComposing: true,
      bubbles: true,
      cancelable: true,
    })
    fireEvent(textarea, composingEvent)
    expect(onSubmit).not.toHaveBeenCalled()

    // Positive control: plain Enter DOES submit
    const plainEvent = new KeyboardEvent('keydown', {
      key: 'Enter',
      isComposing: false,
      bubbles: true,
      cancelable: true,
    })
    fireEvent(textarea, plainEvent)
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith('тест')
  })

  it('shows counter with trimmed length', async () => {
    const user = userEvent.setup()
    render(<AssistantQuestionForm pending={false} onSubmit={vi.fn()} onCancel={vi.fn()} />)
    const textarea = screen.getByLabelText('Вопрос по отчёту')
    await user.type(textarea, '  abc ')
    expect(screen.getByText('3 / 500')).toBeInTheDocument()
  })

  it('shows error style in counter when over limit', async () => {
    const user = userEvent.setup()
    render(<AssistantQuestionForm pending={false} onSubmit={vi.fn()} onCancel={vi.fn()} />)
    const textarea = screen.getByLabelText('Вопрос по отчёту')
    await user.type(textarea, 'a'.repeat(501))
    const counterText = screen.getByText('501 / 500 — слишком длинный вопрос')
    expect(counterText).toBeInTheDocument()
    expect(counterText.className).toContain('error')
  })

  it('fills textarea on example button click without submitting', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<AssistantQuestionForm pending={false} onSubmit={onSubmit} onCancel={vi.fn()} />)
    const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
    await user.click(screen.getByRole('button', { name: 'где отставание и на сколько' }))
    expect(textarea).toHaveValue('где отставание и на сколько')
    expect(textarea).toHaveFocus()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('fills textarea with second example', async () => {
    const user = userEvent.setup()
    render(<AssistantQuestionForm pending={false} onSubmit={vi.fn()} onCancel={vi.fn()} />)
    const textarea = screen.getByLabelText('Вопрос по отчёту')
    await user.click(screen.getByRole('button', { name: 'что с этой площадкой' }))
    expect(textarea).toHaveValue('что с этой площадкой')
    expect(textarea).toHaveFocus()
  })

  it('disables submit button while pending', () => {
    render(<AssistantQuestionForm pending={true} onSubmit={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Спросить' })).toBeDisabled()
  })

  it('shows Cancel button while pending', () => {
    render(<AssistantQuestionForm pending={true} onSubmit={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Отменить' })).toBeInTheDocument()
  })

  it('calls onCancel when Cancel is clicked', async () => {
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(<AssistantQuestionForm pending={true} onSubmit={vi.fn()} onCancel={onCancel} />)
    await user.click(screen.getByRole('button', { name: 'Отменить' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('makes textarea read-only while pending', () => {
    render(<AssistantQuestionForm pending={true} onSubmit={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByLabelText('Вопрос по отчёту')).toHaveAttribute('readonly')
  })

  it('does not submit on Enter while pending', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(
      <AssistantQuestionForm pending={false} onSubmit={onSubmit} onCancel={vi.fn()} />,
    )
    const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
    if (!(textarea instanceof HTMLTextAreaElement)) {
      throw new Error('Expected textarea element')
    }
    await user.type(textarea, 'тест')

    // Test that Enter while pending does NOT submit
    rerender(<AssistantQuestionForm pending={true} onSubmit={onSubmit} onCancel={vi.fn()} />)
    fireEvent.keyDown(textarea, { key: 'Enter' })
    expect(onSubmit).not.toHaveBeenCalled()

    // Positive control: Enter when not pending DOES submit
    rerender(<AssistantQuestionForm pending={false} onSubmit={onSubmit} onCancel={vi.fn()} />)
    const plainEvent = new KeyboardEvent('keydown', {
      key: 'Enter',
      bubbles: true,
      cancelable: true,
    })
    fireEvent(textarea, plainEvent)
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith('тест')
  })

  it('does not show Cancel button when not pending', () => {
    render(<AssistantQuestionForm pending={false} onSubmit={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.queryByRole('button', { name: 'Отменить' })).not.toBeInTheDocument()
  })

  it('displays error prop from parent', () => {
    render(
      <AssistantQuestionForm
        pending={false}
        error="Сервер недоступен"
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByText('Сервер недоступен')).toBeInTheDocument()
  })
})
