import { Link } from 'react-router'
import { ConfidenceMeter } from '@/components/ui/ConfidenceMeter'
import { Icon } from '@/components/ui/Icon'
import type { DeviationItem } from '@/lib/deviations'
import { formatDate, formatWindow } from '@/lib/format'
import { deviationTypeLabels } from '@/lib/labels'
import { SeverityBadge } from './SeverityBadge'
import styles from './DeviationRow.module.css'

interface DeviationListProps {
  items: readonly DeviationItem[]
  /** Сквозной список по всем стройкам: в третьей колонке — стройка, иначе — период. */
  showSite?: boolean
}

/** Список отклонений; порядок задаёт вызывающий (sortDeviations). */
export function DeviationList({ items, showSite }: DeviationListProps) {
  if (items.length === 0) {
    return (
      <div className={styles.list}>
        <p className={`${styles.empty} muted`}>Отклонений не выявлено.</p>
      </div>
    )
  }
  return (
    <ul className={styles.list} aria-label="Отклонения">
      {items.map((d) => (
        <li key={d.id}>
          <Link to={`/sites/${d.site_id}/deviations/${d.id}`} className={styles.row}>
            <span className={styles.tags}>
              <SeverityBadge severity={d.severity} />
            </span>
            <span className={styles.what}>
              <span className="lab">
                {deviationTypeLabels[d.type]}
                {d.is_hypothesis && ' (гипотеза)'}
              </span>
              <span className="sm muted">
                {d.stage_name === undefined
                  ? formatWindow(d.period_start, d.period_end)
                  : (d.stage_name ?? 'Все этапы')}
              </span>
            </span>
            <span className="sm">
              {showSite ? d.site_name : formatWindow(d.period_start, d.period_end)}
            </span>
            <span className="data">{formatDate(d.created_at)}</span>
            <ConfidenceMeter level={d.confidence} />
            <span className={styles.chevron}>
              <Icon name="chevronRight" />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}
