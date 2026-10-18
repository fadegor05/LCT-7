import { FRAME_BOXES, type DemoBox } from './p03'

/**
 * Данные и расчёт для закреплённого таймлайна: этапы p03 по плану, снимки на датах и шаги рассказа.
 * Даты взяты из отчёта ML-цепочки (`report.json`): план этапов, даты снимков, пороги вывода.
 */

const DAY = 86_400_000
const parse = (iso: string) => Date.parse(`${iso}T00:00:00Z`)

export const AXIS_START = '2023-05-01'
export const AXIS_END = '2023-10-31'
export const AXIS_DAYS = Math.round((parse(AXIS_END) - parse(AXIS_START)) / DAY)

/** Дата в днях от начала оси. */
export function dayOf(iso: string): number {
  return Math.round((parse(iso) - parse(AXIS_START)) / DAY)
}

/** Положение даты на оси, доля от 0 до 1. */
export function axisPos(iso: string): number {
  return dayOf(iso) / AXIS_DAYS
}

export const MONTH_TICKS = [
  { iso: '2023-05-01', label: 'мая' },
  { iso: '2023-06-01', label: 'июня' },
  { iso: '2023-07-01', label: 'июля' },
  { iso: '2023-08-01', label: 'августа' },
  { iso: '2023-09-01', label: 'сентября' },
  { iso: '2023-10-01', label: 'октября' },
] as const

export interface PlanRow {
  id: 'piles' | 'sheet'
  title: string
  start: string
  end: string
}

export const PLAN_ROWS: readonly PlanRow[] = [
  { id: 'piles', title: 'Устройство свай', start: '2023-05-15', end: '2023-07-31' },
  { id: 'sheet', title: 'Ограждение котлована: шпунт', start: '2023-07-01', end: '2023-08-31' },
]

export interface Snapshot {
  iso: string
  short: string
  src: string
  alt: string
  caption: string
  boxes: DemoBox[]
}

export const SNAPSHOTS: readonly Snapshot[] = [
  {
    iso: '2023-06-19',
    short: '19.06',
    src: '/landing/p03/start-1.jpg',
    alt: 'Площадка 19 июня 2023: арматурные каркасы и гусеничный кран',
    caption: 'До планового конца этапа свай',
    boxes: FRAME_BOXES['start-1'],
  },
  {
    iso: '2023-08-14',
    short: '14.08',
    src: '/landing/p03/piles-1.jpg',
    alt: 'Площадка 14 августа 2023: две буровые установки у шпунтового ограждения',
    caption: 'Буровые на кадре, плановый конец прошёл',
    boxes: FRAME_BOXES['piles-1'],
  },
  {
    iso: '2023-10-13',
    short: '13.10',
    src: '/landing/p03/sheet-1.jpg',
    alt: 'Площадка 13 октября 2023: в котловане работает экскаватор, шпунтовой техники нет',
    caption: 'Шпунтовой техники нет',
    boxes: FRAME_BOXES['sheet-1'],
  },
]

export interface Step {
  kicker: string
  title: string
  text: string
}

export const STEPS: readonly Step[] = [
  {
    kicker: 'План',
    title: 'Сначала график',
    text: 'Этапы стоят на оси времени так, как их заложил подрядчик. С этим Веха и сверяет снимки.',
  },
  {
    kicker: '19 июня',
    title: 'Первый снимок',
    text: 'Снимок сделан до планового конца этапа свай. Тревожных выводов из него нет, этап идёт.',
  },
  {
    kicker: '14 августа',
    title: 'Плановый срок прошёл, буровые на кадре',
    text: 'Этап свай должен был закончиться 31 июля, а буровые на кадре до сих пор. По снимкам это отставание от 14 до 43 дней.',
  },
  {
    kicker: '13 октября',
    title: 'Плановое начало шпунта было 1 июля',
    text: 'Техники этапа на кадре нет, а плановое начало прошло 104 дня назад. Поэтому статус «Не начат». Будь снимков мало, было бы «Не наблюдалось».',
  },
  {
    kicker: 'Границы',
    title: 'Что Веха не утверждает',
    text: 'Снимки покрывают не всю площадку и не всё время. Отсутствие техники в кадре не доказывает, что работы не ведутся.',
  },
]

export interface TimelineState {
  /** Положение линии «срез» на оси от 0 до 1, `null` до её появления. */
  cursor: number | null
  /** Какие снимки уже прошла линия среза. */
  shown: boolean[]
  /** Какая доля красного отрезка отставания нарисована, от 0 до 1. */
  lag: number
  /** Показаны ли плашки статусов. */
  piles: boolean
  sheet: boolean
  step: number
}

const START = 0.06
const END = 0.9
const LAST = 0.96

/** Расчёт сцены по прогрессу прокрутки секции от 0 до 1. */
export function timelineState(progress: number): TimelineState {
  const p = Math.min(1, Math.max(0, progress))
  if (p < START) {
    return {
      cursor: null,
      shown: SNAPSHOTS.map(() => false),
      lag: 0,
      piles: false,
      sheet: false,
      step: 0,
    }
  }
  const c = Math.min(1, (p - START) / (END - START))
  const cursor = c * axisPos('2023-10-20')
  const shown = SNAPSHOTS.map((s) => cursor >= axisPos(s.iso))
  const from = axisPos('2023-07-31')
  const to = axisPos('2023-08-14')
  const lag = Math.min(1, Math.max(0, (cursor - from) / (to - from)))
  const count = shown.filter(Boolean).length
  const step = p >= LAST ? 4 : count
  return {
    cursor,
    shown,
    lag,
    piles: shown[1] === true,
    sheet: shown[2] === true,
    step,
  }
}
