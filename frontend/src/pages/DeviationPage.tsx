import { Link } from 'react-router'
import { useDeviation, useSiteDeviations } from '@/api/deviations'
import { useSite } from '@/api/sites'
import { SiteShell } from '@/components/layout/SiteShell'
import { QueryState } from '@/components/ui/QueryState'
import { DecisionPanel } from '@/features/deviations/DecisionPanel'
import { DeviationBody } from '@/features/deviations/DeviationBody'
import { SeverityCard } from '@/features/deviations/SeverityCard'
import styles from '@/features/deviations/Deviation.module.css'
import { dataAsOf } from '@/features/overview/siteSubtitle'
import { sortDeviations, visibleDeviations } from '@/lib/deviations'
import { useRequiredParam } from '@/lib/useParam'

/** Экран 7 · Отклонение (UC-5, UC-10). Листание — по списку отклонений стройки в порядке важности. */
export function DeviationPage() {
  const siteId = useRequiredParam('siteId')
  const deviationId = useRequiredParam('deviationId')
  const site = useSite(siteId)
  const deviation = useDeviation(deviationId)
  const list = useSiteDeviations(siteId)

  const ordered = sortDeviations(visibleDeviations(list.data ?? []))
  const index = ordered.findIndex((d) => d.id === deviationId)
  const prev = index > 0 ? ordered[index - 1] : undefined
  const next = index >= 0 ? ordered[index + 1] : undefined
  const link = (id: string) => `/sites/${siteId}/deviations/${id}`

  return (
    <QueryState query={site}>
      {(siteData) => (
        <QueryState query={deviation}>
          {(d) => (
            <SiteShell
              site={siteData}
              crumb={d.title}
              title={d.title}
              subtitle={[siteData.name, dataAsOf(siteData)].filter(Boolean).join(' · ')}
              actions={
                index >= 0 && (
                  <nav className={styles.nav} aria-label="Листание отклонений">
                    <span className="sm muted">
                      {index + 1} из {ordered.length}
                    </span>
                    {prev && <Link to={link(prev.id)}>‹ Предыдущее</Link>}
                    {next && <Link to={link(next.id)}>Следующее ›</Link>}
                  </nav>
                )
              }
            >
              <div className={styles.layout}>
                <DeviationBody deviation={d} />
                <div className={styles.aside}>
                  {d.is_hypothesis && <DecisionPanel deviation={d} />}
                  <SeverityCard deviation={d} />
                </div>
              </div>
            </SiteShell>
          )}
        </QueryState>
      )}
    </QueryState>
  )
}
