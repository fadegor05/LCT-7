import { useRef, useState, type PointerEvent } from 'react'
import type { Point } from '@/api/schemas'
import styles from './Cameras.module.css'

interface ZoneEditorProps {
  imageUrl: string | null
  points: readonly Point[]
  closed: boolean
  onChange: (points: Point[], closed: boolean) => void
}

const clamp = (v: number) => Math.min(1, Math.max(0, v))
const round = (v: number) => Math.round(v * 1000) / 1000

/**
 * Рисование рабочей зоны: клик ставит вершину, клик по первой вершине замыкает контур,
 * вершины перетаскиваются. Координаты — доли кадра 0–1 (DataModel: camera.zone_polygon).
 */
export function ZoneEditor({ imageUrl, points, closed, onChange }: ZoneEditorProps) {
  const box = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState<number | null>(null)

  const toPoint = (event: PointerEvent): Point => {
    const rect = box.current!.getBoundingClientRect()
    return [
      round(clamp((event.clientX - rect.left) / (rect.width || 1))),
      round(clamp((event.clientY - rect.top) / (rect.height || 1))),
    ]
  }

  const onSurfaceDown = (event: PointerEvent<HTMLDivElement>) => {
    if (closed || dragging !== null) return
    onChange([...points, toPoint(event)], false)
  }

  const onVertexDown = (index: number) => (event: PointerEvent<HTMLButtonElement>) => {
    event.stopPropagation()
    if (!closed && index === 0 && points.length >= 3) {
      onChange([...points], true)
      return
    }
    box.current?.setPointerCapture?.(event.pointerId)
    setDragging(index)
  }

  const onMove = (event: PointerEvent<HTMLDivElement>) => {
    if (dragging === null) return
    const next = points.map((p, i) => (i === dragging ? toPoint(event) : p))
    onChange(next, closed)
  }

  const coords = points.map(([x, y]) => `${x},${y}`).join(' ')

  return (
    <div
      ref={box}
      className={styles.editor}
      data-testid="zone-editor"
      style={imageUrl ? { backgroundImage: `url(${imageUrl})` } : undefined}
      onPointerDown={onSurfaceDown}
      onPointerMove={onMove}
      onPointerUp={() => setDragging(null)}
    >
      {!imageUrl && points.length === 0 && (
        <div className={styles.empty}>
          <p className="lab">Кадра пока нет</p>
          <p className="sm muted">
            Возьмите кадр со стрима или загрузите свой. Затем кликайте по нему, чтобы очертить
            рабочую зону.
          </p>
        </div>
      )}
      <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
        {closed ? (
          <polygon className={styles.polygon} points={coords} />
        ) : (
          points.length > 1 && <polyline className={styles.polyline} points={coords} />
        )}
      </svg>
      {points.map(([x, y], i) => (
        <button
          key={i}
          type="button"
          className={[styles.vertex, i === 0 && !closed && styles.vertexFirst]
            .filter(Boolean)
            .join(' ')}
          style={{ left: `${x * 100}%`, top: `${y * 100}%` }}
          aria-label={
            i === 0 && !closed && points.length >= 3 ? 'Замкнуть контур' : `Вершина ${i + 1}`
          }
          onPointerDown={onVertexDown(i)}
        />
      ))}
    </div>
  )
}
