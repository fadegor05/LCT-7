import { useSyncExternalStore } from 'react'

/** Подписка на медиазапрос. Где `matchMedia` нет (тесты, SSR), считаем, что запрос выполнен. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      const list = window.matchMedia?.(query)
      list?.addEventListener?.('change', notify)
      return () => list?.removeEventListener?.('change', notify)
    },
    () => window.matchMedia?.(query).matches ?? true,
    () => true,
  )
}
