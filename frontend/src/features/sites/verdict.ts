import type { SiteSummary } from '@/api/schemas'
import { formatDelay } from '@/lib/format'

/** Итог по объекту (architecture §7.9): «Отставание X–Y дней», «Отклонений не выявлено», «Недостаточно данных». */
export function verdictText(
  summary: Pick<SiteSummary, 'verdict' | 'delay_days_min' | 'delay_days_max'>,
): string {
  switch (summary.verdict) {
    case 'behind': {
      const delay = formatDelay(summary.delay_days_min, summary.delay_days_max)
      return delay ? `Отставание ${delay.replace(' дн.', ' дней')}` : 'Отставание'
    }
    case 'no_deviations':
      return 'Отклонений не выявлено'
    case 'insufficient_data':
      return 'Недостаточно данных'
  }
}
