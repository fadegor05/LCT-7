import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type {
  DeviationListItem,
  ImportIssue,
  Observation,
  ObservationDay,
  Stage,
} from '@/api/schemas'
import { buildFrames } from '@/mocks/fixtures'
import { renderWithProviders } from '@/test/render'
import { ZoneEditor } from './cameras/ZoneEditor'
import { DeviationList } from './deviations/DeviationList'
import { describeIssues } from './new-site/describeIssues'
import { StagesTable } from './new-site/StagesTable'
import { CameraStrip } from './observations/CameraStrip'
import { DayPicker } from './observations/DayPicker'
import { EquipmentList } from './observations/EquipmentList'
import { observationSentence } from './overview/observationSentence'
import { ObservabilityBadge, VerdictBadge } from './sites/SiteBadges'
import { verdictText } from './sites/verdict'

const deviation: DeviationListItem = {
  id: 'd1',
  site_id: 's1',
  site_name: 'Стройка',
  type: 'idle',
  is_hypothesis: true,
  severity: 'attention',
  confidence: 'low',
  stage_name: null,
  title: 'Самосвал простаивает',
  detected_at: '2026-09-18T10:00:00',
  decision: null,
}

describe('DeviationList', () => {
  it('shows site deviations with the waiting marker', () => {
    renderWithProviders(<DeviationList items={[deviation]} />)
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', '/sites/s1/deviations/d1')
    expect(within(link).getByText('Простой техники (гипотеза)')).toBeInTheDocument()
    expect(within(link).getByText('Ждёт решения')).toBeInTheDocument()
    expect(within(link).getByText('Все этапы')).toBeInTheDocument()
    expect(within(link).getByText('Самосвал простаивает')).toBeInTheDocument()
  })

  it('shows the site name in the cross-site list', () => {
    renderWithProviders(<DeviationList items={[deviation]} showSite />)
    expect(screen.getByText('Стройка')).toBeInTheDocument()
    expect(screen.queryByText('Ждёт решения')).not.toBeInTheDocument()
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
      measured_stage_name: null,
      explanation: null,
      observability: 'high' as const,
      cameras_total: 1,
      cameras_reporting: 1,
      last_frame_at: null,
      frames_total: 0,
      frames_without_time: 0,
      data_age_days: null,
      critical_count: 0,
      attention_count: 0,
    }
    render(
      <>
        <VerdictBadge summary={null} />
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

describe('describeIssues', () => {
  const issue = (kind: ImportIssue['kind'], extra: Partial<ImportIssue> = {}): ImportIssue => ({
    id: kind + (extra.row_number ?? ''),
    kind,
    row_number: null,
    stage_id: null,
    message: 'Окна А и Б пересекаются',
    blocking: true,
    resolved_at: null,
    ...extra,
  })

  it('summarises every issue kind', () => {
    const lines = describeIssues([
      issue('row_unparsed', { row_number: 14 }),
      issue('row_unparsed', { row_number: 27 }),
      issue('no_dates'),
      issue('no_dates', { id: 'x' }),
      issue('fuzzy_match'),
      issue('window_overlap'),
    ])
    expect(lines[0]).toBe('2 строки не разобраны (строки 14 и 27 файла: нет названия этапа).')
    expect(lines[1]).toBe('У 2 этапов нет дат: задайте их вручную.')
    expect(lines[2]).toBe('Один этап сопоставлен нечётко: подтвердите.')
    expect(lines[3]).toContain('Окна А и Б пересекаются')
  })

  it('uses singular forms', () => {
    const lines = describeIssues([
      issue('no_dates'),
      issue('fuzzy_match'),
      issue('fuzzy_match', { id: 'y' }),
    ])
    expect(lines).toEqual([
      'У одного этапа нет дат: задайте их вручную.',
      '2 этапа сопоставлены нечётко: подтвердите.',
    ])
    expect(describeIssues([])).toEqual([])
  })
})

describe('StagesTable', () => {
  const stage = (over: Partial<Stage>): Stage => ({
    id: 's',
    seq_no: 1,
    name: 'Этап',
    match_kind: 'exact',
    match_score: null,
    match_confirmed: true,
    planned_start: '2026-09-01',
    planned_end: '2026-09-05',
    dates_source: 'works',
    merged_windows: 1,
    equipment_check: true,
    not_checked_reason: null,
    has_marker: true,
    works: [],
    ...over,
  })

  it('renders works, windows and match labels', () => {
    render(
      <StagesTable
        year={2026}
        onConfirmMatch={vi.fn()}
        onSetDates={vi.fn()}
        stages={[
          stage({
            id: 'a',
            name: 'Подготовка',
            merged_windows: 9,
            works: ['1', '2', '3', '4', '5', '6'].map((n) => ({ id: n, name: `Работа ${n}` })),
          }),
          stage({
            id: 'b',
            name: 'Ручной',
            match_kind: 'manual',
            dates_source: 'manual',
            equipment_check: false,
          }),
          stage({ id: 'c', name: 'Без', match_kind: 'none' }),
        ]}
      />,
    )
    expect(screen.getByText('6 работ')).toBeInTheDocument()
    expect(screen.getByText('ещё 2')).toBeInTheDocument()
    expect(screen.getByText('объединено из 9 окон')).toBeInTheDocument()
    expect(screen.getByText('задано вручную')).toBeInTheDocument()
    expect(screen.getByText('Вручную')).toBeInTheDocument()
    expect(screen.getByText('Не сопоставлен')).toBeInTheDocument()
    expect(screen.getByText('Не проверяется · нет крупной техники')).toBeInTheDocument()
  })

  it('confirms fuzzy matches and validates manual dates', async () => {
    const onConfirm = vi.fn()
    const onSetDates = vi.fn()
    render(
      <StagesTable
        year={2026}
        onConfirmMatch={onConfirm}
        onSetDates={onSetDates}
        stages={[
          stage({
            id: 'f',
            name: 'Плита',
            match_kind: 'fuzzy',
            match_score: 0.74,
            match_confirmed: false,
            planned_start: null,
            planned_end: null,
          }),
        ]}
      />,
    )
    expect(screen.getByText('Справочник · нечёткое · 74%')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Подтвердить сопоставление' }))
    expect(onConfirm).toHaveBeenCalledWith('f')

    const start = screen.getByLabelText('Дата начала: Плита')
    const end = screen.getByLabelText('Дата окончания: Плита')
    await userEvent.click(screen.getByRole('button', { name: 'Задать' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Даты в формате дд.мм')
    await userEvent.type(start, '05.10')
    await userEvent.type(end, '23.09')
    await userEvent.click(screen.getByRole('button', { name: 'Задать' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Окончание раньше начала')
    await userEvent.clear(end)
    await userEvent.type(end, '12.10')
    await userEvent.click(screen.getByRole('button', { name: 'Задать' }))
    expect(onSetDates).toHaveBeenCalledWith('f', '2026-10-05', '2026-10-12')
  })
})

describe('observations', () => {
  const days: ObservationDay[] = [
    { obs_date: '2026-09-17', frames_total: 2, observability: 'high' },
    { obs_date: '2026-09-18', frames_total: 3, observability: 'high' },
  ]

  it('DayPicker switches days and links frames without time', async () => {
    const onChange = vi.fn()
    render(<DayPicker days={days} value="2026-09-18" onChange={onChange} withoutTime={7} />)
    expect(screen.getByRole('button', { name: /Все дни/ })).toHaveTextContent('5 кадров')
    expect(screen.getByRole('button', { name: /18\.09/ })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: /Все дни/ }))
    await userEvent.click(screen.getByRole('button', { name: /17\.09/ }))
    expect(onChange.mock.calls).toEqual([[null], ['2026-09-17']])
    expect(screen.getByRole('link', { name: /Без даты/ })).toHaveAttribute('href', '#no-time')
  })

  it('DayPicker hides the no-time chip when all frames have time', () => {
    render(<DayPicker days={days} value={null} onChange={vi.fn()} withoutTime={0} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  const observation: Observation = {
    obs_date: '2026-09-18',
    expected_stage_name: 'Котлован',
    frames_total: 3,
    observability: 'high',
    equipment: [
      {
        equipment_class: 'excavator',
        name: 'Экскаватор',
        min_count: 2,
        activity: 'working',
        activity_hypothesis: false,
        basis_text: 'движение',
        deviation_id: 'dev-1',
      },
      {
        equipment_class: 'dump_truck',
        name: 'Самосвал',
        min_count: 1,
        activity: 'idle',
        activity_hypothesis: true,
        basis_text: 'стоит',
        deviation_id: null,
      },
      {
        equipment_class: 'truck',
        name: 'Грузовик',
        min_count: 1,
        activity: 'idle',
        activity_hypothesis: false,
        basis_text: 'стоит',
        deviation_id: null,
      },
      {
        equipment_class: 'bulldozer',
        name: 'Бульдозер',
        min_count: 1,
        activity: 'unknown',
        activity_hypothesis: false,
        basis_text: 'нет пары',
        deviation_id: null,
      },
    ],
  }

  it('EquipmentList shows counts, activity and links to deviations', () => {
    renderWithProviders(
      <EquipmentList siteId="s1" stageName="Котлован" items={observation.equipment} />,
    )
    expect(screen.getByText('Этап: Котлован')).toBeInTheDocument()
    expect(screen.getByText('не менее 2')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Экскаватор: Работает/ })).toHaveAttribute(
      'href',
      '/sites/s1/deviations/dev-1',
    )
    expect(screen.getAllByText('Простаивает')).toHaveLength(2)
    expect(screen.getByText('Неизвестно')).toBeInTheDocument()
  })

  it('EquipmentList has an empty state', () => {
    renderWithProviders(<EquipmentList siteId="s1" stageName={null} items={[]} />)
    expect(screen.getByText(/Техники на кадрах не найдено/)).toBeInTheDocument()
  })

  it('observationSentence summarises the day', () => {
    expect(observationSentence(observation)).toBe(
      'Экскаватор 2, самосвал 1, грузовик 1, бульдозер 1 (максимум по кадрам). Простаивает: самосвал (гипотеза), грузовик.',
    )
    expect(
      observationSentence({ ...observation, equipment: observation.equipment.slice(0, 1) }),
    ).toBe('Экскаватор 2 (максимум по кадрам).')
    expect(observationSentence({ ...observation, equipment: [] })).toBe(
      'Техники на кадрах не найдено.',
    )
  })

  it('CameraStrip lists frames and scrolls', async () => {
    const frames = buildFrames().filter(
      (f) => f.camera_id === 'cam-1' && f.captured_at?.startsWith('2026-09-18'),
    )
    render(<CameraStrip name="К-1" frames={frames} withDate={false} classLabel={(c) => c} />)
    const section = screen.getByRole('region', { name: 'Камера К-1' })
    expect(section).toHaveTextContent('6 кадров · последний 14:20')
    expect(screen.getAllByText('Фото')).toHaveLength(6)
    expect(screen.getByText('08:10')).toBeInTheDocument()
    const strip = section.querySelector('[class*="frames"]') as HTMLElement
    strip.scrollBy = vi.fn()
    await userEvent.click(screen.getByRole('button', { name: 'Вперёд по времени' }))
    await userEvent.click(screen.getByRole('button', { name: 'Назад по времени' }))
    expect(strip.scrollBy).toHaveBeenCalledWith({ left: 480, behavior: 'smooth' })
    expect(strip.scrollBy).toHaveBeenCalledWith({ left: -480, behavior: 'smooth' })
  })

  it('CameraStrip shows dates in the all-days mode and empty frames', () => {
    const frames = buildFrames().filter(
      (f) => f.camera_id === 'cam-2' && f.captured_at?.startsWith('2026-09-18'),
    )
    render(<CameraStrip name="К-2" frames={frames} withDate classLabel={(c) => c} />)
    expect(screen.getByText('18.09 08:20')).toBeInTheDocument()
    expect(screen.getAllByText('нет техники').length).toBeGreaterThan(0)
  })
})

describe('ZoneEditor', () => {
  function setup(props: Partial<Parameters<typeof ZoneEditor>[0]> = {}) {
    const onChange = vi.fn()
    render(<ZoneEditor imageUrl={null} points={[]} closed={false} onChange={onChange} {...props} />)
    const box = screen.getByTestId('zone-editor')
    box.getBoundingClientRect = () => ({ left: 0, top: 0, width: 200, height: 100 }) as DOMRect
    return { onChange, box }
  }

  it('adds vertices in frame fractions', () => {
    const { onChange, box } = setup()
    expect(screen.getByText('Кадра пока нет')).toBeInTheDocument()
    fireEvent.pointerDown(box, { clientX: 50, clientY: 25 })
    expect(onChange).toHaveBeenCalledWith([[0.25, 0.25]], false)
  })

  it('closes the contour on the first vertex', () => {
    const points: [number, number][] = [
      [0.1, 0.1],
      [0.5, 0.1],
      [0.5, 0.5],
    ]
    const { onChange } = setup({ points })
    fireEvent.pointerDown(screen.getByRole('button', { name: 'Замкнуть контур' }))
    expect(onChange).toHaveBeenCalledWith(points, true)
  })

  it('drags vertices of a closed zone and ignores clicks on it', () => {
    const points: [number, number][] = [
      [0.1, 0.1],
      [0.5, 0.1],
      [0.5, 0.5],
    ]
    const { onChange, box } = setup({ points, closed: true, imageUrl: '/f.jpg' })
    expect(box).toHaveStyle({ backgroundImage: 'url(/f.jpg)' })
    fireEvent.pointerDown(box, { clientX: 10, clientY: 10 })
    expect(onChange).not.toHaveBeenCalled()
    fireEvent.pointerDown(screen.getByRole('button', { name: 'Вершина 2' }))
    fireEvent.pointerMove(box, { clientX: 300, clientY: -20 })
    expect(onChange).toHaveBeenCalledWith(
      [
        [0.1, 0.1],
        [1, 0],
        [0.5, 0.5],
      ],
      true,
    )
    fireEvent.pointerUp(box)
    onChange.mockClear()
    fireEvent.pointerMove(box, { clientX: 20, clientY: 20 })
    expect(onChange).not.toHaveBeenCalled()
  })
})
