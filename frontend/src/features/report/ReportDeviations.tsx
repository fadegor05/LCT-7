import { formatPeriod } from '@/lib/format'
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
          <th scope="col">Уверенность</th>
          <th scope="col">Решение инженера</th>
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
              {/* Заголовок по машине, под ним тип — как в clean-mvp */}
              <strong>{d.title ?? deviationTypeLabels[d.type]}</strong>
              <span className={styles.sub}>
                {deviationTypeLabels[d.type]}
                {d.is_hypothesis && ' (гипотеза)'}
              </span>
            </td>
            <td>{d.stage_name ?? 'Все этапы'}</td>
            <td className={styles.nowrap}>{formatPeriod(d.period_start, d.period_end)}</td>
            <td>{levelLabels[d.confidence]}</td>
            <td>
              {!d.is_hypothesis
                ? '—'
                : d.decision?.decision === 'confirmed'
                  ? 'Проверено инженером'
                  : 'Ждёт решения'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
