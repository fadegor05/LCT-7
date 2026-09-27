import { useSiteDeviations, useStageStatuses } from '@/api/deviations'
import { useSite } from '@/api/sites'
import { SectionHeader } from '@/components/layout/PageHeader'
import { SiteShell } from '@/components/layout/SiteShell'
import { Button } from '@/components/ui/Button'
import { QueryState } from '@/components/ui/QueryState'
import { DeviationList } from '@/features/deviations/DeviationList'
import { LastObservation } from '@/features/overview/LastObservation'
import { StageStatusTable } from '@/features/overview/StageStatusTable'
import { SummaryCards } from '@/features/overview/SummaryCards'
import { siteSubtitle } from '@/features/overview/siteSubtitle'
import { sortDeviations, visibleDeviations } from '@/lib/deviations'
import { plural } from '@/lib/labels'
import { useRequiredParam } from '@/lib/useParam'
import type { DeviationListItem } from '@/api/schemas'

const section = { display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' } as const

function deviationsDescription(items: readonly DeviationListItem[]): string {
  if (items.length === 0) return 'Отклонений не выявлено.'
  const critical = items.filter((d) => d.severity === 'critical').length
  const waiting = items.filter((d) => d.is_hypothesis && d.decision === null).length
  const parts = [
    critical > 0 && `${critical} ${plural(critical, ['критичное', 'критичных', 'критичных'])}`,
    waiting > 0 &&
      `${waiting} ${plural(waiting, ['гипотеза ждёт', 'гипотезы ждут', 'гипотез ждут'])} вашего решения`,
  ].filter(Boolean)
  return `${parts.length ? `${parts.join(', ')}. ` : ''}Сначала самые важные.`
}

/** Экран 5 · Обзор объекта (UC-4). Служит отчётом о ходе работ. */
export function SiteOverviewPage() {
  const siteId = useRequiredParam('siteId')
  const site = useSite(siteId)
  const deviations = useSiteDeviations(siteId)
  const statuses = useStageStatuses(siteId)

  return (
    <QueryState query={site}>
      {(data) => (
        <SiteShell
          site={data}
          subtitle={siteSubtitle(data)}
          actions={
            <Button variant="ghost" onClick={() => window.print()}>
              Печатная версия
            </Button>
          }
        >
          <SummaryCards site={data} />

          <section style={section}>
            <QueryState query={deviations}>
              {(items) => {
                const visible = sortDeviations(visibleDeviations(items))
                return (
                  <>
                    <SectionHeader
                      title={`Отклонения: ${visible.length}`}
                      description={deviationsDescription(visible)}
                    />
                    <DeviationList items={visible} />
                  </>
                )
              }}
            </QueryState>
          </section>

          <section style={section}>
            <SectionHeader
              title="Этапы"
              description="Факт берётся по датам наблюдений маркерной техники. «Не начата» ставится только при высокой наблюдаемости или если этап ещё не по плану."
            />
            <QueryState query={statuses}>
              {(rows) => <StageStatusTable siteId={siteId} rows={rows} />}
            </QueryState>
          </section>

          <LastObservation siteId={siteId} />
        </SiteShell>
      )}
    </QueryState>
  )
}
