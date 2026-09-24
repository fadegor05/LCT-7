import type { ReactNode } from 'react'
import type { Detection, Point } from '@/api/schemas'
import { Icon } from './Icon'
import styles from './FrameView.module.css'

interface FrameViewProps {
  imageUrl: string | null
  detections?: readonly Detection[]
  /** Подпись рамки по коду класса техники. */
  classLabel?: (code: string) => string
  /** Рабочая зона камеры в долях кадра — рисуется поверх снимка. */
  zone?: readonly Point[] | null
  caption?: ReactNode
  alt?: string
}

/** Кадр с рамками найденной техники; координаты рамок и зоны в долях кадра 0–1. */
export function FrameView({
  imageUrl,
  detections = [],
  classLabel = (code) => code,
  zone,
  caption,
  alt = 'Снимок',
}: FrameViewProps) {
  return (
    <figure className={styles.frame}>
      <div
        className={styles.img}
        role="img"
        aria-label={alt}
        style={imageUrl ? { backgroundImage: `url(${imageUrl})` } : undefined}
      >
        {!imageUrl && (
          <span className={styles.placeholder} aria-hidden="true">
            <Icon name="camera" size={20} />
            Снимок
          </span>
        )}
        {zone && zone.length >= 3 && (
          <svg
            className={styles.zone}
            viewBox="0 0 1 1"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <polygon points={zone.map(([x, y]) => `${x},${y}`).join(' ')} />
          </svg>
        )}
        {detections.map((d) => (
          <span
            key={d.id}
            className={styles.box}
            style={{
              left: `${d.bbox_x * 100}%`,
              top: `${d.bbox_y * 100}%`,
              width: `${d.bbox_w * 100}%`,
              height: `${d.bbox_h * 100}%`,
            }}
          >
            <span className={styles.boxLabel}>{classLabel(d.equipment_class)}</span>
          </span>
        ))}
      </div>
      {caption && <figcaption className={styles.caption}>{caption}</figcaption>}
    </figure>
  )
}
