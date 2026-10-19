import { useDeviation, useDeviations } from '@/api/deviations'
import { useSchedule } from '@/api/schedule'
import { useSite } from '@/api/sites'
import { SiteQueryState } from '@/components/layout/SiteQueryState'
import { SiteShell } from '@/components/layout/SiteShell'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { QueryState } from '@/components/ui/QueryState'
import { DecisionPanel } from '@/features/deviations/DecisionPanel'
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
    <SiteQueryState query={site}>
      {(siteData) => (
        <QueryState query={deviation}>
          {(d) => {
            const stageName = schedule.data?.stages.find((s) => s.id === d.stage_id)?.name ?? null
            // Заголовок по машине (clean-mvp); у прежних строк — тип и этап
            const title = d.title ?? deviationTitle(d, stageName)
            const causeName = d.cause_stage_id
              ? (schedule.data?.stages.find((s) => s.id === d.cause_stage_id)?.name ?? null)
              : null
            return (
              <SiteShell
                site={siteData}
                crumb={title}
                title={title}
                subtitle={siteData.name}
                actions={
                  index >= 0 && (
                    <nav className={styles.nav} aria-label="Листание отклонений">
                      <span className={`sm muted ${styles.counter}`}>
                        {index + 1} из {ordered.length}
                      </span>
                      {/* На краях списка кнопка остаётся, но выключена: блок не прыгает */}
                      {prev ? (
                        <ButtonLink to={link(prev.id)} variant="ghost" size="sm" icon="chevronLeft">
                          Предыдущее
                        </ButtonLink>
                      ) : (
                        <Button variant="ghost" size="sm" icon="chevronLeft" disabled>
                          Предыдущее
                        </Button>
                      )}
                      {next ? (
                        <ButtonLink to={link(next.id)} variant="ghost" size="sm">
                          Следующее
                          <Icon name="chevronRight" />
                        </ButtonLink>
                      ) : (
                        <Button variant="ghost" size="sm" disabled>
                          Следующее
                          <Icon name="chevronRight" />
                        </Button>
                      )}
                    </nav>
                  )
                }
              >
                <div className={styles.layout}>
                  <DeviationBody
                    siteId={siteId}
                    deviation={d}
                    stageName={stageName}
                    causeName={causeName}
                  />
                  <div className={styles.aside}>
                    <SeverityCard siteId={siteId} deviation={d} />
                    {d.is_hypothesis && <DecisionPanel siteId={siteId} deviation={d} />}
                  </div>
                </div>
              </SiteShell>
            )
          }}
        </QueryState>
      )}
    </SiteQueryState>
  )
}
