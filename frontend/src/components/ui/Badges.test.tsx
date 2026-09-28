import { render, screen } from '@testing-library/react'
import type { StageStatusValue } from '@/api/schemas'
import { ConfidenceMeter } from './ConfidenceMeter'
import { DateSourceBadge } from './DateSourceBadge'
import { Pill } from './Pill'
import { StatusBadge } from './StatusBadge'

describe('Pill', () => {
  it('renders tone, size and icon', () => {
    const { container } = render(
      <Pill tone="caution" size="sm" icon="clock">
        Внимание
      </Pill>,
    )
    const pill = screen.getByText('Внимание')
    expect(pill.className).toMatch(/caution/)
    expect(pill.className).toMatch(/small/)
    expect(container.querySelector('[data-icon="clock"]')).toBeInTheDocument()
  })
})

describe('StatusBadge', () => {
  it.each<[StageStatusValue | null, string]>([
    ['ahead', 'Опережение'],
    ['on_track', 'В графике'],
    ['behind', 'Отставание'],
    ['not_started', 'Не начата'],
    [null, 'Не начата'],
    ['not_observed', 'Не наблюдалось'],
    ['not_checked', 'Не проверяется по технике'],
  ])('%s → %s', (status, label) => {
    render(<StatusBadge status={status} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  // bug-reports/002: null при наступившем окне — не «не начата».
  it.each<[string | null, string]>([
    ['2020-01-01', 'Не оценён'],
    [null, 'Не оценён'],
    ['2999-01-01', 'Не начата'],
  ])('null with planned start %s → %s', (plannedStart, label) => {
    render(<StatusBadge status={null} plannedStart={plannedStart} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })
})

describe('ConfidenceMeter', () => {
  it('exposes the level to assistive tech', () => {
    const { container } = render(<ConfidenceMeter level="medium" />)
    expect(screen.getByRole('img', { name: 'Уверенность: средняя' })).toBeInTheDocument()
    expect(container.querySelectorAll('[class*="on"]').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('Средняя')).toBeInTheDocument()
  })

  it('can hide the text label', () => {
    render(<ConfidenceMeter level="high" hideLabel />)
    expect(screen.queryByText('Высокая')).not.toBeInTheDocument()
  })
})

describe('DateSourceBadge', () => {
  it.each([
    ['metadata', 'Метаданные', 'Дата получена вместе со снимком'],
    ['channel', 'Канал', 'Дата получена вместе со снимком'],
    ['stamp', 'Штамп', 'Дата выведена сервисом'],
    ['filename', 'Из имени файла', 'Дата выведена сервисом'],
    ['neighbours', 'По соседним снимкам', 'Дата выведена сервисом'],
    ['manual', 'Вручную', 'Дата введена инженером'],
  ] as const)('%s', (source, label, title) => {
    render(<DateSourceBadge source={source} />)
    expect(screen.getByText(label)).toHaveAttribute('title', title)
  })
})
