import type { Site } from '@/api/schemas'
import { formatDate } from '@/lib/format'

/** «данные на 18.09.2026» — по последнему кадру стройки. */
export function dataAsOf(site: Site): string | null {
  const last = site.summary?.last_frame_at
  return last ? `данные на ${formatDate(last)}` : null
}

/** «Березники, [адрес объекта] · данные на 18.09.2026» */
export function siteSubtitle(site: Site): string {
  return [site.address, dataAsOf(site)].filter(Boolean).join(' · ')
}
