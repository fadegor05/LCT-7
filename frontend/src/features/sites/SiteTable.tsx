import { Link } from 'react-router'
import type { Site } from '@/api/schemas'
import { Pill } from '@/components/ui/Pill'
import { daysAgo, formatDate } from '@/lib/format'
import { ObservabilityBadge, VerdictBadge } from './SiteBadges'
import styles from './SiteTable.module.css'

/** Порог «Данные устарели» в днях — в проде приходит из конфигурации сервера (§9). */
const STALE_DAYS = 7

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
      {sites.map((site) => {
        const s = site.summary
        return (
          <Link key={site.id} to={`/sites/${site.id}`} className={`${styles.grid} ${styles.row}`}>
            <span className={styles.name}>
              <span className={styles.title}>{site.name}</span>
              {site.address && <span className="sm muted">{site.address}</span>}
            </span>
            <span>
              <VerdictBadge summary={s} />
            </span>
            <span className={`data ${styles.count}`} aria-label="Критично">
              {s?.critical_count ?? 0}
            </span>
            <span className={`data ${styles.count}`} aria-label="Внимание">
              {s?.attention_count ?? 0}
            </span>
            <span className={styles.last}>
              <span className="data">{formatDate(s?.last_frame_at)}</span>
              {s?.data_age_days != null &&
                (s.data_age_days > STALE_DAYS ? (
                  <Pill tone="caution" icon="clock">
                    Данные устарели · {s.data_age_days} дн.
                  </Pill>
                ) : (
                  <span className="sm muted">{daysAgo(s.data_age_days)}</span>
                ))}
            </span>
            <span>{s ? <ObservabilityBadge level={s.observability} /> : '—'}</span>
          </Link>
        )
      })}
    </section>
  )
}
