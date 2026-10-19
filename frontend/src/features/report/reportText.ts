import type { StageStatus, SiteSummary } from '@/api/schemas'
import { levelLabels } from '@/lib/labels'
import { stageDelayText } from '@/lib/format'

/** Пояснение к итогу: тот же смысл, что на обзоре, — что за вывод и на чём он держится. */
export const VERDICT_EXPLANATION: Record<
  Exclude<SiteSummary['verdict'], 'insufficient_data'>,
  string
> = {
  behind:
    'Худший интервал по этапам с отставанием. Отставание измерено по датам снимков: точность не выше частоты съёмки.',
  no_deviations: 'Этапы с данными идут по графику.',
}

export const INSUFFICIENT_EXPLANATION =
  'Наблюдений не хватает для вывода. Что именно не собрано, см. в разделе «Состояние данных».'

/** Чего отчёт не утверждает: границы метода, а не оговорка на всякий случай. */
export const LIMITS_TEXT =
  'Отставание считается по датам, когда на кадрах видна маркерная техника этапа: это нижняя граница, точность не выше частоты съёмки. Простой и «вне зоны» — гипотезы, их подтверждает инженер. Отсутствие техники на снимках не доказывает, что работы не велись: машина могла работать вне кадра или вне времени съёмки.'

/** 2026-09-18 → 18.09.2026 (для заголовка документа и даты формирования). */
export function stampDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}

/** Строка «отставание 4 дн. · уверенность высокая» под статусом этапа. */
export function stageBasis(row: StageStatus): string {
  const delay = row.delay_days !== null ? stageDelayText(row) : null
  const confidence = row.confidence
    ? `уверенность ${levelLabels[row.confidence].toLowerCase()}`
    : null
  return [delay, confidence].filter(Boolean).join(' · ')
}
