/** Снимки (домен photo) и наблюдения за дату (домен observation). */
import {
  keepPreviousData,
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { z } from 'zod'
import { env } from '@/lib/env'
import { request } from './client'
import { keys } from './keys'
import type { ProcessingStatus } from './schemas'
import {
  detectBacklogReportSchema,
  observationSchema,
  photoDetailSchema,
  photoSchema,
  uploadReportSchema,
} from './schemas'

export const framesApi = {
  observations: (siteId: string) =>
    request(`/sites/${siteId}/observations`, { schema: z.array(observationSchema) }),
  observation: (siteId: string, date: string) =>
    request(`/sites/${siteId}/observations/${date}`, { schema: observationSchema }),
  /** Снимок с рамками распознавания (детекциями). */
  photo: (siteId: string, photoId: string) =>
    request(`/sites/${siteId}/photos/${photoId}`, { schema: photoDetailSchema }),
  /** Все снимки стройки; `undated` — только снимки без даты. */
  photos: (siteId: string, undated = false) =>
    request(`/sites/${siteId}/photos`, {
      query: { undated: undated || undefined },
      schema: z.array(photoSchema),
    }),
  /** Пачка снимков (multipart `files`); ошибка одного файла не прерывает остальные. */
  upload: (siteId: string, files: readonly File[], cameraId: string | null = null) => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    if (cameraId) form.append('camera_id', cameraId)
    return request(`/sites/${siteId}/photos`, {
      method: 'POST',
      body: form,
      schema: uploadReportSchema,
    })
  },
  setDate: (siteId: string, photoId: string, capturedOn: string) =>
    request(`/sites/${siteId}/photos/${photoId}/date`, {
      method: 'PATCH',
      body: { captured_on: capturedOn },
      schema: photoSchema,
    }),
  redetect: (siteId: string, photoId: string) =>
    request(`/sites/${siteId}/photos/${photoId}/detect`, {
      method: 'POST',
      schema: photoDetailSchema,
    }),
  /** Распознавание необработанных снимков; statuses — фильтр по processing_status. */
  detectBacklog: (siteId: string, statuses?: ProcessingStatus[]) =>
    request(`/sites/${siteId}/photos/detect`, {
      method: 'POST',
      query: statuses && statuses.length > 0 ? { status: statuses.join(',') } : undefined,
      schema: detectBacklogReportSchema,
    }),
}

/** Исходный снимок без рамок (`/image`): подложка для рисования рабочей зоны камеры. */
export function photoImageUrl(siteId: string, photoId: string): string {
  return `${env.apiBaseUrl}/sites/${siteId}/photos/${photoId}/image`
}

/** Исходный снимок без рамок (`/image`) для просмотра с наложенными рамками в браузере. */
export function originalImageUrl(siteId: string, photoId: string): string {
  return `${env.apiBaseUrl}/sites/${siteId}/photos/${photoId}/image`
}

/** Снимок с рамками найденной техники: JPEG рисует и кэширует сервер (`/annotated`). */
export function annotatedImageUrl(siteId: string, photoId: string): string {
  return `${env.apiBaseUrl}/sites/${siteId}/photos/${photoId}/annotated`
}

export function useObservations(siteId: string) {
  return useQuery({
    queryKey: keys.observations(siteId),
    queryFn: () => framesApi.observations(siteId),
  })
}

/** Наблюдение за день; пока грузится другой день, виден прежний (приглушённым на экране). */
export function useObservation(siteId: string, date: string | null) {
  return useQuery(observationQuery(siteId, date))
}

export function observationQuery(siteId: string, date: string | null) {
  return queryOptions({
    queryKey: keys.observation(siteId, date ?? ''),
    queryFn: () => framesApi.observation(siteId, date!),
    enabled: Boolean(date),
    placeholderData: keepPreviousData,
  })
}

export function usePhoto(siteId: string, photoId: string | null) {
  return useQuery({
    queryKey: keys.photo(siteId, photoId ?? ''),
    queryFn: () => framesApi.photo(siteId, photoId!),
    enabled: Boolean(photoId),
  })
}

export function usePhotos(siteId: string) {
  return useQuery({ queryKey: keys.photos(siteId), queryFn: () => framesApi.photos(siteId) })
}

export function useUndatedPhotos(siteId: string) {
  return useQuery({
    queryKey: keys.undatedPhotos(siteId),
    queryFn: () => framesApi.photos(siteId, true),
  })
}

/** Любая правка входа (дата снимка, новые снимки) пересчитывает стройку — сбрасываем её кэш. */
function useSiteMutation<TArgs, TResult>(siteId: string, fn: (args: TArgs) => Promise<TResult>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.site(siteId) }),
  })
}

export function useUploadPhotos(siteId: string) {
  return useSiteMutation(
    siteId,
    ({ files, cameraId }: { files: readonly File[]; cameraId: string | null }) =>
      framesApi.upload(siteId, files, cameraId),
  )
}

export function useSetPhotoDate(siteId: string) {
  return useSiteMutation(
    siteId,
    ({ photoId, capturedOn }: { photoId: string; capturedOn: string }) =>
      framesApi.setDate(siteId, photoId, capturedOn),
  )
}

export function useRedetectPhoto(siteId: string) {
  return useSiteMutation(siteId, (photoId: string) => framesApi.redetect(siteId, photoId))
}

export function useDetectBacklog(siteId: string) {
  return useSiteMutation(siteId, (statuses?: ProcessingStatus[]) =>
    framesApi.detectBacklog(siteId, statuses),
  )
}
