import { useState } from 'react'
import { annotatedImageUrl, useRedetectPhoto } from '@/api/frames'
import type { Photo } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { DateSourceBadge } from '@/components/ui/DateSourceBadge'
import { FrameView } from '@/components/ui/FrameView'
import { formatDate } from '@/lib/format'
import { processingStatusLabels } from '@/lib/labels'
import styles from './Observations.module.css'
import { PhotoViewer } from './PhotoViewer'

interface PhotoStripProps {
  siteId: string
  photos: readonly Photo[]
  /** Показывать дату у снимков (режим «Все дни»). */
  withDate: boolean
}

/** Снимки с рамками найденной техники; необработанные можно отправить детектору ещё раз. */
export function PhotoStrip({ siteId, photos, withDate }: PhotoStripProps) {
  const redetect = useRedetectPhoto(siteId)
  const [open, setOpen] = useState<Photo | null>(null)
  if (photos.length === 0) return <p className="muted">Снимков за этот период нет.</p>
  return (
    <>
      <div className={styles.frames}>
        {photos.map((p) => (
          <FrameView
            key={p.id}
            imageUrl={annotatedImageUrl(siteId, p.id)}
            alt={`Снимок ${p.original_name}`}
            onClick={() => setOpen(p)}
            caption={
              <>
                <span className="sm">{p.original_name}</span>
                {withDate && <span className="data">{formatDate(p.captured_on)}</span>}
                {p.date_source && <DateSourceBadge source={p.date_source} />}
                {p.processing_status !== 'done' && (
                  <>
                    <span className="sm muted">{processingStatusLabels[p.processing_status]}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={redetect.isPending}
                      onClick={() => redetect.mutate(p.id)}
                    >
                      Обработать ещё раз
                    </Button>
                  </>
                )}
              </>
            }
          />
        ))}
      </div>
      {open && <PhotoViewer siteId={siteId} photo={open} onClose={() => setOpen(null)} />}
      {redetect.error && (
        <Callout tone="behind" title="Снимок не обработан">
          {redetect.error.message}
        </Callout>
      )}
    </>
  )
}
