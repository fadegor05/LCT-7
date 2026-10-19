import { type ReactNode, useLayoutEffect, useRef, useState } from 'react'
import { annotatedThumbUrl, useRedetectPhoto } from '@/api/frames'
import type { Photo, Zone } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { DateSourceBadge } from '@/components/ui/DateSourceBadge'
import { FrameView } from '@/components/ui/FrameView'
import { Pill } from '@/components/ui/Pill'
import { formatShortDate, formatShortDateTime, formatTime } from '@/lib/format'
import { processingStatusLabels } from '@/lib/labels'
import styles from './Observations.module.css'
import { byShotTime } from './photoOrder'
import { PhotoViewer } from './PhotoViewer'
import { ZoneOverlay } from './ZoneOverlay'

const CARD_WIDTH = 240 // как grid-auto-columns ленты

interface PhotoStripProps {
  siteId: string
  photos: readonly Photo[]
  /** Показывать дату у снимков (режим «Все дни»). */
  withDate: boolean
  /** Рабочая зона камеры: контур поверх миниатюр. */
  zone?: Zone | null
  /** Заголовок ленты (имя камеры) — в одной строке с кнопками ‹ ›. */
  title?: ReactNode
}

/** Время кадра: «14:20», в режиме «Все дни» — «ПТ 18.09 14:20»; без времени — дата. */
function frameTime(p: Photo, withDate: boolean): string {
  if (p.captured_at)
    return withDate ? formatShortDateTime(p.captured_at) : formatTime(p.captured_at)
  return withDate ? formatShortDate(p.captured_on) : 'время неизвестно'
}

/** Машины кадра одной строкой: «Автокран, самосвал». */
function machinesText(p: Photo): string {
  if (p.processing_status !== 'done') return processingStatusLabels[p.processing_status]
  const names = p.machines ?? []
  if (names.length === 0) return 'нет техники'
  return names.map((n, i) => (i ? n.charAt(0).toLowerCase() + n.slice(1) : n)).join(', ')
}

/**
 * Лента кадров одной камеры с кнопками ‹ › (как в clean-mvp): миниатюры без подписей рамок,
 * под кадром — время, источник даты и какая техника на нём; «Вне зоны» и «Доказательство».
 * Необработанные снимки можно отправить детектору ещё раз.
 */
export function PhotoStrip({ siteId, photos, withDate, zone = null, title }: PhotoStripProps) {
  const redetect = useRedetectPhoto(siteId)
  const [open, setOpen] = useState<Photo | null>(null)
  const list = useRef<HTMLDivElement>(null)
  const ordered = [...photos].sort(byShotTime)
  // «Все дни»: лента сразу у самых новых кадров справа, без проезда через все кадры
  useLayoutEffect(() => {
    const el = list.current
    if (!withDate || !el) return
    if (el.scrollTo) el.scrollTo({ left: el.scrollWidth, behavior: 'instant' })
    else el.scrollLeft = el.scrollWidth
  }, [withDate, photos])
  if (photos.length === 0) return <p className="muted">Снимков за этот период нет.</p>
  const step = (direction: number) =>
    list.current?.scrollBy?.({
      // Почти экран ленты, но не меньше карточки: узкая лента всё равно сдвигается
      left: direction * Math.max(list.current.clientWidth * 0.8, CARD_WIDTH),
    })
  return (
    <>
      <div className={styles.stripHead}>
        {title ?? <span />}
        <Button
          variant="ghost"
          size="icon"
          icon="chevronLeft"
          aria-label="Назад по времени"
          onClick={() => step(-1)}
        />
        <Button
          variant="ghost"
          size="icon"
          icon="chevronRight"
          aria-label="Вперёд по времени"
          onClick={() => step(1)}
        />
      </div>
      <div ref={list} className={styles.frames} data-testid="strip">
        {ordered.map((p) => (
          <FrameView
            key={p.id}
            imageUrl={annotatedThumbUrl(siteId, p.id)}
            alt={`Снимок ${p.original_name}`}
            onClick={() => setOpen(p)}
            overlay={zone && <ZoneOverlay zone={zone} width={p.width} height={p.height} />}
            caption={
              <>
                <span className="data">{frameTime(p, withDate)}</span>
                {p.date_source && <DateSourceBadge source={p.date_source} />}
                <span className="sm">{machinesText(p)}</span>
                {/* Машина за контуром зоны: из таких кадров движок выводит простой и «вне зоны» */}
                {p.out_of_zone && (
                  <Pill tone="caution" size="sm">
                    Вне зоны
                  </Pill>
                )}
                {p.evidence && (
                  <Pill tone="accent" size="sm">
                    Доказательство
                  </Pill>
                )}
                {p.processing_status !== 'done' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={redetect.isPending}
                    onClick={() => redetect.mutate(p.id)}
                  >
                    Обработать ещё раз
                  </Button>
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
