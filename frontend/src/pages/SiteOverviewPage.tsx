import { Link } from 'react-router'
import { useDeviations, useStageStatuses } from '@/api/deviations'
import { useSchedule } from '@/api/schedule'
import { useSite } from '@/api/sites'
import { SectionHeader } from '@/components/layout/PageHeader'
import { SiteQueryState } from '@/components/layout/SiteQueryState'
import { SiteShell } from '@/components/layout/SiteShell'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { QueryState } from '@/components/ui/QueryState'
import { AssistantPanel } from '@/features/assistant/AssistantPanel'
import { DeviationList } from '@/features/deviations/DeviationList'
import { LastObservation } from '@/features/overview/LastObservation'
import { StageStatusTable } from '@/features/overview/StageStatusTable'
import { SummaryCards } from '@/features/overview/SummaryCards'
import { siteSubtitle } from '@/features/overview/siteSubtitle'
import { sortDeviations, withStages, type DeviationItem } from '@/lib/deviations'
import { plural } from '@/lib/labels'
import { useRequiredParam } from '@/lib/useParam'

const section = { display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' } as const

function deviationsDescription(items: readonly DeviationItem[]): string | undefined {
  // Пустой список сам пишет «Отклонений не выявлено» — не повторяем это в подзаголовке.
  if (items.length === 0) return undefined
  const critical = items.filter((d) => d.severity === 'critical').length
  const hypotheses = items.filter((d) => d.is_hypothesis).length
  const parts = [
    critical > 0 && `${critical} ${plural(critical, ['критичное', 'критичных', 'критичных'])}`,
    hypotheses > 0 &&
      `${hypotheses} ${plural(hypotheses, ['гипотеза', 'гипотезы', 'гипотез'])}: проверьте снимки`,
  ].filter(Boolean)
  return `${parts.length ? `${parts.join(', ')}. ` : ''}Сначала самые важные.`
}

function Stages({ siteId, deviations }: { siteId: string; deviations: DeviationItem[] }) {
  const schedule = useSchedule(siteId)
  const statuses = useStageStatuses(siteId, Boolean(schedule.data))
  if (schedule.isPending) return null
  if (!schedule.data) {
    return (
      <Callout tone="caution" title="График не загружен">
        Без графика этапы не оцениваются.{' '}
        <Link to={`/sites/${siteId}/setup`}>Загрузить график</Link>
      </Callout>
    )
  }
  const stages = schedule.data.stages
  return (
    <QueryState query={statuses}>
      {(rows) => (
        <StageStatusTable siteId={siteId} rows={rows} stages={stages} deviations={deviations} />
      )}
    </QueryState>
  )
}

/** Экран 5 · Обзор объекта (UC-4). Служит отчётом о ходе работ. */
export function SiteOverviewPage() {
  const siteId = useRequiredParam('siteId')
  const site = useSite(siteId)
  const deviations = useDeviations(siteId)
  const schedule = useSchedule(siteId)
  const items = sortDeviations(
    withStages(siteId, deviations.data ?? [], schedule.data?.stages ?? []),
  )

  return (
    <SiteQueryState query={site}>
      {(data) => (
        <SiteShell
          site={data}
          subtitle={siteSubtitle(data)}
          actions={
            <>
              <Button variant="ghost" onClick={() => window.print()}>
                Печатная версия
              </Button>
              <ButtonLink
                to={`/sites/${siteId}/report?print=1`}
                target="_blank"
                variant="secondary"
              >
                Скачать отчёт PDF
              </ButtonLink>
            </>
          }
          aside={<AssistantPanel siteId={siteId} />}
        >
          <SummaryCards siteId={siteId} />

          <section style={section}>
            <QueryState query={deviations}>
              {() => (
                <>
                  <SectionHeader
                    title={`Отклонения: ${items.length}`}
                    description={deviationsDescription(items)}
                  />
                  <DeviationList items={items} />
                </>
              )}
            </QueryState>
          </section>

          <section style={section}>
            <SectionHeader
              title="Этапы"
              description="Статус выводится по датам наблюдений маркерной (нормативной) техники. «Не начата» ставится только при высокой наблюдаемости или если этап ещё не по плану."
            />
            <Stages siteId={siteId} deviations={items} />
          </section>

          <LastObservation siteId={siteId} />
        </SiteShell>
      )}
    </SiteQueryState>
  )
}
