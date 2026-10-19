import { Link } from 'react-router'
import { annotatedImageUrl } from '@/api/frames'
import type { DeviationDetail } from '@/api/schemas'
import { Callout } from '@/components/ui/Callout'
import { ConfidenceMeter } from '@/components/ui/ConfidenceMeter'
import { FrameView } from '@/components/ui/FrameView'
import { Pill } from '@/components/ui/Pill'
import { formatDate } from '@/lib/format'
import { deviationTypeLabels } from '@/lib/labels'
import styles from './Deviation.module.css'

interface DeviationBodyProps {
  siteId: string
  deviation: DeviationDetail
  stageName: string | null
  /** Отстающий этап, чья техника ещё на площадке: возможная причина отклонения. */
  causeName?: string | null
}

/** Карточка отклонения (UC-5): ожидание против наблюдения, доказательства, правило, границы вывода. */
export function DeviationBody({ siteId, deviation: d, stageName, causeName }: DeviationBodyProps) {
  const siteUrl = `/sites/${siteId}`
  const period = [d.period_start, d.period_end].map(formatDate).join(' — ')

  return (
    <div className={styles.body}>
      <div className={styles.tags}>
        <Pill tone={d.is_hypothesis ? 'caution' : 'behind'} icon="alert">
          {deviationTypeLabels[d.type]}
        </Pill>
        {d.is_hypothesis && <Pill tone="cautionDashed">Гипотеза</Pill>}
      </div>
      <p>
        {d.stage_id ? (
          <>
            Этап <Link to={siteUrl}>{stageName ?? 'из графика'}</Link>
          </>
        ) : (
          'Все этапы'
        )}
        {' · '}
        <span className="data">{period}</span>
      </p>

      <div className={styles.compare}>
        <section className={styles.col}>
          <h4 className={styles.colTitle}>Ожидалось по правилу</h4>
          <p>{d.expected}</p>
        </section>
        <section className={styles.col}>
          <h4 className={styles.colTitle}>Наблюдается</h4>
          <p>{d.observed}</p>
        </section>
      </div>

      {causeName && (
        <Callout tone="caution" title="Возможная причина">
          Этап «{causeName}» ещё не закончен: его техника всё ещё на площадке
          {stageName ? `, поэтому «${stageName}» мог не начаться` : ''}.{' '}
          <Link to={siteUrl}>К этапам на обзоре</Link>
        </Callout>
      )}

      {d.evidence.length > 0 && (
        <section>
          <h4 className={styles.colTitle}>Снимки-доказательства</h4>
          <div className={styles.frames}>
            {d.evidence.map((e, i) => (
              <FrameView
                key={`${e.photo_id}-${e.detection_id ?? i}`}
                imageUrl={annotatedImageUrl(siteId, e.photo_id)}
                alt={`Снимок-доказательство ${i + 1}`}
                caption={e.caption ? <span className="sm">{e.caption}</span> : undefined}
              />
            ))}
          </div>
        </section>
      )}

      <dl className={styles.meta}>
        <div>
          <dt>Сработавшее правило</dt>
          <dd>
            {d.rule_id ? (
              <Link to={`${siteUrl}/methodology`}>Методика этапа</Link>
            ) : (
              <span className="muted">Правило сервиса</span>
            )}
          </dd>
        </div>
        <div>
          <dt>Уверенность</dt>
          <dd>
            <ConfidenceMeter level={d.confidence} />
          </dd>
        </div>
      </dl>

      <Callout title="Чего это не доказывает">{d.limits_text}</Callout>
    </div>
  )
}
