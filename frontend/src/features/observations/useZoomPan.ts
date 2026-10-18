import { useRef, useState } from 'react'

/** Вид контента: масштаб и сдвиг в px (transform: translate(x,y) scale(scale), origin 0 0). */
export interface View {
  scale: number
  x: number
  y: number
}

export interface Box {
  width: number
  height: number
}

export interface Point {
  x: number
  y: number
}

const INITIAL: View = { scale: 1, x: 0, y: 0 }
const WHEEL_FACTOR = 1.2
const BUTTON_FACTOR = 1.5

/** Ограничивает масштаб и не даёт контенту уйти за края контейнера. */
export function clampView(view: View, box: Box, minScale = 1, maxScale = 8): View {
  const scale = Math.min(maxScale, Math.max(minScale, view.scale))
  const x = Math.min(0, Math.max(box.width * (1 - scale), view.x))
  const y = Math.min(0, Math.max(box.height * (1 - scale), view.y))
  return { scale, x, y }
}

/** Зум к точке: контент под point остаётся на месте. */
export function zoomAt(view: View, factor: number, point: Point, box: Box): View {
  const scale = view.scale * factor
  // координата контента под курсором до зума
  const contentX = (point.x - view.x) / view.scale
  const contentY = (point.y - view.y) / view.scale
  return clampView({ scale, x: point.x - contentX * scale, y: point.y - contentY * scale }, box)
}

export function useZoomPan() {
  const [view, setView] = useState<View>(INITIAL)
  const containerRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(
    null,
  )

  // размер и локальные координаты берём в момент события
  const readBox = (): { box: Box; left: number; top: number } => {
    const rect = containerRef.current?.getBoundingClientRect()
    return {
      box: { width: rect?.width ?? 0, height: rect?.height ?? 0 },
      left: rect?.left ?? 0,
      top: rect?.top ?? 0,
    }
  }

  const zoomBy = (factor: number, point: Point | null) => {
    const { box } = readBox()
    const target = point ?? { x: box.width / 2, y: box.height / 2 }
    setView((v) => zoomAt(v, factor, target, box))
  }

  const onWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    const { box, left, top } = readBox()
    const point = { x: e.clientX - left, y: e.clientY - top }
    const factor = e.deltaY < 0 ? WHEEL_FACTOR : 1 / WHEEL_FACTOR
    setView((v) => zoomAt(v, factor, point, box))
  }

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    // перетаскивание имеет смысл только при увеличении
    if (view.scale <= 1) return
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: view.x, origY: view.y }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag) return
    const { box } = readBox()
    const dx = e.clientX - drag.startX
    const dy = e.clientY - drag.startY
    setView((v) => clampView({ scale: v.scale, x: drag.origX + dx, y: drag.origY + dy }, box))
  }

  const onPointerUp = () => {
    dragRef.current = null
  }

  const reset = () => setView(INITIAL)

  return {
    view,
    containerRef,
    handlers: {
      onWheel,
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onDoubleClick: reset,
    },
    zoomIn: () => zoomBy(BUTTON_FACTOR, null),
    zoomOut: () => zoomBy(1 / BUTTON_FACTOR, null),
    reset,
    isZoomed: view.scale > 1,
  }
}
