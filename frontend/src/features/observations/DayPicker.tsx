import type { ObservationDay } from '@/api/schemas'
import { formatShortDate } from '@/lib/format'
import { pluralFrames } from '@/lib/labels'
import styles from './Observations.module.css'

interface DayPickerProps {
  days: readonly ObservationDay[]
  /** null — «Все дни». */
  value: string | null
  onChange: (date: string | null) => void
  withoutTime: number
}

export function DayPicker({ days, value, onChange, withoutTime }: DayPickerProps) {
  const total = days.reduce((sum, d) => sum + d.frames_total, 0)
  return (
    <div className={styles.days} role="group" aria-label="Дни наблюдений">
      <button
        type="button"
        className={styles.day}
        aria-pressed={value === null}
        onClick={() => onChange(null)}
      >
        <span className="lab">Все дни</span>
        <span className="sm muted">{pluralFrames(total)}</span>
      </button>
      {days.map((d) => (
        <button
          key={d.obs_date}
          type="button"
          className={styles.day}
          aria-pressed={value === d.obs_date}
          onClick={() => onChange(d.obs_date)}
        >
          <span className="lab data">{formatShortDate(d.obs_date)}</span>
          <span className="sm muted">{pluralFrames(d.frames_total)}</span>
        </button>
      ))}
      {withoutTime > 0 && (
        <a href="#no-time" className={`${styles.day} ${styles.dayWarn}`}>
          <span className="lab">Без даты</span>
          <span className="sm muted">{pluralFrames(withoutTime)} · ниже</span>
        </a>
      )}
    </div>
  )
}
