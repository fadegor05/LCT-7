import { Link } from 'react-router'
import { useFrames, useObservation, useObservationDays } from '@/api/frames'
import type { Frame } from '@/api/schemas'
import { DateSourceBadge } from '@/components/ui/DateSourceBadge'
import { FrameView } from '@/components/ui/FrameView'
import { SectionHeader } from '@/components/layout/PageHeader'
import { useEquipmentName } from '@/features/observations/useEquipmentName'
import { formatShortDate, formatTime } from '@/lib/format'
import { observationSentence } from './observationSentence'
import styles from './Overview.module.css'

/** Последний кадр каждой камеры за дату. */
function latestPerCamera(frames: readonly Frame[]): Frame[] {
  const byCamera = new Map<string, Frame>()
  for (const f of frames) byCamera.set(f.camera_id ?? f.id, f)
  return [...byCamera.values()].slice(0, 3)
}

export function LastObservation({ siteId }: { siteId: string }) {
  const days = useObservationDays(siteId)
  const date = days.data?.at(-1)?.obs_date ?? null
  const observation = useObservation(siteId, date)
  const frames = useFrames(siteId, date)
  const name = useEquipmentName()

  if (!date) return null
  return (
    <section className={styles.section}>
      <SectionHeader
        title={`Последнее наблюдение · ${formatShortDate(date)}`}
        description={observation.data && observationSentence(observation.data)}
        actions={
          <Link to={`/sites/${siteId}/observations`} className="sm">
            Открыть наблюдения →
          </Link>
        }
      />
      <div className={styles.frames}>
        {latestPerCamera(frames.data ?? []).map((f) => (
          <FrameView
            key={f.id}
            imageUrl={f.image_url}
            detections={f.detections}
            classLabel={name}
            alt={`Кадр ${f.camera_name ?? ''} ${formatTime(f.captured_at)}`}
            caption={
              <>
                <span className="data">{formatTime(f.captured_at)}</span>
                {f.date_source && <DateSourceBadge source={f.date_source} />}
                <span className="muted">{f.camera_name}</span>
              </>
            }
          />
        ))}
      </div>
    </section>
  )
}
