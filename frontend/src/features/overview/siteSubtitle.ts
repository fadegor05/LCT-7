import type { Site } from '@/api/schemas'

/** Подзаголовок экранов объекта: адрес или обозначение стройки. */
export function siteSubtitle(site: Site): string | undefined {
  return site.address ?? undefined
}
