import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import type { Observation, ScheduleReport, Stage, StageStatus } from '@/api/schemas'
import type { DeviationItem } from '@/lib/deviations'
import { server } from '@/mocks/server'
import { renderWithProviders } from '@/test/render'
import { DeviationList } from './deviations/DeviationList'
import { describeIssues } from './new-site/describeIssues'
import { StagesTable } from './new-site/StagesTable'
import { DayPicker } from './observations/DayPicker'
import { EquipmentList } from './observations/EquipmentList'
import { observationSentence } from './overview/observationSentence'
import { StageStatusTable } from './overview/StageStatusTable'
import { SummaryCards } from './overview/SummaryCards'
import { ObservabilityBadge, VerdictBadge } from './sites/SiteBadges'
import { verdictText } from './sites/verdict'

const deviation: DeviationItem = {
  id: 'd1',
  site_id: 's1',
  site_name: 'Стройка',
  stage_id: null,
  stage_name: null,
  type: 'idle',
  is_hypothesis: true,
  severity: 'attention',
  confidence: 'low',
  period_start: '2026-09-17',
  period_end: '2026-09-18',
  expected: 'Самосвал работает',
  observed: 'Самосвал стоит',
  limits_text: 'Гипотеза',
  rule_id: null,
  created_at: '2026-09-18T10:00:00Z',
}

describe('DeviationList', () => {
  it('shows site deviations with the stage and period', () => {
    renderWithProviders(<DeviationList items={[deviation]} />)
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', '/sites/s1/deviations/d1')
    expect(within(link).getByText('Простой техники (гипотеза)')).toBeInTheDocument()
    expect(within(link).getByText('Все этапы')).toBeInTheDocument()
    expect(within(link).getByText('ЧТ 17.09.2026 — ПТ 18.09.2026')).toBeInTheDocument()
    expect(within(link).getByText('ПТ 18.09.2026')).toBeInTheDocument()
  })

  it('shows the site name and period in the cross-site list', () => {
    renderWithProviders(
      <DeviationList items={[{ ...deviation, stage_name: undefined }]} showSite />,
    )
    expect(screen.getByText('Стройка')).toBeInTheDocument()
    expect(screen.getByText('ЧТ 17.09.2026 — ПТ 18.09.2026')).toBeInTheDocument()
  })

  it('has an empty state', () => {
    renderWithProviders(<DeviationList items={[]} />)
    expect(screen.getByText('Отклонений не выявлено.')).toBeInTheDocument()
  })
})

describe('verdict', () => {
  it('builds verdict texts', () => {
    expect(verdictText({ verdict: 'behind', delay_days_min: 4, delay_days_max: null })).toBe(
      'Отставание от 4 дней',
    )
    expect(verdictText({ verdict: 'behind', delay_days_min: 4, delay_days_max: 6 })).toBe(
      'Отставание 4–6 дней',
    )
    expect(verdictText({ verdict: 'behind', delay_days_min: null, delay_days_max: null })).toBe(
      'Отставание',
    )
    expect(
      verdictText({ verdict: 'no_deviations', delay_days_min: null, delay_days_max: null }),
    ).toBe('Отклонений не выявлено')
  })

  it('renders verdict and observability badges', () => {
    const base = {
      delay_days_min: null,
      delay_days_max: null,
      critical_count: 0,
      attention_count: 0,
    }
    render(
      <>
        <VerdictBadge summary={undefined} />
        <VerdictBadge summary={{ ...base, verdict: 'no_deviations' }} />
        <ObservabilityBadge level="high" />
        <ObservabilityBadge level="low" />
      </>,
    )
    expect(screen.getByText('Недостаточно данных')).toBeInTheDocument()
    expect(screen.getByText('Отклонений не выявлено')).toBeInTheDocument()
    expect(screen.getByText('Высокая')).toBeInTheDocument()
    expect(screen.getByText('Низкая')).toBeInTheDocument()
  })
})

const report = (patch: Partial<ScheduleReport>): ScheduleReport => ({
  id: 'sch',
  site_id: 's1',
  source_filename: 'g.csv',
  imported_at: '2026-09-01T00:00:00Z',
  rows_total: 0,
  rows_parsed: 0,
  parse_method: 'builtin',
  stages_with_dates: 0,
  stages_without_dates: 0,
  stages: [],
  issues: [],
  ...patch,
})

describe('describeIssues', () => {
  it('lists unparsed rows and stages without dates', () => {
    const lines = describeIssues(
      report({
        issues: [
          { id: 'i1', row_number: 4, raw_row: ';;', reason: 'Нет названия этапа.' },
          { id: 'i2', row_number: 9, raw_row: 'x', reason: 'Некорректная дата' },
        ],
        stages_without_dates: 3,
      }),
    )
    expect(lines).toEqual([
      'Строка 4 не разобрана: Нет названия этапа.',
      'Строка 9 не разобрана: Некорректная дата.',
      'У 3 этапов нет дат: задайте их вручную, иначе этап не оценивается.',
    ])
  })

  it('uses the singular form and is empty for a clean file', () => {
    expect(describeIssues(report({ stages_without_dates: 1 }))).toEqual([
      'У одного этапа нет дат: задайте их вручную, иначе этап не оценивается.',
    ])
    expect(describeIssues(report({}))).toEqual([])
  })
})

const stage = (patch: Partial<Stage>): Stage => ({
  id: 'st',
  name: 'Этап',
  position: 1,
  planned_start: '2026-09-01',
  planned_end: '2026-09-10',
  dates_source: 'file',
  ...patch,
})

describe('StagesTable', () => {
  it('renders windows and marks manual dates', () => {
    renderWithProviders(
      <StagesTable
        year={2026}
        onSetDates={vi.fn()}
        stages={[
          stage({ id: 'a', name: 'Котлован' }),
          stage({ id: 'b', name: 'Основание', position: 2, dates_source: 'manual' }),
        ]}
      />,
    )
    const rows = screen.getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('1КотлованВТ 01.09.2026 — ЧТ 10.09.2026')
    expect(within(rows[1]!).getByText('задано вручную')).toBeInTheDocument()
  })

  it('validates manual dates', async () => {
    const onSetDates = vi.fn()
    renderWithProviders(
      <StagesTable
        year={2026}
        onSetDates={onSetDates}
        stages={[stage({ id: 'x', name: 'Плита', planned_start: null, planned_end: null })]}
      />,
    )
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Задать' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Даты в формате дд.мм.гггг')
    await user.type(screen.getByLabelText('Дата начала: Плита'), '10.10')
    await user.type(screen.getByLabelText('Дата окончания: Плита'), '01.10')
    await user.click(screen.getByRole('button', { name: 'Задать' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Окончание раньше начала')
    await user.clear(screen.getByLabelText('Дата окончания: Плита'))
    await user.type(screen.getByLabelText('Дата окончания: Плита'), '20.10')
    await user.click(screen.getByRole('button', { name: 'Задать' }))
    expect(onSetDates).toHaveBeenCalledWith('x', '2026-10-10', '2026-10-20')
  })
})

describe('StageStatusTable', () => {
  const status = (patch: Partial<StageStatus>): StageStatus => ({
    stage_id: 'st',
    stage_name: 'Этап',
    position: 1,
    status: null,
    delay_days: null,
    confidence: null,
    confidence_reason: null,
    computed_at: null,
    ...patch,
  })

  it('shows plan, status, delay, confidence and linked deviations', () => {
    renderWithProviders(
      <StageStatusTable
        siteId="s1"
        stages={[stage({ id: 'a' })]}
        deviations={[{ ...deviation, stage_id: 'a' }]}
        rows={[
          status({
            stage_id: 'a',
            stage_name: 'Котлован',
            status: 'behind',
            delay_days: 4,
            confidence: 'high',
            confidence_reason: 'Экскаватор после планового конца',
          }),
          status({ stage_id: 'b', stage_name: 'Плита', status: 'ahead', delay_days: 2 }),
          status({ stage_id: 'c', stage_name: 'Засыпка' }),
        ]}
      />,
    )
    const [, pit, slab, backfill] = screen.getAllByRole('row')
    expect(pit).toHaveTextContent('ВТ 01.09.2026–ЧТ 10.09.2026')
    expect(pit).toHaveTextContent('Экскаватор после планового конца')
    expect(pit).toHaveTextContent('отставание 4 дн. · уверенность высокая')
    expect(within(pit!).getByRole('link', { name: 'Простой техники (гипотеза)' })).toHaveAttribute(
      'href',
      '/sites/s1/deviations/d1',
    )
    expect(slab).toHaveTextContent('опережение 2 дн.')
    expect(slab).toHaveTextContent('—')
    expect(backfill).toHaveTextContent('Не начата')
  })
})

describe('observations', () => {
  const observation = (patch: Partial<Observation>): Observation => ({
    id: 'o',
    site_id: 's1',
    observed_on: '2026-09-18',
    photo_count: 3,
    observability: 'high',
    observability_notes: null,
    recomputed_at: '2026-09-18T12:00:00Z',
    equipment: [],
    ...patch,
  })
  const days = [
    observation({ observed_on: '2026-09-17', photo_count: 2 }),
    observation({ observed_on: '2026-09-18', photo_count: 3 }),
  ]

  it('DayPicker switches days and links photos without a date', async () => {
    const onChange = vi.fn()
    render(<DayPicker days={days} value="2026-09-18" onChange={onChange} undated={7} />)
    expect(screen.getByRole('button', { name: /Все дни/ })).toHaveTextContent('5 снимков')
    expect(screen.getByRole('button', { name: /18\.09/ })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: /Все дни/ }))
    await userEvent.click(screen.getByRole('button', { name: /17\.09/ }))
    expect(onChange.mock.calls).toEqual([[null], ['2026-09-17']])
    expect(screen.getByRole('link', { name: /Без даты/ })).toHaveAttribute('href', '#no-date')
  })

  it('DayPicker hides the no-date chip when every photo has a date', () => {
    render(<DayPicker days={days} value={null} onChange={vi.fn()} undated={0} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  const equipment: Observation['equipment'] = [
    {
      equipment_type_id: 'e1',
      equipment_code: 'excavator_crawler',
      equipment_title: 'Гусеничный экскаватор',
      count_min: 2,
      activity: 'works',
      activity_basis: 'Движение: машина сместилась между 10:05 и 10:15\nЗона: внутри зоны',
      confidence: 'high',
    },
    {
      equipment_type_id: 'e2',
      equipment_code: 'dump_truck',
      equipment_title: 'Самосвал',
      count_min: 1,
      activity: 'idle',
      confidence: 'medium',
    },
    {
      equipment_type_id: 'e3',
      equipment_code: 'bulldozer',
      equipment_title: 'Бульдозер',
      count_min: 1,
      activity: 'unknown',
      confidence: 'low',
    },
  ]

  it('EquipmentList shows counts, activity and confidence', () => {
    render(
      <EquipmentList
        observation={observation({
          equipment,
          observability: 'medium',
          observability_notes: 'Мало снимков',
        })}
      />,
    )
    expect(screen.getByText('Наблюдаемость средняя · Мало снимков')).toBeInTheDocument()
    expect(screen.getByText('не менее 2')).toBeInTheDocument()
    expect(screen.getByText('Работает')).toBeInTheDocument()
    expect(screen.getByText('Простаивает')).toBeInTheDocument()
    expect(screen.getByText('Неизвестно')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Уверенность: низкая' })).toBeInTheDocument()
    // Основание активности — под строкой машины
    expect(screen.getByText(/машина сместилась между 10:05 и 10:15/)).toBeInTheDocument()
  })

  it('EquipmentList shows a shared activity basis once', () => {
    const basis = 'Движение: нет серии кадров одной камеры со временем — по одному снимку не видно'
    render(
      <EquipmentList
        observation={observation({
          equipment: equipment.map((e) => ({ ...e, activity_basis: basis })),
        })}
      />,
    )
    expect(screen.getAllByText(basis)).toHaveLength(1)
  })

  it('EquipmentList has an empty state', () => {
    render(<EquipmentList observation={observation({})} />)
    expect(screen.getByText(/Техники на снимках не найдено/)).toBeInTheDocument()
    expect(screen.getByText('Наблюдаемость высокая')).toBeInTheDocument()
  })

  it('observationSentence summarises the day', () => {
    expect(observationSentence(observation({ equipment }))).toBe(
      'Гусеничный экскаватор 2, самосвал 1, бульдозер 1 (максимум по снимкам). Простаивает: самосвал.',
    )
    expect(observationSentence(observation({ equipment: equipment.slice(0, 1) }))).toBe(
      'Гусеничный экскаватор 2 (максимум по снимкам).',
    )
    expect(observationSentence(observation({}))).toBe('Техники на снимках не найдено.')
  })
})

// bug-reports/002: «Недостаточно данных» называет настоящую причину.
describe('SummaryCards insufficient data', () => {
  const insufficient = () =>
    http.get('/api/sites/:siteId/assessment/summary', () =>
      HttpResponse.json({
        verdict: 'insufficient_data',
        delay_days_min: null,
        delay_days_max: null,
        critical_count: 0,
        attention_count: 0,
      }),
    )

  it('points to undated photos when they are the only photos', async () => {
    server.use(
      insufficient(),
      http.get('/api/sites/:siteId/observations', () => HttpResponse.json([])),
    )
    renderWithProviders(<SummaryCards siteId="site-berezniki" />)
    expect(await screen.findByText(/Нет наблюдений: у 2 снимков не задана/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Задать дату' })).toHaveAttribute(
      'href',
      '/sites/site-berezniki/observations#no-date',
    )
  })

  it('asks for a schedule when there is none', async () => {
    server.use(
      insufficient(),
      http.get('/api/sites/:siteId/schedule', () =>
        HttpResponse.json({ detail: 'График не загружен' }, { status: 404 }),
      ),
    )
    renderWithProviders(<SummaryCards siteId="site-berezniki" />)
    expect(
      await screen.findByText(/График не загружен: этапы не с чем сравнить/),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Загрузить график' })).toHaveAttribute(
      'href',
      '/sites/site-berezniki/setup',
    )
  })

  it('blames observability when observations exist', async () => {
    server.use(insufficient())
    renderWithProviders(<SummaryCards siteId="site-berezniki" />)
    expect(await screen.findByText(/Наблюдений не хватает для вывода/)).toBeInTheDocument()
  })
})
