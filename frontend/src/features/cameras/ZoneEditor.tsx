import { useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from 'react'
import type { Zone } from '@/api/schemas'
import styles from './ZoneEditor.module.css'

interface ZoneEditorProps {
  imageUrl: string | null
  /** Ширина к высоте кадра: контур рисуется в долях кадра 0–1. */
  aspect: number
  /** Замкнутый контур или `null`, пока зона не задана. */
  value: Zone | null
  onChange: (zone: Zone | null) => void
  /** Начат, но не замкнут контур: сохранять такую зону нельзя. */
  onOpenContour?: (open: boolean) => void
  /** Кадр-подложка не загрузился. */
  onImageError?: () => void
}

const H = 1000 // высота области рисования в единицах SVG
const MIN_POINTS = 3
const DRAG_PX = 4 // меньше — это нажатие, а не перетаскивание (дрожание пальца)
const KEY_STEP = 0.01 // шаг стрелок клавиатуры, доля кадра

const clamp = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 10_000) / 10_000

interface Drag {
  index: number
  x: number
  y: number
  moved: boolean
}

/**
 * Редактор рабочей зоны (§8.5): клик ставит вершину, клик по первой точке замыкает контур,
 * вершины перетаскиваются, клик по стороне добавляет вершину, выделенная вершина удаляется
 * клавишей Delete (не меньше трёх у замкнутого контура). Вершины — кнопки постоянного
 * размера: в них попадает палец, до них доходит Tab, стрелки двигают выделенную.
 */
export function ZoneEditor({
  imageUrl,
  aspect,
  value,
  onChange,
  onOpenContour,
  onImageError,
}: ZoneEditorProps) {
  const svg = useRef<SVGSVGElement>(null)
  const box = useRef<HTMLDivElement>(null)
  const [draft, setDraftState] = useState<Zone>([])
  const [selected, setSelected] = useState<number | null>(null)
  const drag = useRef<Drag | null>(null)
  const W = H * aspect
  const closed = value !== null
  const points = value ?? draft

  const setDraft = (next: Zone) => {
    setDraftState(next)
    onOpenContour?.(next.length > 0)
  }
  const at = (event: { clientX: number; clientY: number }): [number, number] => {
    const rect = svg.current!.getBoundingClientRect()
    return [
      clamp((event.clientX - rect.left) / rect.width),
      clamp((event.clientY - rect.top) / rect.height),
    ]
  }
  const put = (next: Zone) => (closed ? onChange(next) : setDraft(next))

  const onBackground = (event: PointerEvent<SVGSVGElement>) => {
    if (closed || event.target !== event.currentTarget) return
    setDraft([...draft, at(event)])
    setSelected(null)
  }

  const onVertexDown = (event: PointerEvent<HTMLButtonElement>, index: number) => {
    event.stopPropagation()
    // Захват: перетаскивание не теряется, если указатель ушёл за кадр
    box.current?.setPointerCapture?.(event.pointerId)
    drag.current = { index, x: event.clientX, y: event.clientY, moved: false }
    setSelected(index)
  }

  const end = () => {
    drag.current = null
  }

  const onMove = (event: PointerEvent<HTMLDivElement>) => {
    const state = drag.current
    if (!state) return
    // Кнопку отпустили там, куда pointerup не дошёл: перетаскивание закончено
    if (event.buttons === 0) return end()
    if (!state.moved && Math.hypot(event.clientX - state.x, event.clientY - state.y) < DRAG_PX) {
      return
    }
    state.moved = true
    const next = points.slice()
    next[state.index] = at(event)
    put(next)
  }

  const onUp = () => {
    const state = drag.current
    end()
    // Нажатие без перетаскивания по первой точке открытого контура — замкнуть его
    if (state && !state.moved && !closed && state.index === 0 && draft.length >= MIN_POINTS) {
      onChange(draft)
      setDraft([])
      setSelected(null)
    }
  }

  const insert = (event: PointerEvent<SVGLineElement>, after: number) => {
    event.stopPropagation()
    const next = points.slice()
    next.splice(after + 1, 0, at(event))
    onChange(next)
    setSelected(after + 1)
  }

  const remove = (index: number | null) => {
    if (index === null || (closed && points.length <= MIN_POINTS)) return
    put(points.filter((_, i) => i !== index))
    setSelected(null)
  }

  const onVertexKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const shifts: Record<string, [number, number]> = {
      ArrowLeft: [-KEY_STEP, 0],
      ArrowRight: [KEY_STEP, 0],
      ArrowUp: [0, -KEY_STEP],
      ArrowDown: [0, KEY_STEP],
    }
    const shift = shifts[event.key]
    if (shift) {
      event.preventDefault()
      const next = points.slice()
      const [x, y] = next[index]!
      next[index] = [clamp(x + shift[0]), clamp(y + shift[1])]
      put(next)
    } else if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault()
      event.stopPropagation()
      remove(index)
    }
  }

  const line = points.map((p) => `${p[0] * W},${p[1] * H}`).join(' ')

  return (
    <div
      ref={box}
      className={styles.frame}
      style={{ aspectRatio: `${aspect}`, '--aspect': aspect } as CSSProperties}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onPointerCancel={end}
      onLostPointerCapture={end}
    >
      {imageUrl && (
        <img
          className={styles.image}
          src={imageUrl}
          alt="Кадр для ориентира"
          onError={onImageError}
        />
      )}
      <svg
        ref={svg}
        className={styles.svg}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="application"
        aria-label="Рабочая зона"
        tabIndex={0}
        onPointerDown={onBackground}
        onKeyDown={(event) => {
          if (event.key === 'Delete' || event.key === 'Backspace') remove(selected)
        }}
      >
        {closed ? (
          <polygon className={styles.area} points={line} />
        ) : (
          <polyline className={styles.path} points={line} />
        )}
        {closed &&
          points.map((p, i) => {
            const q = points[(i + 1) % points.length]!
            return (
              <line
                key={`edge-${i}`}
                className={styles.edge}
                x1={p[0] * W}
                y1={p[1] * H}
                x2={q[0] * W}
                y2={q[1] * H}
                data-testid={`edge-${i}`}
                onPointerDown={(event) => insert(event, i)}
              />
            )
          })}
      </svg>
      {points.map((p, i) => (
        <button
          key={`v-${i}`}
          type="button"
          className={[
            styles.vertex,
            i === selected && styles.selected,
            !closed && i === 0 && styles.first,
          ]
            .filter(Boolean)
            .join(' ')}
          style={{ left: `${p[0] * 100}%`, top: `${p[1] * 100}%` }}
          aria-label={`Вершина ${i + 1}`}
          aria-pressed={i === selected}
          onPointerDown={(event) => onVertexDown(event, i)}
          onFocus={() => setSelected(i)}
          onKeyDown={(event) => onVertexKey(event, i)}
        />
      ))}
    </div>
  )
}
