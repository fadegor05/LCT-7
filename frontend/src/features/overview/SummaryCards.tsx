import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { useSummary } from '@/api/deviations'
import { useObservations, useUndatedPhotos } from '@/api/frames'
import { useSchedule } from '@/api/schedule'
import type { SiteSummary } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { formatDate, latestObservation } from '@/lib/format'
import { levelLabels, plural } from '@/lib/labels'
import { verdictText } from '@/features/sites/verdict'
import styles from './Overview.module.css'

const EXPLANATION: Record<Exclude<SiteSummary['verdict'], 'insufficient_data'>, string> = {
  behind:
    'Худший интервал по этапам с отставанием. Отставание измерено по датам снимков: точность не выше частоты съёмки.',
  no_deviations: 'Этапы с данными идут по графику.',
}

/** «Недостаточно данных» — называем настоящую причину, а не перечисляем все возможные. */
function InsufficientReason({ siteId }: { siteId: string }): ReactNode {
  const schedule = useSchedule(siteId)
  const observations = useObservations(siteId)
  const undated = useUndatedPhotos(siteId)
  if (schedule.isPending || observations.isPending || undated.isPending) {
    return 'Нет оценённых этапов.'
  }
  if (!schedule.data) {
    return (
      <>
        График не загружен: этапы не с чем сравнить.{' '}
        <Link to={`/sites/${siteId}/setup`}>Загрузить график</Link>
      </>
    )
  }
  if ((observations.data?.length ?? 0) > 0) {
    return 'Наблюдений не хватает для вывода: наблюдаемость низкая или этапы не проверяются по технике.'
  }
  const count = undated.data?.length ?? 0
  if (count > 0) {
    return (
      <>
        Нет наблюдений: у {count} {plural(count, ['снимка', 'снимков', 'снимков'])} не задана дата.{' '}
        <Link to={`/sites/${siteId}/observations#no-date`}>Задать дату</Link>
      </>
    )
  }
  return (
    <>
      Нет наблюдений: снимки ещё не загружены.{' '}
      <Link to={`/sites/${siteId}/observations`}>К наблюдениям</Link>
    </>
  )
}

function VerdictCard({ siteId, summary }: { siteId: string; summary: SiteSummary }) {
  return (
    <Card aria-labelledby="verdict-title">
      <p id="verdict-title" className="lab muted">
        Итог по объекту
      </p>
      <p
        className={[styles.verdict, summary.verdict === 'behind' && styles.verdictBehind]
          .filter(Boolean)
          .join(' ')}
      >
        {verdictText(summary)}
      </p>
      <p className="sm">
        {summary.verdict === 'insufficient_data' ? (
          <InsufficientReason siteId={siteId} />
        ) : (
          EXPLANATION[summary.verdict]
        )}
      </p>
    </Card>
  )
}

function DataStateCard({ siteId }: { siteId: string }) {
  const observations = useObservations(siteId).data ?? []
  const undated = useUndatedPhotos(siteId).data?.length ?? 0
  const last = latestObservation(observations)
  const dated = observations.reduce((sum, o) => sum + o.photo_count, 0)
  return (
    <Card aria-labelledby="data-state-title">
      <p id="data-state-title" className="lab muted">
        Состояние данных
      </p>
      <p className="lab">
        {last
          ? `Наблюдаемость ${levelLabels[last.observability].toLowerCase()}`
          : 'Наблюдений пока нет'}
      </p>
      <dl className={styles.kv}>
        <div>
          <dt>Последнее наблюдение</dt>
          <dd className="data">{formatDate(last?.observed_on)}</dd>
        </div>
        <div>
          <dt>Дней наблюдений</dt>
          <dd className="data">{observations.length}</dd>
        </div>
        <div>
          <dt>Всего снимков</dt>
          <dd className="data">{dated + undated}</dd>
        </div>
        <div>
          <dt>Без даты</dt>
          <dd className="data">{undated}</dd>
        </div>
      </dl>
      <Link to={`/sites/${siteId}/observations`} className="sm">
        Снимки и наблюдения →
      </Link>
    </Card>
  )
}

export function SummaryCards({ siteId }: { siteId: string }) {
  const summary = useSummary(siteId)
  return (
    <div className={styles.top}>
      {summary.data && <VerdictCard siteId={siteId} summary={summary.data} />}
      <DataStateCard siteId={siteId} />
    </div>
  )
}
