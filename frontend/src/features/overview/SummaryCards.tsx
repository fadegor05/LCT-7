import { Link } from 'react-router'
import type { Site, SiteSummary } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { formatShortDateTime } from '@/lib/format'
import { levelLabels } from '@/lib/labels'
import { verdictText } from '@/features/sites/verdict'
import styles from './Overview.module.css'

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
      {summary.explanation && <p className="sm">{summary.explanation}</p>}
    </Card>
  )
}

function DataStateCard({ site, summary }: { site: Site; summary: SiteSummary }) {
  return (
    <Card aria-labelledby="data-state-title">
      <p id="data-state-title" className="lab muted">
        Состояние данных
      </p>
      <p className="lab">Наблюдаемость {levelLabels[summary.observability].toLowerCase()}</p>
      <dl className={styles.kv}>
        <div>
          <dt>Камеры</dt>
          <dd>
            {summary.cameras_reporting} из {summary.cameras_total} присылают кадры
          </dd>
        </div>
        <div>
          <dt>Последний кадр</dt>
          <dd className="data">{formatShortDateTime(summary.last_frame_at)}</dd>
        </div>
        <div>
          <dt>Всего кадров</dt>
          <dd className="data">{summary.frames_total}</dd>
        </div>
        <div>
          <dt>Без даты или времени</dt>
          <dd className="data">{summary.frames_without_time}</dd>
        </div>
      </dl>
      <Link to={`/sites/${site.id}/cameras`} className="sm">
        Камеры и кадры →
      </Link>
    </Card>
  )
}

export function SummaryCards({ site }: { site: Site }) {
  if (!site.summary) return null
  return (
    <div className={styles.top}>
      <VerdictCard summary={site.summary} />
      <DataStateCard site={site} summary={site.summary} />
    </div>
  )
}
