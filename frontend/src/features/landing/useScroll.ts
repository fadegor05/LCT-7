import { useEffect, useRef, useState, type RefObject } from 'react'

/** Система просит уменьшить движение. */
export function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

/**
 * Прогресс прокрутки секции от 0 до 1: 0, пока верх секции у верха окна, 1, когда её низ достиг низа окна.
 * Секция выше экрана: внутри неё лежит закреплённая сцена.
 */
export function useScrollProgress(target: RefObject<HTMLElement | null>, enabled: boolean): number {
  const [progress, setProgress] = useState(0)
  const frame = useRef(0)

  useEffect(() => {
    const node = target.current
    if (!enabled || !node) return undefined
    const update = () => {
      frame.current = 0
      const rect = node.getBoundingClientRect()
      const span = rect.height - window.innerHeight
      const value = span > 0 ? Math.min(1, Math.max(0, -rect.top / span)) : 0
      setProgress((prev) => (Math.abs(prev - value) > 0.001 ? value : prev))
    }
    const schedule = () => {
      if (!frame.current) frame.current = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    return () => {
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      if (frame.current) cancelAnimationFrame(frame.current)
    }
  }, [target, enabled])

  return progress
}

/** `true`, когда элемент вошёл в окно. Без IntersectionObserver и при «меньше движения» сразу `true`. */
export function useInView(target: RefObject<Element | null>): boolean {
  const unsupported = typeof IntersectionObserver === 'undefined'
  const [seen, setSeen] = useState(false)

  useEffect(() => {
    const node = target.current
    if (unsupported || !node || prefersReducedMotion()) return undefined
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setSeen(true)
          observer.disconnect()
        }
      },
      { threshold: 0, rootMargin: '0px 0px -10% 0px' },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [target, unsupported])

  return unsupported || seen || prefersReducedMotion()
}
