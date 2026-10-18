import type { Photo } from '@/api/schemas'

/** Последний загруженный снимок стройки: подложка для рисования зоны, если кадров камеры нет. */
export function newestPhoto(photos: Photo[] | undefined): Photo | undefined {
  return photos?.reduce<Photo | undefined>(
    (best, photo) => (!best || photo.uploaded_at > best.uploaded_at ? photo : best),
    undefined,
  )
}
