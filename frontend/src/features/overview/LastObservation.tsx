import { useState } from 'react'
import { Link } from 'react-router'
import { annotatedThumbUrl, useObservations, usePhotos } from '@/api/frames'
import type { Photo } from '@/api/schemas'
import { DateSourceBadge } from '@/components/ui/DateSourceBadge'
import { FrameView } from '@/components/ui/FrameView'
import { SectionHeader } from '@/components/layout/PageHeader'
import { formatDate, formatTime, latestObservation } from '@/lib/format'
import { byShotTime } from '@/features/observations/photoOrder'
import { PhotoViewer } from '@/features/observations/PhotoViewer'
import { observationSentence } from './observationSentence'
import styles from './Overview.module.css'

const VISIBLE = 3

export function LastObservation({ siteId }: { siteId: string }) {
  const last = latestObservation(useObservations(siteId).data)
  const photos = usePhotos(siteId).data ?? []
  const [open, setOpen] = useState<Photo | null>(null)

  if (!last) return null
  // Как в clean-mvp: кадры с техникой, по одному с камеры, затем остальные — по времени
  const ofDay = photos
    .filter((p) => p.captured_on === last.observed_on)
    .sort((a, b) => (b.machines?.length ? 1 : 0) - (a.machines?.length ? 1 : 0) || byShotTime(a, b))
  const seen = new Set<string>()
  const picked = [
    ...ofDay.filter((p) => {
      const cam = p.camera_id ?? p.id
      if (!p.machines?.length || seen.has(cam)) return false
      seen.add(cam)
      return true
    }),
    ...ofDay,
  ]
    .filter((p, i, all) => all.indexOf(p) === i)
    .slice(0, VISIBLE)
  return (
    <section className={styles.section}>
      <SectionHeader
        title={`Последнее наблюдение · ${formatDate(last.observed_on)}`}
        description={observationSentence(last)}
        actions={
          <Link to={`/sites/${siteId}/observations`} className="sm">
            Открыть наблюдения →
          </Link>
        }
      />
      <div className={styles.frames}>
        {picked.map((p) => (
          <FrameView
            key={p.id}
            imageUrl={annotatedThumbUrl(siteId, p.id)}
            alt={`Снимок ${p.original_name}`}
            onClick={() => setOpen(p)}
            caption={
              <>
                {p.captured_at && <span className="data">{formatTime(p.captured_at)}</span>}
                {p.date_source && <DateSourceBadge source={p.date_source} />}
                <span className="sm">
                  {p.machines?.length ? p.machines.join(', ') : 'нет техники'}
                </span>
              </>
            }
          />
        ))}
      </div>
      {open && <PhotoViewer siteId={siteId} photo={open} onClose={() => setOpen(null)} />}
    </section>
  )
}
