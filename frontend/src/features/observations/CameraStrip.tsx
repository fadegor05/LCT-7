import { useRef } from 'react'
import type { Frame } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { DateSourceBadge } from '@/components/ui/DateSourceBadge'
import { FrameView } from '@/components/ui/FrameView'
import { formatShortDateTime, formatTime } from '@/lib/format'
import { pluralFrames, pluralMachines, sourceTypeLabels } from '@/lib/labels'
import styles from './Observations.module.css'

interface CameraStripProps {
  name: string
  frames: readonly Frame[]
  /** Показывать дату у кадров (режим «Все дни»). */
  withDate: boolean
  classLabel: (code: string) => string
}

const SCROLL = 480

/** Лента кадров одной камеры: слева направо по времени съёмки, прокручивается отдельно. */
export function CameraStrip({ name, frames, withDate, classLabel }: CameraStripProps) {
  const strip = useRef<HTMLDivElement>(null)
  const last = frames.at(-1)?.captured_at
  const time = withDate ? formatShortDateTime : formatTime
  const scroll = (left: number) => strip.current?.scrollBy?.({ left, behavior: 'smooth' })

  return (
    <section className={styles.strip} aria-label={`Камера ${name}`}>
      <div className={styles.stripHead}>
        <div>
          <h3>{name}</h3>
          <p className="sm muted">
            {pluralFrames(frames.length)}
            {last && ` · последний ${time(last)}`}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          icon="chevronLeft"
          aria-label="Назад по времени"
          onClick={() => scroll(-SCROLL)}
        />
        <Button
          variant="ghost"
          size="icon"
          icon="chevronRight"
          aria-label="Вперёд по времени"
          onClick={() => scroll(SCROLL)}
        />
      </div>
      <div ref={strip} className={styles.frames}>
        {frames.map((f) => (
          <FrameView
            key={f.id}
            imageUrl={f.image_url}
            detections={f.detections}
            classLabel={classLabel}
            alt={`Кадр ${name} ${time(f.captured_at)}`}
            caption={
              <>
                <span className="sm muted">{sourceTypeLabels[f.source_type]}</span>
                <span className="data">{time(f.captured_at)}</span>
                {f.date_source && <DateSourceBadge source={f.date_source} />}
                <span className="sm muted">
                  {f.detections.length ? pluralMachines(f.detections.length) : 'нет техники'}
                </span>
              </>
            }
          />
        ))}
      </div>
    </section>
  )
}
