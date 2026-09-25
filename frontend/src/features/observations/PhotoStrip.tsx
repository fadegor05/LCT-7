import { annotatedImageUrl, useRedetectPhoto } from '@/api/frames'
import type { Photo } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { DateSourceBadge } from '@/components/ui/DateSourceBadge'
import { FrameView } from '@/components/ui/FrameView'
import { formatShortDate } from '@/lib/format'
import { processingStatusLabels } from '@/lib/labels'
import styles from './Observations.module.css'

interface PhotoStripProps {
  siteId: string
  photos: readonly Photo[]
  /** Показывать дату у снимков (режим «Все дни»). */
  withDate: boolean
}

/** Снимки с рамками найденной техники; необработанные можно отправить детектору ещё раз. */
export function PhotoStrip({ siteId, photos, withDate }: PhotoStripProps) {
  const redetect = useRedetectPhoto(siteId)
  if (photos.length === 0) return <p className="muted">Снимков за этот период нет.</p>
  return (
    <>
      <div className={styles.frames}>
        {photos.map((p) => (
          <FrameView
            key={p.id}
            imageUrl={annotatedImageUrl(siteId, p.id)}
            alt={`Снимок ${p.original_name}`}
            caption={
              <>
                <span className="sm">{p.original_name}</span>
                {withDate && <span className="data">{formatShortDate(p.captured_on)}</span>}
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
      {redetect.error && (
        <Callout tone="behind" title="Снимок не обработан">
          {redetect.error.message}
        </Callout>
      )}
    </>
  )
}
