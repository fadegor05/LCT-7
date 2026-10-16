import { Link } from 'react-router'
import { useSummary } from '@/api/deviations'
import { useObservations } from '@/api/frames'
import type { Site } from '@/api/schemas'
import { formatDate, latestObservation } from '@/lib/format'
import { ObservabilityBadge, VerdictBadge } from './SiteBadges'
import styles from './SiteTable.module.css'

/** Строка стройки: итог и последнее наблюдение приходят отдельными запросами по стройке. */
function SiteRow({ site }: { site: Site }) {
  const summary = useSummary(site.id).data
  const last = latestObservation(useObservations(site.id).data)
  return (
    <Link to={`/sites/${site.id}`} className={`${styles.grid} ${styles.row}`}>
      <span className={styles.name}>
        <span className={styles.title}>{site.name}</span>
        {site.address && <span className="sm muted">{site.address}</span>}
      </span>
      <span>
        <VerdictBadge summary={summary} />
      </span>
      <span className={`data ${styles.count}`} aria-label="Критично">
        {summary?.critical_count ?? 0}
      </span>
      <span className={`data ${styles.count}`} aria-label="Внимание">
        {summary?.attention_count ?? 0}
      </span>
      <span className={`data ${styles.last}`}>{formatDate(last?.observed_on)}</span>
      <span>{last ? <ObservabilityBadge level={last.observability} /> : '—'}</span>
    </Link>
  )
}

export function SiteTable({ sites }: { sites: readonly Site[] }) {
  return (
    <section className={styles.table} aria-label="Список строек">
      <div className={`${styles.grid} ${styles.head} sm muted lab`} aria-hidden="true">
        <span>Объект</span>
        <span>Итог</span>
        <span>Критично</span>
        <span>Внимание</span>
        <span>Последнее наблюдение</span>
        <span>Наблюдаемость</span>
      </div>
      {sites.map((site) => (
        <SiteRow key={site.id} site={site} />
      ))}
    </section>
  )
}
