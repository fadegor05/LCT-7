import {
  daysAgo,
  formatDate,
  formatDateTime,
  formatDelay,
  latestObservation,
  formatFileSize,
  formatShortDate,
  formatShortDateTime,
  formatTime,
  formatWindow,
  parseRuDate,
  parseRuDateTime,
  todayIso,
} from './format'

describe('format', () => {
  it('formats dates and times as in the mockups', () => {
    expect(formatDate('2026-09-18')).toBe('ПТ 18.09.2026')
    expect(formatShortDate('2026-09-18T14:20:00+05:00')).toBe('ПТ 18.09')
    expect(formatTime('2026-09-18T14:20:00+05:00')).toBe('14:20')
    expect(formatShortDateTime('2026-09-18T14:20:00+05:00')).toBe('ПТ 18.09 14:20')
    expect(formatDateTime('2026-09-18T08:05:00')).toBe('ПТ 18.09.2026 08:05')
  })

  it('prefixes dates with the weekday', () => {
    expect(formatShortDate('2026-09-01')).toBe('ВТ 01.09')
    expect(formatShortDate('2026-09-07')).toBe('ПН 07.09')
    expect(formatShortDate('2026-09-06')).toBe('ВС 06.09')
  })

  it('renders a dash for empty or malformed values', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatDate('garbage')).toBe('—')
    expect(formatShortDate(undefined)).toBe('—')
    expect(formatTime(null)).toBe('—')
    expect(formatShortDateTime(null)).toBe('—')
    expect(formatDateTime(null)).toBe('—')
  })

  it('formats plan windows', () => {
    expect(formatWindow('2026-08-24', '2026-08-31')).toBe('ПН 24.08.2026 — ПН 31.08.2026')
    expect(formatWindow('2026-08-24', '2026-08-31', '–')).toBe('ПН 24.08.2026–ПН 31.08.2026')
    expect(formatWindow(null, null)).toBe('—')
  })

  it('formats delay intervals', () => {
    expect(formatDelay(null, null)).toBeNull()
    expect(formatDelay(4, null)).toBe('от 4 дн.')
    expect(formatDelay(4, 4)).toBe('4 дн.')
    expect(formatDelay(4, 6)).toBe('4–6 дн.')
  })

  it('formats file sizes', () => {
    expect(formatFileSize(512)).toBe('512 Б')
    expect(formatFileSize(24 * 1024)).toBe('24 КБ')
    expect(formatFileSize(3.5 * 1024 * 1024)).toBe('3,5 МБ')
  })

  it('gives today in local time as YYYY-MM-DD', () => {
    vi.useFakeTimers({ toFake: ['Date'], now: new Date(2026, 8, 7, 23, 30) })
    expect(todayIso()).toBe('2026-09-07')
    vi.useRealTimers()
  })

  it('parses ru dates with validation', () => {
    expect(parseRuDate('23.09', 2026)).toBe('2026-09-23')
    expect(parseRuDate(' 1.1.2027 ', 2026)).toBe('2027-01-01')
    expect(parseRuDate('31.02', 2026)).toBeNull()
    expect(parseRuDate('abc', 2026)).toBeNull()
  })

  it('parses ru date-times', () => {
    expect(parseRuDateTime('18.09.2026 8:05')).toBe('2026-09-18T08:05:00')
    expect(parseRuDateTime('18.09.2026 24:00')).toBeNull()
    expect(parseRuDateTime('18.09.2026 10:60')).toBeNull()
    expect(parseRuDateTime('18.09 10:00')).toBeNull()
    expect(parseRuDateTime('32.09.2026 10:00')).toBeNull()
  })

  it('describes relative days', () => {
    expect(daysAgo(0)).toBe('сегодня')
    expect(daysAgo(1)).toBe('вчера')
    expect(daysAgo(2)).toBe('2 дня назад')
    expect(daysAgo(5)).toBe('5 дней назад')
    expect(daysAgo(21)).toBe('21 день назад')
  })
})

describe('latestObservation', () => {
  it('takes the greatest date regardless of list order', () => {
    const list = [{ observed_on: '2023-10-13' }, { observed_on: '2023-06-19' }]
    expect(latestObservation(list)?.observed_on).toBe('2023-10-13')
    expect(latestObservation([...list].reverse())?.observed_on).toBe('2023-10-13')
    expect(latestObservation([])).toBeUndefined()
    expect(latestObservation(undefined)).toBeUndefined()
  })
})
