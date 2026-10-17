import { useEffect, useState, type RefObject } from 'react'

/** `true`, когда элемент прокручен вверх за край экрана (не «ещё ниже», а уже пройден). */
export function useScrolledPast(target: RefObject<Element | null>): boolean {
  const [past, setPast] = useState(false)
  useEffect(() => {
    const node = target.current
    if (!node || typeof IntersectionObserver === 'undefined') return undefined
    const observer = new IntersectionObserver(([entry]) => {
      if (entry) setPast(!entry.isIntersecting && entry.boundingClientRect.top < 0)
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [target])
  return past
}
