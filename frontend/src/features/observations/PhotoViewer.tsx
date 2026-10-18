import { useEffect, useState, type CSSProperties } from 'react'
import { originalImageUrl, usePhoto } from '@/api/frames'
import { useAuthorizedImage } from '@/api/images'
import type { Photo } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Dialog } from '@/components/ui/Dialog'
import { formatDate } from '@/lib/format'
import { DetectionOverlay } from './DetectionOverlay'
import styles from './PhotoViewer.module.css'
import { useZoomPan } from './useZoomPan'

interface PhotoViewerProps {
  siteId: string
  photo: Photo
  onClose: () => void
}

/** Снимок оригинального качества с рамками техники; колесо и кнопки приближают. */
export function PhotoViewer({ siteId, photo, onClose }: PhotoViewerProps) {
  const { view, containerRef, handlers, zoomIn, zoomOut, reset, isZoomed } = useZoomPan()
  const src = useAuthorizedImage(originalImageUrl(siteId, photo.id))
  const detail = usePhoto(siteId, photo.id)
  const [activeId, setActiveId] = useState<string | null>(null)

  // React вешает onWheel пассивно, и preventDefault там не работает, поэтому гасим скролл страницы нативно
  useEffect(() => {
    const viewport = containerRef.current
    if (!viewport) return undefined
    const stop = (event: WheelEvent) => event.preventDefault()
    viewport.addEventListener('wheel', stop, { passive: false })
    return () => viewport.removeEventListener('wheel', stop)
  }, [containerRef])

  const title = photo.captured_on
    ? `${photo.original_name} · ${formatDate(photo.captured_on)}`
    : photo.original_name
  const ratio = photo.height > 0 ? photo.width / photo.height : 4 / 3

  return (
    <Dialog wide title={title} onClose={onClose}>
      <div
        ref={containerRef}
        className={[styles.viewport, isZoomed && styles.grab].filter(Boolean).join(' ')}
        style={{ '--ratio': ratio } as CSSProperties}
        onWheel={handlers.onWheel}
        onPointerDown={handlers.onPointerDown}
        onPointerMove={handlers.onPointerMove}
        onPointerUp={handlers.onPointerUp}
        onDoubleClick={handlers.onDoubleClick}
      >
        <div
          className={styles.layer}
          style={
            {
              transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
              '--zoom': view.scale,
            } as CSSProperties
          }
        >
          {src && (
            <img
              className={styles.image}
              src={src}
              alt={`Снимок ${photo.original_name}`}
              draggable={false}
            />
          )}
          <DetectionOverlay
            detections={detail.data?.detections ?? []}
            activeId={activeId}
            onActive={setActiveId}
          />
        </div>
      </div>

      <div className={styles.toolbar}>
        <Button variant="secondary" size="icon" aria-label="Уменьшить" onClick={zoomOut}>
          −
        </Button>
        <Button variant="secondary" size="icon" aria-label="Увеличить" onClick={zoomIn}>
          +
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Сбросить масштаб"
          disabled={!isZoomed}
          onClick={reset}
        >
          100%
        </Button>
      </div>
      <p className="sm muted">
        Колесо мыши — приближение, двойной щелчок — сброс. Наведите на рамку, чтобы увидеть технику.
      </p>
      {detail.isError && <Callout tone="caution">Не удалось загрузить рамки</Callout>}
    </Dialog>
  )
}
