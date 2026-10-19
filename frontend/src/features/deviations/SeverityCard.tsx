import { Link } from 'react-router'
import { useStageStatuses, useSummary } from '@/api/deviations'
import { useSchedule } from '@/api/schedule'
import type { DeviationDetail } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { formatDate, formatDelay } from '@/lib/format'
import { SeverityBadge } from './SeverityBadge'
import styles from './Deviation.module.css'

/** Сколько дней длится отклонение: от начала серии до последнего наблюдения. */
function lasting(d: Pick<DeviationDetail, 'period_start' | 'period_end'>): number {
  return Math.round((Date.parse(d.period_end) - Date.parse(d.period_start)) / 86_400_000)
}

/** Боковая панель: важность с объяснением и ссылки «Проверить». */
export function SeverityCard({
  siteId,
  deviation: d,
}: {
  siteId: string
  deviation: DeviationDetail
}) {
  const base = `/sites/${siteId}`
  const statuses = useStageStatuses(siteId, d.type === 'behind_schedule')
  // Отставание — интервалом этапа, как в итоге («7 дн.», «14–74 дн.»); остальные — сколько длится
  const stage = statuses.data?.find((s) => s.stage_id === d.stage_id)
  const delay =
    d.type === 'behind_schedule' && stage
      ? formatDelay(
          stage.delay_min ?? stage.delay_days,
          stage.delay_open ? null : (stage.delay_max ?? stage.delay_days),
        )
      : null
  const big = delay ?? (lasting(d) > 0 ? `до ${lasting(d)} дн.` : null)
  // Смысл числа (clean-mvp): нижняя граница на опорную дату, измерение, а не прогноз
  const asOf = useSummary(siteId).data?.as_of
  const planned = useSchedule(siteId).data?.stages.find((s) => s.id === d.stage_id)
  const dm = (v: string | null | undefined) => (v ? `${v.slice(8, 10)}.${v.slice(5, 7)}` : '—')
  const meaning =
    delay && asOf && planned
      ? stage?.status === 'not_started'
        ? `Нижняя граница: этап не начат к ${dm(asOf)}, плановое начало ${dm(planned.planned_start)}.`
        : `Нижняя граница: этап не закончен к ${dm(asOf)}, плановый конец ${dm(planned.planned_end)}.`
      : null
  return (
    <>
      <Card as="aside" aria-label="Важность">
        <p className="lab muted">Важность</p>
        <div>
          <SeverityBadge severity={d.severity} />
        </div>
        {/* Крупно, как в clean-mvp: отставание «7 дн.» или длительность «до 2 дн.» */}
        {big && <p className={styles.lasting}>{big}</p>}
        {meaning && (
          <p className="sm">{meaning} Измерение, не прогноз; точность не выше частоты съёмки.</p>
        )}
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
