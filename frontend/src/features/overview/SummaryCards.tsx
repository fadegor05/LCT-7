import { Link } from 'react-router'
import { useSummary } from '@/api/deviations'
import { useObservations, useUndatedPhotos } from '@/api/frames'
import type { SiteSummary } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { formatDate } from '@/lib/format'
import { levelLabels } from '@/lib/labels'
import { verdictText } from '@/features/sites/verdict'
import styles from './Overview.module.css'

const EXPLANATION: Record<SiteSummary['verdict'], string> = {
  behind:
    'Худший интервал по этапам с отставанием. Отставание измерено по датам снимков: точность не выше частоты съёмки.',
  no_deviations: 'Этапы с данными идут по графику.',
  insufficient_data:
    'Нет оценённых этапов: график не загружен, снимков нет или наблюдаемость недостаточна для вывода.',
}

function VerdictCard({ summary }: { summary: SiteSummary }) {
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
      <p className="sm">{EXPLANATION[summary.verdict]}</p>
    </Card>
  )
}

function DataStateCard({ siteId }: { siteId: string }) {
  const observations = useObservations(siteId).data ?? []
  const undated = useUndatedPhotos(siteId).data?.length ?? 0
  const last = observations.at(-1)
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
      {summary.data && <VerdictCard summary={summary.data} />}
      <DataStateCard siteId={siteId} />
    </div>
  )
}
