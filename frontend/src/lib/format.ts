import { plural } from './labels'

/**
 * Форматирование дат. Даты наблюдений приходят как YYYY-MM-DD (в часовом поясе стройки),
 * моменты — как ISO с зоной. Показываем в формате макета с днём недели: ПТ 18.09.2026, ПТ 18.09, 14:20.
 */

const pad = (n: number) => String(n).padStart(2, '0')

function parts(value: string): { y: number; m: number; d: number; hh: number; mm: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(value)
  if (!match) return null
  const [, y, m, d, hh = '0', mm = '0'] = match
  return { y: +y!, m: +m!, d: +d!, hh: +hh, mm: +mm }
}

const WEEKDAYS = ['ВС', 'ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ'] as const

/** День недели календарной даты (без часового пояса браузера). */
function weekday(p: { y: number; m: number; d: number }): string {
  return WEEKDAYS[new Date(Date.UTC(p.y, p.m - 1, p.d)).getUTCDay()]!
}

/** 2026-09-18 → ПТ 18.09.2026 */
export function formatDate(value: string | null | undefined): string {
  const p = value ? parts(value) : null
  return p ? `${weekday(p)} ${pad(p.d)}.${pad(p.m)}.${p.y}` : '—'
}

/** 2026-09-18 → ПТ 18.09 */
export function formatShortDate(value: string | null | undefined): string {
  const p = value ? parts(value) : null
  return p ? `${weekday(p)} ${pad(p.d)}.${pad(p.m)}` : '—'
}

/** 2026-09-18T14:20:00+05:00 → 14:20 (локальное время стройки, как записано в строке). */
export function formatTime(value: string | null | undefined): string {
  const p = value ? parts(value) : null
  return p ? `${pad(p.hh)}:${pad(p.mm)}` : '—'
}

/** 2026-09-18T14:20 → ПТ 18.09 14:20 */
export function formatShortDateTime(value: string | null | undefined): string {
  return value ? `${formatShortDate(value)} ${formatTime(value)}` : '—'
}

/** 2026-09-18T14:20 → ПТ 18.09.2026 14:20 */
export function formatDateTime(value: string | null | undefined): string {
  return value ? `${formatDate(value)} ${formatTime(value)}` : '—'
}

/** Плановое окно этапа: ПН 24.08.2026 — ПН 31.08.2026 */
export function formatWindow(start: string | null, end: string | null, sep = ' — '): string {
  if (!start && !end) return '—'
  return `${formatDate(start)}${sep}${formatDate(end)}`
}

/** Отставание: «от 4 дн.» или «4–6 дн.» */
export function formatDelay(min: number | null, max: number | null): string | null {
  if (min === null) return null
  if (max === null) return `от ${min} дн.`
  if (max === min) return `${min} дн.`
  return `${min}–${max} дн.`
}

/** Размер файла: 24 КБ */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`
  return `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} МБ`
}

/** Сегодня в локальном времени браузера: YYYY-MM-DD, как даты с сервера. */
export function todayIso(): string {
  const now = new Date()
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** «дд.мм» или «дд.мм.гггг» → YYYY-MM-DD. Год по умолчанию берётся из `fallbackYear`. */
export function parseRuDate(value: string, fallbackYear: number): string | null {
  const match = /^\s*(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s*$/.exec(value)
  if (!match) return null
  const [, d, m, y] = match
  const day = +d!
  const month = +m!
  const year = y ? +y : fallbackYear
  const date = new Date(Date.UTC(year, month - 1, day))
  if (date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null
  return `${year}-${pad(month)}-${pad(day)}`
}

/** «дд.мм.гггг чч:мм» → YYYY-MM-DDTHH:MM:00 (время стройки, без зоны). */
export function parseRuDateTime(value: string): string | null {
  const match = /^\s*(\d{1,2}\.\d{1,2}\.\d{4})\s+(\d{1,2}):(\d{2})\s*$/.exec(value)
  if (!match) return null
  const [, datePart, hh, mm] = match
  const date = parseRuDate(datePart!, 0)
  if (!date || +hh! > 23 || +mm! > 59) return null
  return `${date}T${pad(+hh!)}:${mm}:00`
}

/** Сколько дней назад: «2 дня назад», «сегодня». */
export function daysAgo(days: number): string {
  if (days <= 0) return 'сегодня'
  if (days === 1) return 'вчера'
  return `${days} ${plural(days, ['день', 'дня', 'дней'])} назад`
}

/** Наблюдение с наибольшей датой. Порядок списка от API не гарантирован (бэкенд отдаёт по убыванию). */
export function latestObservation<T extends { observed_on: string }>(
  observations: readonly T[] | undefined,
): T | undefined {
  return observations?.reduce<T | undefined>(
    (best, o) => (!best || o.observed_on > best.observed_on ? o : best),
    undefined,
  )
}
