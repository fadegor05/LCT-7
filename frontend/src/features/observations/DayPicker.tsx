import type { Observation } from '@/api/schemas'
import { formatShortDate } from '@/lib/format'
import { pluralPhotos } from '@/lib/labels'
import styles from './Observations.module.css'

interface DayPickerProps {
  days: readonly Observation[]
  /** null — «Все дни». */
  value: string | null
  onChange: (date: string | null) => void
  undated: number
}

export function DayPicker({ days, value, onChange, undated }: DayPickerProps) {
  const total = days.reduce((sum, d) => sum + d.photo_count, 0)
  return (
    <div className={styles.days} role="group" aria-label="Дни наблюдений">
      <button
        type="button"
        className={styles.day}
        aria-pressed={value === null}
        onClick={() => onChange(null)}
      >
        <span className="lab">Все дни</span>
        <span className="sm muted">{pluralPhotos(total)}</span>
      </button>
      {days.map((d) => (
        <button
          key={d.observed_on}
          type="button"
          className={styles.day}
          aria-pressed={value === d.observed_on}
          onClick={() => onChange(d.observed_on)}
        >
          <span className="lab data">{formatShortDate(d.observed_on)}</span>
          <span className="sm muted">{pluralPhotos(d.photo_count)}</span>
        </button>
      ))}
      {undated > 0 && (
        <a href="#no-date" className={`${styles.day} ${styles.dayWarn}`}>
          <span className="lab">Без даты</span>
          <span className="sm muted">{pluralPhotos(undated)} · ниже</span>
        </a>
      )}
    </div>
  )
}
