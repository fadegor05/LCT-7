/** Подписи перечислений в интерфейсе (architecture §7). Меняются только согласованно. */
import type {
  Activity,
  DateSource,
  DeviationType,
  Level,
  ObjectType,
  Obligation,
  ProcessingStatus,
  Severity,
} from '@/api/schemas'

export const dateSourceLabels: Record<DateSource, string> = {
  channel: 'Канал',
  metadata: 'Метаданные',
  stamp: 'Штамп',
  filename: 'Из имени файла',
  neighbours: 'По соседним снимкам',
  manual: 'Вручную',
}

export const objectTypeLabels: Record<ObjectType, string> = {
  housing: 'Жильё',
  education: 'Образование',
  health: 'Здравоохранение',
  other: 'Другое',
}

/** Рабочие дни — пресеты макета (clean-mvp). */
export const WORKDAY_PRESETS = [
  { value: 'weekdays', label: 'Пн–Пт', days: [0, 1, 2, 3, 4] },
  { value: 'six', label: 'Пн–Сб', days: [0, 1, 2, 3, 4, 5] },
  { value: 'daily', label: 'Ежедневно', days: [0, 1, 2, 3, 4, 5, 6] },
] as const

export type WorkdayPreset = (typeof WORKDAY_PRESETS)[number]['value']

/** Пресет по списку дней; `null` — набор не из макета (задан через API). */
export function workdayPreset(days: readonly number[]): WorkdayPreset | null {
  const key = [...days].sort((a, b) => a - b).join(',')
  return WORKDAY_PRESETS.find((p) => p.days.join(',') === key)?.value ?? null
}

const WEEKDAYS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']

/** «Пн–Пт», «Ежедневно» или перечень дней набора не из макета. */
export function workdaysText(days: readonly number[]): string {
  const preset = WORKDAY_PRESETS.find((p) => p.value === workdayPreset(days))
  return preset
    ? preset.label
    : [...days]
        .sort((a, b) => a - b)
        .map((d) => WEEKDAYS[d])
        .join(', ')
}

export const processingStatusLabels: Record<ProcessingStatus, string> = {
  pending: 'Не обработан',
  queued: 'В очереди',
  processing: 'Обрабатывается',
  done: 'Обработан',
  failed: 'Ошибка детектора',
}

export const obligationLabels: Record<Obligation, string> = {
  normative: 'Нормативная',
  logical: 'Логическая',
  auxiliary: 'Вспомогательная',
}

export const activityLabels: Record<Activity, string> = {
  works: 'Работает',
  idle: 'Простаивает',
  unknown: 'Неизвестно',
}

export const deviationTypeLabels: Record<DeviationType, string> = {
  missing_equipment: 'Нет нужной техники',
  missing_logical_equipment: 'Нет ожидаемой техники',
  stage_mismatch: 'Несоответствие этапу',
  stale_data: 'Данные устарели',
  idle: 'Простой техники',
  extra_equipment: 'Лишняя техника',
  out_of_zone: 'Вне рабочей зоны',
  no_progress: 'Нет прогресса',
  behind_schedule: 'Отставание от графика',
  incomplete_kit: 'Неполный комплект',
}

export const severityLabels: Record<Severity, string> = {
  critical: 'Критично',
  attention: 'Внимание',
}

export const levelLabels: Record<Level, string> = {
  high: 'Высокая',
  medium: 'Средняя',
  low: 'Низкая',
}

/** Русское склонение: plural(5, ['кадр', 'кадра', 'кадров']) → 'кадров'. */
export function plural(n: number, forms: readonly [string, string, string]): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return forms[0]
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1]
  return forms[2]
}

export const pluralPhotos = (n: number) => `${n} ${plural(n, ['снимок', 'снимка', 'снимков'])}`
