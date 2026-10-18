import { useEffect, type RefObject } from 'react'

/** Насколько сдвигается слой глубины 1 при курсоре у края экрана, px. */
const PARALLAX_X = 18
const PARALLAX_Y = 12

/**
 * Параллакс от курсора: слои с `data-depth` внутри `root` смещаются в противоположную сторону,
 * чем глубже слой, тем сильнее. Только мышь и без «уменьшить движение».
 */
export function useCursorParallax(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const media = (q: string) => window.matchMedia?.(q).matches ?? false
    if (!media('(pointer: fine)') || media('(prefers-reduced-motion: reduce)')) return undefined
    const target = { x: 0, y: 0 }
    const current = { x: 0, y: 0 }
    let raf = 0
    const tick = () => {
      current.x += (target.x - current.x) * 0.08
      current.y += (target.y - current.y) * 0.08
      const layers = root.current?.querySelectorAll<HTMLElement>('[data-depth]') ?? []
      for (const layer of layers) {
        const depth = Number(layer.dataset.depth)
        const x = (-current.x * depth * PARALLAX_X).toFixed(2)
        const y = (-current.y * depth * PARALLAX_Y).toFixed(2)
        layer.style.transform = `translate3d(${x}px, ${y}px, 0)`
      }
      const settled = Math.abs(target.x - current.x) + Math.abs(target.y - current.y) < 0.002
      raf = settled ? 0 : requestAnimationFrame(tick)
    }
    const onMove = (e: PointerEvent) => {
      target.x = (e.clientX / window.innerWidth) * 2 - 1
      target.y = (e.clientY / window.innerHeight) * 2 - 1
      if (!raf) raf = requestAnimationFrame(tick)
    }
    window.addEventListener('pointermove', onMove)
    return () => {
      window.removeEventListener('pointermove', onMove)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [root])
}
