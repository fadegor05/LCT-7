import type { Deviation, Stage } from '@/api/schemas'
import { deviationTypeLabels } from './labels'

/** Порядок списков отклонений (architecture §7.7): сначала критичные, внутри уровня свежие. */
export function sortDeviations<
  T extends Pick<Deviation, 'severity' | 'created_at'> & { period_end?: string },
>(items: readonly T[]): T[] {
  return [...items].sort((a, b) => {
    if (a.severity !== b.severity) return a.severity === 'critical' ? -1 : 1
    // Свежее — по дате наблюдения: все строки одного пересчёта созданы в одну секунду
    return (b.period_end ?? b.created_at).localeCompare(a.period_end ?? a.created_at)
  })
}

/** Заголовок отклонения: backend отдаёт тип, а не текст — собираем по шаблону. */
export function deviationTitle(
  d: Pick<Deviation, 'type' | 'is_hypothesis'>,
  stageName?: string | null,
): string {
  const title = `${deviationTypeLabels[d.type]}${d.is_hypothesis ? ' (гипотеза)' : ''}`
  return stageName ? `${title} · ${stageName}` : title
}

/**
 * Отклонение в списке: к ответу backend фронт добавляет стройку и название этапа.
 * `stage_name` не задан — этап неизвестен (сквозной список), вместо него показывается период.
 */
export type DeviationItem = Deviation & {
  site_id: string
  site_name?: string
  stage_name?: string | null
}

/** Отклонения стройки с названием этапа из графика. */
export function withStages(
  siteId: string,
  items: readonly Deviation[],
  stages: readonly Stage[],
): DeviationItem[] {
  return items.map((d) => ({
    ...d,
    site_id: siteId,
    stage_name: d.stage_id ? (stages.find((s) => s.id === d.stage_id)?.name ?? null) : null,
  }))
}
