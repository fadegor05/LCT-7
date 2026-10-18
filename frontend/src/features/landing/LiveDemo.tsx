import { useRef, useState, type KeyboardEvent } from 'react'
import { Pill } from '@/components/ui/Pill'
import { DEMO_FINDINGS, type DemoFinding, type DemoFrame } from './demo/p03'
import { Shot } from './Shot'
import styles from './LiveDemo.module.css'

const ICON = { behind: 'clock', outline: 'circle', caution: 'alert' } as const

function Frame({ frame }: { frame: DemoFrame }) {
  return (
    <figure className={styles.frame}>
      <Shot src={frame.src} alt={frame.alt} boxes={frame.boxes} />
      <figcaption>
        Снимок от {frame.date}. Сплошная рамка: техника распознана уверенно, вывод строится по ней.
        Пунктир: распознавание неуверенное, в вывод не идёт.
      </figcaption>
    </figure>
  )
}

function Detail({ finding }: { finding: DemoFinding }) {
  return (
    <article className={styles.detail} aria-label={`Карточка: ${finding.title}`}>
      <header className={styles.detailHead}>
        <h3>{finding.title}</h3>
        <div className={styles.badges}>
          <Pill tone={finding.severity === 'Критично' ? 'behind' : 'caution'} icon="alert">
            {finding.severity}
          </Pill>
          {finding.hypothesis ? <Pill tone="cautionDashed">Гипотеза</Pill> : null}
        </div>
      </header>

      <dl className={styles.facts}>
        <div>
          <dt>Ожидалось по правилу</dt>
          <dd>{finding.expected}</dd>
        </div>
        <div>
          <dt>Наблюдается</dt>
          <dd>{finding.observed}</dd>
        </div>
        <div>
          <dt>Уверенность: {finding.confidence}</dt>
          <dd>{finding.confidenceReason}</dd>
        </div>
        <div>
          <dt>Правило</dt>
          <dd>
            {finding.rule}
            <span className={styles.source}>{finding.ruleSource}</span>
          </dd>
        </div>
      </dl>

      <div className={styles.frames}>
        {finding.frames.map((f) => (
          <Frame key={f.src} frame={f} />
        ))}
      </div>

      <p className={styles.limits}>
        <b>Чего это не доказывает.</b> {finding.cannotClaim}
      </p>
    </article>
  )
}

/** Живой пример: три вывода по площадке p03, у каждого кадр, правило, уверенность и границы. */
export function LiveDemo() {
  const [selected, setSelected] = useState(DEMO_FINDINGS[0]!.id)
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const finding = DEMO_FINDINGS.find((f) => f.id === selected) ?? DEMO_FINDINGS[0]!

  const move = (event: KeyboardEvent, index: number) => {
    const step = event.key === 'ArrowDown' ? 1 : event.key === 'ArrowUp' ? -1 : 0
    if (!step) return
    event.preventDefault()
    const next = (index + step + DEMO_FINDINGS.length) % DEMO_FINDINGS.length
    refs.current[next]?.focus()
    setSelected(DEMO_FINDINGS[next]!.id)
  }

  return (
    <div className={styles.demo}>
      <div className={styles.grid}>
        <ul className={styles.list} aria-label="Выводы по площадке">
          {DEMO_FINDINGS.map((f, i) => (
            <li key={f.id}>
              <button
                type="button"
                ref={(node) => {
                  refs.current[i] = node
                }}
                className={styles.row}
                aria-pressed={f.id === selected}
                onClick={() => setSelected(f.id)}
                onKeyDown={(e) => move(e, i)}
              >
                <span className={styles.rowTitle}>{f.title}</span>
                <span className={styles.rowMeta}>
                  <span>План: {f.plan}</span>
                  <span>Факт: {f.fact}</span>
                </span>
                <Pill tone={f.tone} icon={ICON[f.tone]}>
                  {f.status}
                </Pill>
              </button>
            </li>
          ))}
        </ul>
        <Detail finding={finding} />
      </div>
    </div>
  )
}
