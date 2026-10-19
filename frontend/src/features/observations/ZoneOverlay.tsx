import type { Zone } from '@/api/schemas'
import styles from './Observations.module.css'

interface ZoneOverlayProps {
  zone: Zone
  /** Размер кадра в пикселях: контур кадрируется так же, как снимок (`cover`). */
  width: number
  height: number
}

/**
 * Рабочая зона камеры поверх снимка (как в clean-mvp). `slice` в SVG — то же, что `cover` у
 * снимка: на миниатюре 4:3 контур совпадает с картинкой при любых пропорциях кадра.
 */
export function ZoneOverlay({ zone, width, height }: ZoneOverlayProps) {
  const points = zone.map(([x, y]) => `${x * width},${y * height}`).join(' ')
  return (
    <svg
      className={styles.zone}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid slice"
      role="img"
      aria-label="Рабочая зона камеры"
    >
      {/* Белая подложка под пунктиром: контур виден и на небе, и на земле */}
      <polygon className={styles.zoneHalo} points={points} vectorEffect="non-scaling-stroke" />
      <polygon points={points} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}
