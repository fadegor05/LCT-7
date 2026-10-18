import { formatWindow } from '@/lib/format'
import type { DeviationItem } from '@/lib/deviations'
import { deviationTypeLabels, levelLabels, severityLabels } from '@/lib/labels'
import styles from './Report.module.css'

/** Отклонения в отчёте: что за отклонение, где и когда, на каком основании и насколько уверенно. */
export function ReportDeviations({ items }: { items: readonly DeviationItem[] }) {
  if (items.length === 0) return <p>Отклонений нет.</p>
  return (
    <table className={styles.table}>
      <caption className="srOnly">Отклонения</caption>
      <thead>
        <tr>
          <th scope="col">Важность</th>
          <th scope="col">Отклонение</th>
          <th scope="col">Этап</th>
          <th scope="col">Период</th>
          <th scope="col">Основание</th>
          <th scope="col">Уверенность</th>
        </tr>
      </thead>
      <tbody>
        {items.map((d) => (
          <tr key={d.id}>
            <td>
              <span className={d.severity === 'critical' ? styles.critical : undefined}>
                {severityLabels[d.severity]}
              </span>
            </td>
            <td>
              <strong>{deviationTypeLabels[d.type]}</strong>
              {d.is_hypothesis && <span className={styles.sub}>Гипотеза: проверьте снимки</span>}
            </td>
            <td>{d.stage_name ?? 'Все этапы'}</td>
            <td className={styles.nowrap}>{formatWindow(d.period_start, d.period_end, '–')}</td>
            <td>
              <span>Ожидалось: {d.expected}</span>
              <span className={styles.sub}>
                Наблюдается: {d.observed}. {d.limits_text}
              </span>
            </td>
            <td>{levelLabels[d.confidence]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
