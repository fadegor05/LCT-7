/** Подписи перечислений в интерфейсе (DataModel §5.7, architecture §7). Меняются только согласованно. */
import type {
  Activity,
  DateSource,
  DeviationType,
  EvidenceState,
  Level,
  ObjectType,
  RuleKind,
  Severity,
  SourceType,
  TimeIssue,
  WorkDays,
} from '@/api/schemas'

export const objectTypeLabels: Record<ObjectType, string> = {
  housing: 'Жильё',
  education: 'Образование',
  health: 'Здравоохранение',
  other: 'Другое',
}

export const workDaysLabels: Record<WorkDays, string> = {
  mon_fri: 'Пн–Пт',
  mon_sat: 'Пн–Сб',
  all: 'Ежедневно',
}

export const sourceTypeLabels: Record<SourceType, string> = {
  photo: 'Фото',
  video: 'Видео',
  stream: 'Стрим',
}

export const dateSourceLabels: Record<DateSource, string> = {
  exif: 'Метаданные',
  stamp: 'Штамп',
  manual: 'Вручную',
  video: 'Видео · старт + смещение',
  stream: 'Поток',
}

export const timeIssueLabels: Record<TimeIssue, string> = {
  stamp_unrecognized: 'Штамп не распознан',
  no_metadata: 'Метаданных нет',
  stamp_cropped: 'Штамп обрезан',
  stamp_low_conf: 'Штамп читается неуверенно',
  clip_no_start: 'Клип без времени начала',
}

export const ruleKindLabels: Record<RuleKind, string> = {
  normative: 'Нормативная',
  logical: 'Логическая',
  auxiliary: 'Вспомогательная',
}

export const evidenceLabels: Record<EvidenceState, string> = {
  marker_confirmed: 'Подтверждено маркером',
  compatible: 'Совместимо',
  none: 'Нет',
  unknown: 'Неизвестно',
}

export const activityLabels: Record<Activity, string> = {
  working: 'Работает',
  idle: 'Простаивает',
  unknown: 'Неизвестно',
}

export const deviationTypeLabels: Record<DeviationType, string> = {
  missing_equipment: 'Нет нужной техники',
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

export const pluralFrames = (n: number) => `${n} ${plural(n, ['кадр', 'кадра', 'кадров'])}`
export const pluralMachines = (n: number) => `${n} ${plural(n, ['машина', 'машины', 'машин'])}`
export const pluralWorks = (n: number) => `${n} ${plural(n, ['работа', 'работы', 'работ'])}`
