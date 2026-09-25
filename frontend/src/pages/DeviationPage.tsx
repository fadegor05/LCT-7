import { Link } from 'react-router'
import { useDeviation, useDeviations } from '@/api/deviations'
import { useSchedule } from '@/api/schedule'
import { useSite } from '@/api/sites'
import { SiteShell } from '@/components/layout/SiteShell'
import { QueryState } from '@/components/ui/QueryState'
import { DeviationBody } from '@/features/deviations/DeviationBody'
import { SeverityCard } from '@/features/deviations/SeverityCard'
import styles from '@/features/deviations/Deviation.module.css'
import { deviationTitle, sortDeviations } from '@/lib/deviations'
import { useRequiredParam } from '@/lib/useParam'

/** Экран 7 · Отклонение (UC-5). Листание — по списку отклонений стройки в порядке важности. */
export function DeviationPage() {
  const siteId = useRequiredParam('siteId')
  const deviationId = useRequiredParam('deviationId')
  const site = useSite(siteId)
  const deviation = useDeviation(siteId, deviationId)
  const list = useDeviations(siteId)
  const schedule = useSchedule(siteId)

  const ordered = sortDeviations(list.data ?? [])
  const index = ordered.findIndex((d) => d.id === deviationId)
  const prev = index > 0 ? ordered[index - 1] : undefined
  const next = index >= 0 ? ordered[index + 1] : undefined
  const link = (id: string) => `/sites/${siteId}/deviations/${id}`

  return (
    <QueryState query={site}>
      {(siteData) => (
        <QueryState query={deviation}>
          {(d) => {
            const stageName = schedule.data?.stages.find((s) => s.id === d.stage_id)?.name ?? null
            const title = deviationTitle(d, stageName)
            return (
              <SiteShell
                site={siteData}
                crumb={title}
                title={title}
                subtitle={siteData.name}
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
                  <DeviationBody siteId={siteId} deviation={d} stageName={stageName} />
                  <div className={styles.aside}>
                    <SeverityCard siteId={siteId} deviation={d} />
                  </div>
                </div>
              </SiteShell>
            )
          }}
        </QueryState>
      )}
    </QueryState>
  )
}
