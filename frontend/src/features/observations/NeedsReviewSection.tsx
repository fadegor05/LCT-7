import { useState } from 'react'
import { useSetPhotoDate, useUndatedPhotos } from '@/api/frames'
import type { Photo } from '@/api/schemas'
import { SectionHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Pill } from '@/components/ui/Pill'
import { QueryState } from '@/components/ui/QueryState'
import { parseRuDate, todayIso } from '@/lib/format'
import { pluralPhotos, processingStatusLabels } from '@/lib/labels'
import styles from './Observations.module.css'

const FORMAT_ERROR = 'Формат: дд.мм.гггг'
const FUTURE_ERROR = 'Дата не может быть позже сегодняшней'

function PhotoDateRow({ photo, siteId }: { photo: Photo; siteId: string }) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const setDate = useSetPhotoDate(siteId)
  const submit = () => {
    const parsed = /\d{4}\s*$/.test(value) ? parseRuDate(value, 0) : null
    if (!parsed) return setError(FORMAT_ERROR)
    // Дублирует проверку сервера, чтобы не гонять заведомо отклонённый запрос.
    if (parsed > todayIso()) return setError(FUTURE_ERROR)
    setError(null)
    setDate.mutate({ photoId: photo.id, capturedOn: parsed })
  }
  const message = error ?? setDate.error?.message
  return (
    <li className={styles.reviewRow}>
      <span className={`sm ${styles.reviewName}`} title={photo.original_name}>
        {photo.original_name}
      </span>
      <span className={`sm muted ${styles.reviewStatus}`}>
        {processingStatusLabels[photo.processing_status]}
      </span>
      <span className={`sm muted ${styles.reviewHint}`}>
        Даты нет ни в метаданных, ни в имени файла, ни у соседних снимков
      </span>
      <span className={styles.dateField}>
        <input
          className={styles.input}
          placeholder="дд.мм.гггг"
          aria-label={`Дата съёмки ${photo.original_name}`}
          aria-invalid={message ? true : undefined}
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        {message && (
          <span className="sm" role="alert" style={{ color: 'var(--status-behind)' }}>
            {message}
          </span>
        )}
      </span>
      <Button variant="ghost" size="sm" onClick={submit} disabled={setDate.isPending}>
        Задать дату
      </Button>
    </li>
  )
}

/** «Без даты» (UC-8): такие снимки не участвуют в расчётах, пока дата не задана. */
export function NeedsReviewSection({ siteId }: { siteId: string }) {
  const undated = useUndatedPhotos(siteId)
  return (
    <section
      id="no-date"
      style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}
    >
      <QueryState query={undated}>
        {(photos) => (
          <>
            <SectionHeader
              title="Без даты"
              description={
                photos.length
                  ? `${pluralPhotos(photos.length)}. Не участвуют в расчётах, пока дата не задана.`
                  : 'У всех снимков известна дата.'
              }
              actions={photos.length > 0 && <Pill tone="caution">Требует проверки</Pill>}
            />
            {photos.length > 0 && (
              <>
                <Callout tone="caution" title="Дата задаётся вручную">
                  Дата съёмки не бывает в будущем. После неё снимок попадёт в наблюдение за этот
                  день, и выводы по стройке пересчитаются.
                </Callout>
                <ul className={styles.review} aria-label="Снимки без даты">
                  {photos.map((photo) => (
                    <PhotoDateRow key={photo.id} photo={photo} siteId={siteId} />
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </QueryState>
    </section>
  )
}
