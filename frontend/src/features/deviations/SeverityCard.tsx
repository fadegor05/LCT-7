import { Link } from 'react-router'
import type { DeviationDetail } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { formatDate } from '@/lib/format'
import { SeverityBadge } from './SeverityBadge'
import styles from './Deviation.module.css'

/** Боковая панель: важность с объяснением и ссылки «Проверить». */
export function SeverityCard({
  siteId,
  deviation: d,
}: {
  siteId: string
  deviation: DeviationDetail
}) {
  const base = `/sites/${siteId}`
  return (
    <>
      <Card as="aside" aria-label="Важность">
        <p className="lab muted">Важность</p>
        <div>
          <SeverityBadge severity={d.severity} />
        </div>
        <p className="sm">
          {d.is_hypothesis
            ? 'Гипотеза: есть косвенный признак, но нет доказательства. Проверьте снимки.'
            : 'Вывод верен, пока верны график, методика и снимки.'}
        </p>
        <details className="sm">
          <summary>Как считается важность</summary>
          Важность = тип отклонения + отставание в днях + уверенность + наблюдаемость. Потолок
          опускает только низкая уверенность или низкая наблюдаемость; гипотезы никогда не бывают
          критичными.
        </details>
      </Card>
      <Card as="aside" aria-label="Проверить">
        <p className="lab muted">Проверить</p>
        <div className={styles.links}>
          <Link to={`${base}/observations?date=${d.period_end}`}>
            Наблюдения за {formatDate(d.period_end)}
          </Link>
          {d.stage_id && <Link to={`${base}/methodology`}>Методика этапа</Link>}
        </div>
      </Card>
    </>
  )
}
