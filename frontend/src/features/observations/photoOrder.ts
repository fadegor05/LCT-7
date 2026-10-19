import type { Photo } from '@/api/schemas'

/** Кадры слева направо по времени съёмки: дата, затем время (кадры без времени — в начале дня). */
export function byShotTime(a: Photo, b: Photo): number {
  const key = (p: Photo) => p.captured_at ?? p.captured_on ?? ''
  return key(a).localeCompare(key(b))
}
