import type { SiteSummary } from '@/api/schemas'
import { plural } from '@/lib/labels'

/** Родительный падеж после «от»/«до»: от 1 дня, от 4 дней, до 21 дня. */
const daysAfterPreposition = (n: number) => plural(n, ['дня', 'дней', 'дней'])

/** Итог по объекту (architecture §7.9): «Отставание X–Y дней», «Отклонений не выявлено», «Недостаточно данных». */
export function verdictText(
  summary: Pick<SiteSummary, 'verdict' | 'delay_days_min' | 'delay_days_max'>,
): string {
  switch (summary.verdict) {
    case 'behind': {
      const { delay_days_min: min, delay_days_max: max } = summary
      if (min === null && max === null) return 'Отставание'
      if (min === null) return `Отставание до ${max} ${daysAfterPreposition(max!)}`
      if (max === null) return `Отставание от ${min} ${daysAfterPreposition(min)}`
      // Слово согласуется с последним числом: 4 дня, 4–6 дней, 14–43 дня
      const days = plural(max, ['день', 'дня', 'дней'])
      return min === max ? `Отставание ${min} ${days}` : `Отставание ${min}–${max} ${days}`
    }
    case 'no_deviations':
      return 'Отклонений не выявлено'
    case 'insufficient_data':
      return 'Недостаточно данных'
  }
}
