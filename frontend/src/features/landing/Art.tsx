import { Pill } from '@/components/ui/Pill'
import { PLAN_ROWS, SNAPSHOTS, dayOf } from './demo/timeline'
import styles from './Art.module.css'

const SHORT: Record<string, string> = { piles: 'Сваи', sheet: 'Шпунт' }

const ROWS = [
  ...PLAN_ROWS.map((r) => ({ name: SHORT[r.id] ?? r.title, start: r.start, end: r.end })),
  { name: 'Котлован', start: '2023-08-15', end: '2023-10-31' },
  { name: 'Фундаментная плита', start: '2023-11-01', end: '2023-12-31' },
]

const FROM = dayOf('2023-05-15')
const SPAN = dayOf('2023-12-31') - FROM
const pos = (iso: string) => (dayOf(iso) - FROM) / SPAN
const fmt = (iso: string) => iso.split('-').reverse().slice(0, 2).join('.')

/** Шаг 1: как выглядит график после загрузки, этапы с датами. */
export function ScheduleArt() {
  return (
    <div
      className={styles.card}
      role="img"
      aria-label="Календарный график после загрузки: четыре этапа с датами"
    >
      <div className={styles.file} aria-hidden="true">
        <b>график_p03.xlsx</b>
        <span>4 этапа</span>
      </div>
      <ul className={styles.sched} aria-hidden="true">
        {ROWS.map((r) => (
          <li key={r.name}>
            <span className={styles.name}>{r.name}</span>
            <span className={styles.dates}>
              {fmt(r.start)} - {fmt(r.end)}
            </span>
            <span className={styles.track}>
              <i
                style={{
                  left: `${pos(r.start) * 100}%`,
                  width: `${(pos(r.end) - pos(r.start)) * 100}%`,
                }}
              />
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Шаг 2: снимки площадки со штампами дат, как они лежат в ленте. */
export function PhotosArt() {
  return (
    <div
      className={`${styles.card} ${styles.photos}`}
      role="img"
      aria-label="Три снимка площадки с датами съёмки"
    >
      {SNAPSHOTS.map((s) => (
        <figure key={s.iso} aria-hidden="true">
          <img src={s.src} alt="" loading="lazy" width="960" />
          <figcaption>{s.short}.2023</figcaption>
        </figure>
      ))}
    </div>
  )
}

/** Шаг 3: итог по объекту и статусы этапов. */
export function StatusArt() {
  return (
    <div
      className={styles.card}
      role="img"
      aria-label="Итог по объекту: отставание от 14 до 43 дней, статусы двух этапов"
    >
      <div className={styles.verdict} aria-hidden="true">
        <small>Итог по объекту</small>
        <strong>Отставание 14–43 дня</strong>
      </div>
      <ul className={styles.stat} aria-hidden="true">
        <li>
          <span>Устройство свай</span>
          <Pill tone="behind" icon="clock" size="sm">
            Отставание
          </Pill>
        </li>
        <li>
          <span>Ограждение котлована: шпунт</span>
          <Pill tone="outline" icon="circle" size="sm">
            Не начат
          </Pill>
        </li>
      </ul>
    </div>
  )
}
