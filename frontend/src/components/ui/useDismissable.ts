import { useEffect, type RefObject } from 'react'

/**
 * Поведение всплывающей поверхности: Escape закрывает, фокус уходит внутрь и
 * возвращается на прежний элемент при размонтировании. Общее для Dialog и Drawer.
 */
export function useDismissable(onClose: () => void, ref: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    ref.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previous?.focus()
    }
  }, [onClose, ref])
}
