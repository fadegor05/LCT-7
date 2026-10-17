import { useEffect, useRef, useState } from 'react'
import { MONTHS, STAGES, dayLabel, stageAt } from './gantt'
import styles from './GanttBackdrop.module.css'

/** Линия «сегодня» проходит от 30 % до 90 % года за столько, затем начинает заново. */
const CYCLE_MS = 48_000
const FROM = 0.3
const TO = 0.9
/** Насколько сдвигается слой глубины 1 при курсоре у края экрана, px. */
const PARALLAX_X = 18
const PARALLAX_Y = 12

const pct = (v: number) => `${(v * 100).toFixed(3)}%`
const rowTop = (i: number) => 17 + i * 5.8

/**
 * Фон лендинга: график работ, где факт по снимкам догоняет план, а отстающие этапы краснеют.
 * Слои лежат на разной глубине и смещаются за курсором (только мышь, без «уменьшить движение»).
 */
export function GanttBackdrop() {
  const [k, setK] = useState(0.62)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return undefined
    const t0 = performance.now() - CYCLE_MS * 0.55
    const timer = window.setInterval(() => {
      const phase = ((performance.now() - t0) % CYCLE_MS) / CYCLE_MS
      setK(FROM + (TO - FROM) * phase)
    }, 120)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const media = (q: string) => window.matchMedia?.(q).matches ?? false
    if (!media('(pointer: fine)') || media('(prefers-reduced-motion: reduce)')) return undefined
    const layers = [...(root.current?.querySelectorAll<HTMLElement>('[data-depth]') ?? [])]
    const target = { x: 0, y: 0 }
    const current = { x: 0, y: 0 }
    let raf = 0
    const tick = () => {
      current.x += (target.x - current.x) * 0.08
      current.y += (target.y - current.y) * 0.08
      for (const layer of layers) {
        const depth = Number(layer.dataset.depth)
        const x = (-current.x * depth * PARALLAX_X).toFixed(2)
        const y = (-current.y * depth * PARALLAX_Y).toFixed(2)
        layer.style.transform = `translate3d(${x}px, ${y}px, 0)`
      }
      const settled = Math.abs(target.x - current.x) + Math.abs(target.y - current.y) < 0.002
      raf = settled ? 0 : requestAnimationFrame(tick)
    }
    const onMove = (e: PointerEvent) => {
      target.x = (e.clientX / window.innerWidth) * 2 - 1
      target.y = (e.clientY / window.innerHeight) * 2 - 1
      if (!raf) raf = requestAnimationFrame(tick)
    }
    window.addEventListener('pointermove', onMove)
    return () => {
      window.removeEventListener('pointermove', onMove)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [])

  const states = STAGES.map((s) => stageAt(s, k))

  return (
    <div ref={root} className={styles.root} aria-hidden="true">
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
        {STAGES.map((s, i) =>
          states[i]!.state === 'behind' ? (
            <span
              key={s.name}
              className={styles.chip}
              style={{ left: pct(states[i]!.fact), top: `calc(${rowTop(i)}% - 30px)` }}
            >
              {s.name} · −{Math.round(s.lag * 365)} дн.
            </span>
          ) : null,
        )}
      </div>
    </div>
  )
}
