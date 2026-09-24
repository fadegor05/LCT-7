import { Link } from 'react-router'
import type { DeviationListItem } from '@/api/schemas'
import { ConfidenceMeter } from '@/components/ui/ConfidenceMeter'
import { Icon } from '@/components/ui/Icon'
import { Pill } from '@/components/ui/Pill'
import { formatDate } from '@/lib/format'
import { deviationTypeLabels } from '@/lib/labels'
import { SeverityBadge } from './SeverityBadge'
import styles from './DeviationRow.module.css'

interface DeviationListProps {
  items: readonly DeviationListItem[]
  /** Сквозной список по всем стройкам: в третьей колонке — стройка, иначе — заголовок отклонения. */
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
              {d.is_hypothesis && !showSite && d.decision === null && (
                <Pill tone="cautionDashed" size="sm">
                  Ждёт решения
                </Pill>
              )}
            </span>
            <span className={styles.what}>
              <span className="lab">
                {deviationTypeLabels[d.type]}
                {d.is_hypothesis && ' (гипотеза)'}
              </span>
              <span className="sm muted">{d.stage_name ?? 'Все этапы'}</span>
            </span>
            <span className="sm">{showSite ? d.site_name : d.title}</span>
            <span className="data">{formatDate(d.detected_at)}</span>
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
