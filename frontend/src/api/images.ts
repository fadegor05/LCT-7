import { useEffect, useState } from 'react'
import { getToken } from '@/lib/authStorage'

// Сколько снимков держать в памяти: ленты «Все дни» — сотни кадров, старые вытесняются
const MAX_CACHED = 300

// Загруженные снимки по адресу: повторный показ (переход между вкладками, возврат к дню)
// берёт картинку отсюда сразу, а не мигает пустой подложкой, пока идёт запрос
const loaded = new Map<string, string>()
const pending = new Map<string, Promise<string | null>>()

function remember(url: string, src: string): void {
  loaded.delete(url)
  loaded.set(url, src)
  while (loaded.size > MAX_CACHED) {
    const [oldest, old] = loaded.entries().next().value as [string, string]
    loaded.delete(oldest)
    URL.revokeObjectURL(old)
  }
}

function load(url: string): Promise<string | null> {
  const inflight = pending.get(url)
  if (inflight) return inflight
  const token = getToken()
  const request = fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    .then(async (response) => {
      if (!response.ok) return null
      const src = URL.createObjectURL(await response.blob())
      remember(url, src)
      return src
    })
    .catch(() => null)
    .finally(() => pending.delete(url))
  pending.set(url, request)
  return request
}

/** Забыть загруженные снимки: при выходе — следующий пользователь их видеть не должен. */
export function clearImageCache(): void {
  loaded.forEach((src) => URL.revokeObjectURL(src))
  loaded.clear()
  pending.clear()
}

/**
 * Снимки закрыты авторизацией, а CSS `url()` и `<img>` не умеют слать заголовок `Authorization`.
 * Поэтому картинку забираем запросом с токеном и показываем из памяти (`blob:`). Загруженная
 * картинка остаётся в памяти: уже виденный снимок показывается сразу.
 * Возвращает `null`, пока картинка грузится или если её не удалось получить.
 */
export function useAuthorizedImage(url: string | null): string | null {
  const [state, setState] = useState<{ url: string; src: string } | null>(() => {
    const src = url ? loaded.get(url) : undefined
    return url && src ? { url, src } : null
  })

  useEffect(() => {
    // Уже в памяти — рендер берёт его сам (ниже), запрос не нужен
    if (!url || loaded.has(url)) return undefined
    let alive = true
    void load(url).then((src) => {
      if (alive && src) setState({ url, src })
    })
    return () => {
      alive = false
    }
  }, [url])

  if (!url) return null
  if (state?.url === url) return state.src
  return loaded.get(url) ?? null
}
