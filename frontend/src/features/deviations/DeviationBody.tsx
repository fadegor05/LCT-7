import { Link } from 'react-router'
import type { DeviationDetail } from '@/api/schemas'
import { Callout } from '@/components/ui/Callout'
import { ConfidenceMeter } from '@/components/ui/ConfidenceMeter'
import { DateSourceBadge } from '@/components/ui/DateSourceBadge'
import { FrameView } from '@/components/ui/FrameView'
import { Pill } from '@/components/ui/Pill'
import { useEquipmentName } from '@/features/observations/useEquipmentName'
import { formatDate } from '@/lib/format'
import { deviationTypeLabels, ruleKindLabels } from '@/lib/labels'
import styles from './Deviation.module.css'

/** Карточка отклонения (UC-5): ожидание против наблюдения, доказательства, правило, границы вывода. */
export function DeviationBody({ deviation: d }: { deviation: DeviationDetail }) {
  const name = useEquipmentName()
  const siteUrl = `/sites/${d.site_id}`
  const period = [d.period_start, d.period_end].filter(Boolean).map(formatDate).join(' — ')

  return (
    <div className={styles.body}>
      <div className={styles.tags}>
        <Pill tone={d.is_hypothesis ? 'caution' : 'behind'} icon="alert">
          {deviationTypeLabels[d.type]}
        </Pill>
        {d.is_hypothesis && <Pill tone="cautionDashed">Гипотеза</Pill>}
      </div>
      <p>
        {d.stage_id && d.stage_name ? (
          <>
            Этап <Link to={siteUrl}>{d.stage_name}</Link>
          </>
        ) : (
          'Все этапы'
        )}
        {period && (
          <>
            {' · '}
            <span className="data">{period}</span>
          </>
        )}
      </p>

      <div className={styles.compare}>
        <section className={styles.col}>
          <h4 className={styles.colTitle}>Ожидалось по правилу</h4>
          <p>{d.expected_text}</p>
        </section>
        <section className={styles.col}>
          <h4 className={styles.colTitle}>Наблюдается</h4>
          <p>{d.observed_text}</p>
        </section>
      </div>

      {d.cause_text && (
        <Callout tone="caution" title="Возможная причина">
          {d.cause_text} <Link to={siteUrl}>К этапам на обзоре</Link>
        </Callout>
      )}

      {d.evidence.length > 0 && (
        <section>
          <h4 className={styles.colTitle}>Снимки-доказательства</h4>
          <div className={styles.frames}>
            {d.evidence.map((e, i) => (
              <FrameView
                key={`${e.frame.id}-${e.role}-${i}`}
                imageUrl={e.frame.image_url}
                detections={e.frame.detections}
                classLabel={name}
                zone={e.role === 'zone' ? d.zone_polygon : null}
                alt={e.caption ?? 'Снимок-доказательство'}
                caption={
                  e.role === 'zone' ? (
                    <span className="muted">{e.caption}</span>
                  ) : (
                    <>
                      <span className="data">{formatDate(e.frame.captured_at)}</span>
                      {e.frame.date_source && <DateSourceBadge source={e.frame.date_source} />}
                      {e.caption && <span className="muted">{e.caption}</span>}
                    </>
                  )
                }
              />
            ))}
          </div>
        </section>
      )}

      <dl className={styles.meta}>
        <div>
          <dt>Сработавшее правило</dt>
          <dd>
            {d.rule ? (
              <>
                <span>{d.rule.name}</span>
                <span className="sm muted">
                  {ruleKindLabels[d.rule.rule_kind]}
                  {d.rule.source_ref && ` · ${d.rule.source_ref}`}
                </span>
              </>
            ) : (
              <span className="muted">Правило сервиса</span>
            )}
          </dd>
        </div>
        <div>
          <dt>Уверенность</dt>
          <dd>
            <ConfidenceMeter level={d.confidence} />
            <span className="sm">{d.confidence_reason}</span>
          </dd>
        </div>
      </dl>

      <Callout title="Чего это не доказывает">{d.limits_text}</Callout>
    </div>
  )
}
