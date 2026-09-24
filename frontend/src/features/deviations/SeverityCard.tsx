import { Link } from 'react-router'
import type { DeviationDetail } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { formatDelay, formatShortDate } from '@/lib/format'
import { SeverityBadge } from './SeverityBadge'
import styles from './Deviation.module.css'

/** Боковая панель: важность с объяснением и ссылки «Проверить». */
export function SeverityCard({ deviation: d }: { deviation: DeviationDetail }) {
  const base = `/sites/${d.site_id}`
  const delay = formatDelay(d.delay_days_min, d.delay_days_max)
  return (
    <>
      <Card as="aside" aria-label="Важность">
        <p className="lab muted">Важность</p>
        <div>
          <SeverityBadge severity={d.severity} />
        </div>
        {delay && <p className={styles.big}>{delay}</p>}
        <p className="sm">{d.severity_reason}</p>
        {!d.is_hypothesis && (
          <p className="sm muted">
            Решения по этому отклонению нет: вывод верен, пока верны график, методика и кадры.
          </p>
        )}
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
          {d.observation_date && (
            <Link to={`${base}/observations?date=${d.observation_date}`}>
              Наблюдения за {formatShortDate(d.observation_date)}
            </Link>
          )}
          {d.stage_id && <Link to={`${base}/methodology`}>Методика этапа</Link>}
          <Link to={`${base}/cameras`}>
            {d.camera_name ? `Зона камеры ${d.camera_name}` : 'Камеры'}
          </Link>
        </div>
      </Card>
    </>
  )
}
