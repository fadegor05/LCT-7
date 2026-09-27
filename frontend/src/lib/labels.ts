/** Подписи перечислений в интерфейсе (architecture §7). Меняются только согласованно. */
import type {
  Activity,
  DateSource,
  DeviationType,
  Level,
  Obligation,
  ProcessingStatus,
  Severity,
} from '@/api/schemas'

export const dateSourceLabels: Record<DateSource, string> = {
  channel: 'Канал',
  metadata: 'Метаданные',
  stamp: 'Штамп',
  neighbours: 'По соседним снимкам',
  manual: 'Вручную',
}

export const processingStatusLabels: Record<ProcessingStatus, string> = {
  pending: 'Не обработан',
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
