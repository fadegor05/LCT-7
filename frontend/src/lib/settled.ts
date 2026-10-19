/** Состояние запроса, по которому решаем, готов ли экран. */
interface QueryLike {
  isPending: boolean
  fetchStatus?: 'fetching' | 'paused' | 'idle'
}

/**
 * Готовы ли данные экрана: все запросы ответили (выключенный запрос — тоже «готов»).
 * Экран показывается целиком, когда готово всё (как в clean-mvp): блоки, приходящие
 * своими запросами по очереди, иначе сдвигают друг друга.
 */
export function settled(...queries: readonly QueryLike[]): boolean {
  return queries.every((q) => !q.isPending || q.fetchStatus === 'idle')
}
