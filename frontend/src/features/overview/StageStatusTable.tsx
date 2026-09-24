import { Link } from 'react-router'
import type { StageStatus } from '@/api/schemas'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { formatDelay, formatWindow } from '@/lib/format'
import { levelLabels } from '@/lib/labels'
import styles from './Overview.module.css'

function meta(row: StageStatus): string | null {
  const parts = [
    formatDelay(row.delay_days_min, row.delay_days_max),
    row.confidence && `уверенность ${levelLabels[row.confidence].toLowerCase()}`,
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : null
}

/** Таблица «Этапы» обзора (UC-4): план, факт по маркеру, статус, связанные отклонения. */
export function StageStatusTable({
  siteId,
  rows,
}: {
  siteId: string
  rows: readonly StageStatus[]
}) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className="srOnly">Статусы этапов</caption>
        <thead>
          <tr>
            <th scope="col">Этап</th>
            <th scope="col">План</th>
            <th scope="col">Факт по маркеру</th>
            <th scope="col">Статус и отклонения</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.stage_id}>
              <th scope="row">
                <div className={styles.stageName}>
                  <span style={{ fontSize: 16 }}>{row.stage_name}</span>
                  {row.basis_text && <span className="sm muted">{row.basis_text}</span>}
                </div>
              </th>
              <td className="data">{formatWindow(row.planned_start, row.planned_end, '–')}</td>
              <td className="data">{row.fact_label ?? '—'}</td>
              <td>
                <div className={styles.statusCell}>
                  <StatusBadge status={row.status} />
                  {row.deviations.map((d) => (
                    <Link key={d.id} to={`/sites/${siteId}/deviations/${d.id}`} className="sm">
                      {d.title}
                    </Link>
                  ))}
                  {meta(row) && <span className="sm muted">{meta(row)}</span>}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
