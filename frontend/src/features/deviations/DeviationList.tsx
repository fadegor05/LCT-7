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

/** Заголовок без повтора типа: «Неполный комплект: не виден самосвал» под «Неполный комплект». */
function detail(d: DeviationItem): string {
  const title = d.title ?? formatWindow(d.period_start, d.period_end)
  // «Отставание: …» под «Отставание от графика», «Простой: …» под «Простой техники»
  const cut = title.indexOf(': ')
  const head = cut > 0 ? title.slice(0, cut) : ''
  return head && deviationTypeLabels[d.type].startsWith(head) ? title.slice(cut + 2) : title
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
                {d.stage_name === undefined ? detail(d) : (d.stage_name ?? 'Все этапы')}
              </span>
            </span>
            {/* Что именно: машина и этап (clean-mvp), а не только тип — иначе три
                «Несоответствия этапу» подряд не отличить */}
            <span className="sm">{showSite ? d.site_name : detail(d)}</span>
            {/* Дата наблюдения, а не пересчёта: «ПН 19.10» у всех строк ничего не говорил */}
            <span className="data">{formatDate(d.period_end)}</span>
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
