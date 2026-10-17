import { useEffect, useState } from 'react'
import { getToken } from '@/lib/authStorage'

/**
 * Снимки закрыты авторизацией, а CSS `url()` и `<img>` не умеют слать заголовок `Authorization`.
 * Поэтому картинку забираем запросом с токеном и показываем из памяти (`blob:`).
 * Свежесть держит HTTP-кэш браузера: `/annotated` отдаётся с ETag, повторный показ — это 304.
 * Возвращает `null`, пока картинка грузится или если её не удалось получить.
 */
export function useAuthorizedImage(url: string | null): string | null {
  const [loaded, setLoaded] = useState<{ url: string; src: string } | null>(null)

  useEffect(() => {
    if (!url) return undefined
    let src: string | null = null
    let alive = true
    const token = getToken()
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(async (response) => {
        if (!response.ok) return
        const blob = await response.blob()
        src = URL.createObjectURL(blob)
        if (alive) setLoaded({ url, src })
        else URL.revokeObjectURL(src)
      })
      .catch(() => undefined)
    return () => {
      alive = false
      if (src) URL.revokeObjectURL(src)
    }
  }, [url])

  return url && loaded?.url === url ? loaded.src : null
}
