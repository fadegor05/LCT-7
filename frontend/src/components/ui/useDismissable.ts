import { useEffect, useRef, type RefObject } from 'react'

/**
 * Поведение всплывающей поверхности: Escape закрывает, фокус уходит внутрь и
 * возвращается на прежний элемент при размонтировании. Общее для Dialog и Drawer.
 */
export function useDismissable(onClose: () => void, ref: RefObject<HTMLElement | null>): void {
  // Свежий onClose без перезапуска эффекта: иначе каждый перерендер родителя с новой
  // стрелочной функцией снова уводит фокус на окно и выдёргивает курсор из поля ввода
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    ref.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCloseRef.current()
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previous?.focus()
    }
  }, [ref])
}
