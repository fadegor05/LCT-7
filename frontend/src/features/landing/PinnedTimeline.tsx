import { useRef } from 'react'
import { Pill } from '@/components/ui/Pill'
import {
  AXIS_DAYS,
  MONTH_TICKS,
  PLAN_ROWS,
  SNAPSHOTS,
  STEPS,
  axisPos,
  timelineState,
} from './demo/timeline'
import { Shot } from './Shot'
import { useMediaQuery } from './useMediaQuery'
import { prefersReducedMotion, useScrollProgress } from './useScroll'
import styles from './PinnedTimeline.module.css'

const pct = (v: number) => `${(v * 100).toFixed(3)}%`

/** Подпись даты линии среза: доля оси переводится в день 2023 года. */
function cursorLabel(cursor: number): string {
  const date = new Date(Date.UTC(2023, 4, 1) + Math.round(cursor * AXIS_DAYS) * 86_400_000)
  const d = String(date.getUTCDate()).padStart(2, '0')
  const m = String(date.getUTCMonth() + 1).padStart(2, '0')
  return `${d}.${m}.2023`
}

/** Без закрепления (телефон, «меньше движения»): те же шаги подряд, снимок под каждым. */
function StaticStory() {
  return (
    <ol className={styles.story}>
      {STEPS.map((s, i) => {
        const snap = i >= 1 && i <= 3 ? SNAPSHOTS[i - 1] : undefined
        return (
          <li key={s.title}>
            <span className={styles.kicker}>{s.kicker}</span>
            <h3>{s.title}</h3>
            <p>{s.text}</p>
            {snap ? <Shot src={snap.src} alt={snap.alt} boxes={snap.boxes} /> : null}
          </li>
        )
      })}
    </ol>
  )
}

/**
 * Фирменный момент страницы: пока читатель листает, линия среза идёт по оси времени, на датах
 * появляются настоящие снимки площадки p03, а у этапа свай вырастает красный отрезок отставания.
 */
export function PinnedTimeline() {
  const track = useRef<HTMLElement>(null)
  const wide = useMediaQuery('(width >= 1000px)')
  const pinned = wide && !prefersReducedMotion()
  const progress = useScrollProgress(track, pinned)
  const state = timelineState(progress)
  const step = STEPS[state.step]!
  const piles = PLAN_ROWS[0]!
  const sheet = PLAN_ROWS[1]!

  if (!pinned) {
    return (
      <div className={styles.flat}>
        <StaticStory />
      </div>
    )
  }

  return (
    <section ref={track} className={styles.track} aria-label="Как отставание видно во времени">
      <div className={styles.stage}>
        <div className={styles.caption} aria-live="polite">
          <div className={styles.when}>
            <span className={styles.stepNo}>
              Шаг {state.step + 1} из {STEPS.length}
            </span>
            <b key={`d${state.step}`} className={styles.date}>
              {step.kicker}
            </b>
            <span className={styles.bars}>
              {STEPS.map((s, i) => (
                <i key={s.kicker} className={i <= state.step ? styles.barOn : undefined} />
              ))}
            </span>
          </div>
          <div className={styles.say}>
            <h3 key={state.step} className={styles.stepTitle}>
              {step.title}
            </h3>
            <p key={`t${state.step}`} className={styles.stepText}>
              {step.text}
            </p>
          </div>
        </div>

        <div className={styles.chart} aria-hidden="true">
          {MONTH_TICKS.map((m) => (
            <span key={m.iso} className={styles.month} style={{ left: pct(axisPos(m.iso)) }}>
              <i>{m.label}</i>
            </span>
          ))}

          {[piles, sheet].map((row, i) => (
            <div key={row.id} className={styles.row} style={{ top: `${44 + i * 74}px` }}>
              <span
                className={styles.plan}
                style={{
                  left: pct(axisPos(row.start)),
                  width: pct(axisPos(row.end) - axisPos(row.start)),
                }}
              />
              <span className={styles.rowTitle} style={{ left: pct(axisPos(row.start)) }}>
                {row.title}
              </span>
            </div>
          ))}

          <span
            className={styles.lag}
            style={{
              left: pct(axisPos('2023-07-31')),
              width: pct((axisPos('2023-08-14') - axisPos('2023-07-31')) * state.lag),
              top: 44,
            }}
          />
          {state.piles ? (
            <span
              className={`${styles.badge} ${styles.badgeIn}`}
              style={{ left: pct(axisPos('2023-08-14') + 0.012), top: 36 }}
            >
              <Pill tone="behind" icon="clock">
                Отставание 14–43 дня
              </Pill>
            </span>
          ) : null}
          {state.sheet ? (
            <span
              className={`${styles.badge} ${styles.badgeIn}`}
              style={{ left: pct(axisPos('2023-08-31') + 0.012), top: 110 }}
            >
              <Pill tone="outline" icon="circle">
                Не начат
              </Pill>
            </span>
          ) : null}

          {SNAPSHOTS.map((s, i) => (
            <span
              key={s.iso}
              className={`${styles.tick} ${state.shown[i] ? styles.tickOn : ''}`}
              style={{ left: pct(axisPos(s.iso)) }}
            >
              <i>{s.short}</i>
            </span>
          ))}

          {state.cursor !== null ? (
            <span className={styles.cursor} style={{ left: pct(state.cursor) }}>
              <i>срез {cursorLabel(state.cursor)}</i>
            </span>
          ) : null}
        </div>

        <ul className={styles.strip}>
          {SNAPSHOTS.map((s, i) => (
            <li key={s.iso} className={state.shown[i] ? styles.cardOn : styles.card}>
              <Shot src={s.src} alt={s.alt} boxes={s.boxes} />
              <span className={styles.cardCap}>
                <b>{s.short}.2023</b> {s.caption}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
