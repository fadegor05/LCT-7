import type { Level } from '@/api/schemas'
import { levelLabels } from '@/lib/labels'
import styles from './ConfidenceMeter.module.css'

const SEGMENTS: Record<Level, number> = { high: 3, medium: 2, low: 1 }

/** Уверенность — три уровня, не число (architecture §7.3). */
export function ConfidenceMeter({ level, hideLabel }: { level: Level; hideLabel?: boolean }) {
  const label = levelLabels[level]
  return (
    <span className={styles.meter} role="img" aria-label={`Уверенность: ${label.toLowerCase()}`}>
      <span className={styles.bar} aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={i < SEGMENTS[level] ? `${styles.seg} ${styles.on}` : styles.seg}
          />
        ))}
      </span>
      {!hideLabel && <span aria-hidden="true">{label}</span>}
    </span>
  )
}
