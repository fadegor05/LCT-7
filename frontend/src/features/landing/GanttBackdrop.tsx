import { useEffect, useState } from 'react'
import { MONTHS, STAGES, dayLabel, stageAt } from './gantt'
import styles from './GanttBackdrop.module.css'

/** Линия «сегодня» проходит от 30 % до 90 % года за столько, затем начинает заново. */
const CYCLE_MS = 48_000
const FROM = 0.3
const TO = 0.9
const pct = (v: number) => `${(v * 100).toFixed(3)}%`
const rowTop = (i: number) => 17 + i * 5.8

/**
 * Фон лендинга: график работ, где факт по снимкам догоняет план, а отстающие этапы краснеют.
 * Слои лежат на разной глубине (`data-depth`) — их смещает `useCursorParallax` страницы.
 */
export function GanttBackdrop() {
  const [k, setK] = useState(0.62)

  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return undefined
    const t0 = performance.now() - CYCLE_MS * 0.55
    const timer = window.setInterval(() => {
      const phase = ((performance.now() - t0) % CYCLE_MS) / CYCLE_MS
      setK(FROM + (TO - FROM) * phase)
    }, 120)
    return () => window.clearInterval(timer)
  }, [])

  const states = STAGES.map((s) => stageAt(s, k))

  return (
    <div className={styles.root} aria-hidden="true">
      <div className={styles.layer} data-depth="0.35">
        <div className={styles.months}>
          {MONTHS.map((m, i) => (
            <span key={m} className={styles.month} style={{ left: pct(i / 12) }}>
              {m}
            </span>
          ))}
        </div>
        {Array.from({ length: 48 }, (_, i) => (
          <span
            key={i}
            className={i % 4 === 0 ? styles.gridMonth : styles.gridWeek}
            style={{ left: pct(i / 48) }}
          />
        ))}
      </div>

      <div className={styles.layer} data-depth="0.7">
        {STAGES.map((s, i) => (
          <div key={s.name} className={styles.row} style={{ top: `${rowTop(i)}%` }}>
            <span
              className={styles.plan}
              style={{ left: pct(s.start), width: pct(s.end - s.start) }}
            />
            <span className={styles.label} style={{ left: pct(s.start) }}>
              {s.name}
            </span>
          </div>
        ))}
      </div>

      <div className={styles.layer} data-depth="1">
        {STAGES.map((s, i) => {
          const st = states[i]!
          return (
            <div key={s.name} className={styles.row} style={{ top: `${rowTop(i)}%` }}>
              <span
                className={`${styles.fact} ${styles[st.state]}`}
                style={{ left: pct(s.start), width: pct(st.fact - s.start) }}
              />
            </div>
          )
        })}
        <div className={styles.today} style={{ left: pct(k) }}>
          <span className={styles.todayLabel}>сегодня · {dayLabel(k)}</span>
        </div>
      </div>

      <div className={styles.layer} data-depth="1.6">
        {STAGES.map((s, i) => {
          const { state, fact } = states[i]!
          if (state !== 'behind' && state !== 'ahead') return null
          const ahead = state === 'ahead'
          const days = Math.round((ahead ? (s.lead ?? 0) : s.lag) * 365)
          return (
            <span
              key={s.name}
              className={`${styles.chip} ${ahead ? styles.chipAhead : ''}`}
              style={{ left: pct(fact), top: `calc(${rowTop(i)}% - 30px)` }}
            >
              {s.name} · {ahead ? '+' : '−'}
              {days} дн.
            </span>
          )
        })}
      </div>
    </div>
  )
}
