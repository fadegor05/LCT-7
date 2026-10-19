import type { Site } from '@/api/schemas'

/** Подзаголовок экранов объекта: адрес и дата данных («данные на 18.09.2026», clean-mvp). */
export function siteSubtitle(site: Site, asOf?: string | null): string | undefined {
  const parts = [site.address, asOf && `данные на ${asOf.split('-').reverse().join('.')}`]
  return parts.filter(Boolean).join(' · ') || undefined
}
