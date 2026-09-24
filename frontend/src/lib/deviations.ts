import type { DeviationListItem } from '@/api/schemas'

/** Порядок списков отклонений (architecture §7.7): сначала критичные, внутри уровня свежие. */
export function sortDeviations<T extends Pick<DeviationListItem, 'severity' | 'detected_at'>>(
  items: readonly T[],
): T[] {
  return [...items].sort((a, b) => {
    if (a.severity !== b.severity) return a.severity === 'critical' ? -1 : 1
    return b.detected_at.localeCompare(a.detected_at)
  })
}

/** Отклонения в списках: «Не подтверждается» уходит в архив и не показывается (§7.10). */
export function visibleDeviations<T extends Pick<DeviationListItem, 'decision'>>(
  items: readonly T[],
): T[] {
  return items.filter((d) => d.decision !== 'rejected')
}
