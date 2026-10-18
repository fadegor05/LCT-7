import { useState } from 'react'
import { Link } from 'react-router'
import { annotatedImageUrl, useObservations, usePhotos } from '@/api/frames'
import type { Photo } from '@/api/schemas'
import { DateSourceBadge } from '@/components/ui/DateSourceBadge'
import { FrameView } from '@/components/ui/FrameView'
import { SectionHeader } from '@/components/layout/PageHeader'
import { formatDate, latestObservation } from '@/lib/format'
import { PhotoViewer } from '@/features/observations/PhotoViewer'
import { observationSentence } from './observationSentence'
import styles from './Overview.module.css'

const VISIBLE = 3

export function LastObservation({ siteId }: { siteId: string }) {
  const last = latestObservation(useObservations(siteId).data)
  const photos = usePhotos(siteId).data ?? []
  const [open, setOpen] = useState<Photo | null>(null)

  if (!last) return null
  const ofDay = photos.filter((p) => p.captured_on === last.observed_on).slice(0, VISIBLE)
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
        {ofDay.map((p) => (
          <FrameView
            key={p.id}
            imageUrl={annotatedImageUrl(siteId, p.id)}
            alt={`Снимок ${p.original_name}`}
            onClick={() => setOpen(p)}
            caption={
              <>
                <span className="sm">{p.original_name}</span>
                {p.date_source && <DateSourceBadge source={p.date_source} />}
              </>
            }
          />
        ))}
      </div>
      {open && <PhotoViewer siteId={siteId} photo={open} onClose={() => setOpen(null)} />}
    </section>
  )
}
