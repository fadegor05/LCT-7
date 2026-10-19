import { useLayoutEffect, useRef } from 'react'
import type { Observation } from '@/api/schemas'
import { formatDate } from '@/lib/format'
import { pluralPhotos } from '@/lib/labels'
import styles from './Observations.module.css'

interface DayPickerProps {
  days: readonly Observation[]
  /** null — «Все дни». */
  value: string | null
  onChange: (date: string | null) => void
  /** День под указателем: его данные грузятся до клика. */
  onPreview?: (date: string) => void
  undated: number
}

export function DayPicker({ days, value, onChange, onPreview, undated }: DayPickerProps) {
  const total = days.reduce((sum, d) => sum + d.photo_count, 0)
  // Дни слева направо по времени, как ленты кадров
  const ordered = [...days].sort((a, b) => a.observed_on.localeCompare(b.observed_on))
  const row = useRef<HTMLDivElement>(null)
  // Выбранный день виден в строке: по умолчанию это последний, у правого края
  useLayoutEffect(() => {
    const pressed = row.current?.querySelector<HTMLElement>('[aria-pressed="true"]')
    pressed?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
  }, [value, days])
  return (
    <div ref={row} className={styles.days} role="group" aria-label="Дни наблюдений">
      <button
        type="button"
        className={styles.day}
        aria-pressed={value === null}
        onClick={() => onChange(null)}
      >
        <span className="lab">Все дни</span>
        <span className="sm muted">{pluralPhotos(total)}</span>
      </button>
      {ordered.map((d) => (
        <button
          key={d.observed_on}
          type="button"
          className={styles.day}
          aria-pressed={value === d.observed_on}
          onClick={() => onChange(d.observed_on)}
          onMouseEnter={() => onPreview?.(d.observed_on)}
          onFocus={() => onPreview?.(d.observed_on)}
        >
          <span className="lab data">{formatDate(d.observed_on)}</span>
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
