import type { Detection } from '@/api/schemas'
import styles from './DetectionOverlay.module.css'

interface Props {
  detections: readonly Detection[]
  activeId: string | null
  onActive: (id: string | null) => void
}

// Подпись у верхнего края кадра выводим внутри рамки, иначе она уйдёт за пределы фото.
const EDGE = 0.08

export function DetectionOverlay({ detections, activeId, onActive }: Props) {
  const hovered = detections.find((d) => d.id === activeId) ?? null
  // Пока курсор не на рамке, подписываем самую уверенную детекцию: снимок открылся — машина видна сразу
  const featured = detections.reduce<Detection | null>(
    (best, d) => (best === null || d.score > best.score ? d : best),
    null,
  )
  const active = hovered ?? featured
  const [activeX = 0, activeY = 0] = active?.bbox ?? []

  return (
    <div className={styles.root}>
      <svg className={styles.svg} viewBox="0 0 1 1" preserveAspectRatio="none">
        {/* Светлая подложка под рамкой: контур виден и на небе, и на земле */}
        {detections.map((d) => {
          const [x1 = 0, y1 = 0, x2 = 0, y2 = 0] = d.bbox
          // Подложка гаснет вместе со своей рамкой, иначе у приглушённой рамки остаётся яркая обводка
          const isMuted = activeId !== null && d.id !== activeId
          return (
            <rect
              key={`halo-${d.id}`}
              className={[styles.halo, isMuted && styles.muted].filter(Boolean).join(' ')}
              x={x1}
              y={y1}
              width={x2 - x1}
              height={y2 - y1}
              vectorEffect="non-scaling-stroke"
              aria-hidden="true"
            />
          )
        })}
        {detections.map((d) => {
          const [x1 = 0, y1 = 0, x2 = 0, y2 = 0] = d.bbox
          const isActive = d.id === activeId
          const isMuted = activeId !== null && !isActive
          const className = [styles.box, isActive && styles.active, isMuted && styles.muted]
            .filter(Boolean)
            .join(' ')
          return (
            <rect
              key={d.id}
              className={className}
              x={x1}
              y={y1}
              width={x2 - x1}
              height={y2 - y1}
              vectorEffect="non-scaling-stroke"
              tabIndex={0}
              aria-label={`${d.equipment_title}, ${Math.round(d.score * 100)}%`}
              onMouseEnter={() => onActive(d.id)}
              onMouseLeave={() => onActive(null)}
              onFocus={() => onActive(d.id)}
              onBlur={() => onActive(null)}
            />
          )
        })}
      </svg>
      {active && (
        <div
          className={[styles.label, activeY < EDGE && styles.labelInside].filter(Boolean).join(' ')}
          style={{ left: `${activeX * 100}%`, top: `${activeY * 100}%` }}
        >
          {`${active.equipment_title} · ${Math.round(active.score * 100)}%`}
        </div>
      )}
    </div>
  )
}
