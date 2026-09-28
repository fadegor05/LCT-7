import { render, screen, within } from '@testing-library/react'
import { createRef } from 'react'
import type { AssistantAnswer } from '@/api/schemas'
import { AssistantAnswerView } from './AssistantAnswer'

describe('AssistantAnswerView', () => {
  // Базовая успешная проверка (verified:true)
  it('does not show alert when verified is true', () => {
    const answer: AssistantAnswer = {
      answer: 'Всё хорошо',
      verified: true,
      numbers_not_in_report: [],
      numbers_of_other_site: [],
      limits: 'Это ограничение',
      site_label: 'p1',
      stages: [],
    }
    render(<AssistantAnswerView answer={answer} />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows limits text in document when verified is true', () => {
    const answer: AssistantAnswer = {
      answer: 'Всё хорошо',
      verified: true,
      numbers_not_in_report: [],
      numbers_of_other_site: [],
      limits: 'Это ограничение',
      site_label: 'p1',
      stages: [],
    }
    render(<AssistantAnswerView answer={answer} />)
    expect(screen.getByText('Это ограничение')).toBeInTheDocument()
  })

  it('does not put limits text into title or aria-label attribute when verified', () => {
    const answer: AssistantAnswer = {
      answer: 'Ответ',
      verified: true,
      numbers_not_in_report: [],
      numbers_of_other_site: [],
      limits: 'Это ограничение',
      site_label: 'p1',
      stages: [],
    }
    const { container } = render(<AssistantAnswerView answer={answer} />)
    // Query for any element with title or aria-label containing the limits text
    const allAttrs = container.querySelectorAll('[title], [aria-label]')
    allAttrs.forEach((el) => {
      const title = el.getAttribute('title') || ''
      const ariaLabel = el.getAttribute('aria-label') || ''
      expect(title + ariaLabel).not.toContain('Это ограничение')
    })
  })

  // Невыполненная проверка с обоими списками
  it('shows alert with title and text when verified is false', () => {
    const answer: AssistantAnswer = {
      answer: 'Что-то не так',
      verified: false,
      numbers_not_in_report: ['999'],
      numbers_of_other_site: ['p1: 5'],
      limits: '',
      site_label: 'p1',
      stages: [],
    }
    render(<AssistantAnswerView answer={answer} />)
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Ответ не прошёл проверку')
    expect(alert).toHaveTextContent('Сверьтесь с отчётом: эти числа в нём не найдены.')
  })

  it('shows alert icon when verified is false', () => {
    const answer: AssistantAnswer = {
      answer: 'Что-то не так',
      verified: false,
      numbers_not_in_report: ['999'],
      numbers_of_other_site: [],
      limits: '',
      site_label: 'p1',
      stages: [],
    }
    render(<AssistantAnswerView answer={answer} />)
    const alert = screen.getByRole('alert')
    const icon = alert.querySelector('[data-icon="alert"]')
    expect(icon).toBeInTheDocument()
  })

  it('shows both number lists with captions when verified is false and both are non-empty', () => {
    const answer: AssistantAnswer = {
      answer: 'Что-то не так',
      verified: false,
      numbers_not_in_report: ['999'],
      numbers_of_other_site: ['p1: 5'],
      limits: '',
      site_label: 'p1',
      stages: [],
    }
    render(<AssistantAnswerView answer={answer} />)
    const alert = screen.getByRole('alert')
    expect(within(alert).getByText('Чисел нет в отчёте:')).toBeInTheDocument()
    expect(within(alert).getByText('999')).toBeInTheDocument()
    expect(within(alert).getByText('Числа относятся к другой площадке:')).toBeInTheDocument()
    expect(within(alert).getByText('p1: 5')).toBeInTheDocument()
  })

  it('hides second list caption when only numbers_of_other_site is empty', () => {
    const answer: AssistantAnswer = {
      answer: 'Что-то не так',
      verified: false,
      numbers_not_in_report: ['999'],
      numbers_of_other_site: [],
      limits: '',
      site_label: 'p1',
      stages: [],
    }
    render(<AssistantAnswerView answer={answer} />)
    const alert = screen.getByRole('alert')
    expect(within(alert).getByText('Чисел нет в отчёте:')).toBeInTheDocument()
    expect(within(alert).queryByText('Числа относятся к другой площадке:')).not.toBeInTheDocument()
  })

  it('hides first list caption when only numbers_not_in_report is empty', () => {
    const answer: AssistantAnswer = {
      answer: 'Что-то не так',
      verified: false,
      numbers_not_in_report: [],
      numbers_of_other_site: ['p1: 5'],
      limits: '',
      site_label: 'p1',
      stages: [],
    }
    render(<AssistantAnswerView answer={answer} />)
    const alert = screen.getByRole('alert')
    expect(within(alert).queryByText('Чисел нет в отчёте:')).not.toBeInTheDocument()
    expect(within(alert).getByText('Числа относятся к другой площадке:')).toBeInTheDocument()
  })

  it('shows notice without captions when both lists are empty but verified is false', () => {
    const answer: AssistantAnswer = {
      answer: 'Что-то не так',
      verified: false,
      numbers_not_in_report: [],
      numbers_of_other_site: [],
      limits: '',
      site_label: 'p1',
      stages: [],
    }
    render(<AssistantAnswerView answer={answer} />)
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Ответ не прошёл проверку')
    expect(alert).toHaveTextContent('Сверьтесь с отчётом')
    expect(alert).not.toHaveTextContent('Чисел нет в отчёте')
    expect(alert).not.toHaveTextContent('Числа относятся к другой площадке')
  })

  // Ссылки на этапы
  it('renders links for known stages', () => {
    const answer: AssistantAnswer = {
      answer: 'Этап 3 отстаёт, этап 4 нет, этап 99 нет.',
      verified: true,
      numbers_not_in_report: [],
      numbers_of_other_site: [],
      limits: '',
      site_label: 'p1',
      stages: [
        { ref: 'этап 3', stage_id: 's3' },
        { ref: 'этап 4', stage_id: 's4' },
      ],
    }
    render(<AssistantAnswerView answer={answer} />)
    const link3 = screen.getByRole('link', { name: 'Этап 3' })
    const link4 = screen.getByRole('link', { name: 'этап 4' })
    expect(link3).toHaveAttribute('href', '#stage-s3')
    expect(link4).toHaveAttribute('href', '#stage-s4')
    // этап 99 должен быть простым текстом
    expect(screen.queryByRole('link', { name: /99/ })).not.toBeInTheDocument()
  })

  it('renders no links when stages array is empty', () => {
    const answer: AssistantAnswer = {
      answer: 'Этап 3 отстаёт',
      verified: true,
      numbers_not_in_report: [],
      numbers_of_other_site: [],
      limits: '',
      site_label: 'p1',
      stages: [],
    }
    render(<AssistantAnswerView answer={answer} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  // Безопасность от инъекций
  it('renders injection as literal text without creating elements', () => {
    const answer: AssistantAnswer = {
      answer: '<img src=x onerror=alert(1)> **жирный**',
      verified: true,
      numbers_not_in_report: [],
      numbers_of_other_site: [],
      limits: '',
      site_label: 'p1',
      stages: [],
    }
    const { container } = render(<AssistantAnswerView answer={answer} />)
    expect(screen.getByText('<img src=x onerror=alert(1)> **жирный**')).toBeInTheDocument()
    expect(container.querySelector('img')).not.toBeInTheDocument()
  })

  // Ограничения (limits)
  it('does not render paragraph when limits is empty string', () => {
    const answer: AssistantAnswer = {
      answer: 'Ответ',
      verified: true,
      numbers_not_in_report: [],
      numbers_of_other_site: [],
      limits: '',
      site_label: 'p1',
      stages: [],
    }
    const { container } = render(<AssistantAnswerView answer={answer} />)
    // Проверяем, что нет параграфов с классом "sm muted" (то есть limits не отображается)
    expect(container.querySelector('p.sm.muted')).not.toBeInTheDocument()
  })

  // Ref передача и табиндекс
  it('forwards containerRef to root element', () => {
    const ref = createRef<HTMLDivElement>()
    const answer: AssistantAnswer = {
      answer: 'Ответ',
      verified: true,
      numbers_not_in_report: [],
      numbers_of_other_site: [],
      limits: '',
      site_label: 'p1',
      stages: [],
    }
    render(<AssistantAnswerView answer={answer} containerRef={ref} />)
    expect(ref.current).toBeInstanceOf(HTMLDivElement)
    expect(ref.current).toHaveAttribute('tabindex', '-1')
  })

  // HTML корректность
  it('has valid HTML nesting (no div inside p)', () => {
    const answer: AssistantAnswer = {
      answer: 'Ответ',
      verified: false,
      numbers_not_in_report: ['123'],
      numbers_of_other_site: ['456'],
      limits: 'Ограничение',
      site_label: 'p1',
      stages: [],
    }
    const { container } = render(<AssistantAnswerView answer={answer} />)
    expect(container.querySelector('p div')).toBeNull()
  })

  it('does not call console.error during render', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const answer: AssistantAnswer = {
      answer: 'Ответ',
      verified: false,
      numbers_not_in_report: ['123'],
      numbers_of_other_site: ['456'],
      limits: 'Ограничение',
      site_label: 'p1',
      stages: [],
    }
    render(<AssistantAnswerView answer={answer} />)
    expect(spy).not.toHaveBeenCalled()
    spy.mockRestore()
  })
})
