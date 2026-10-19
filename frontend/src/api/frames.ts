/** Снимки (домен photo) и наблюдения за дату (домен observation). */
import {
  keepPreviousData,
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { z } from 'zod'
import { env } from '@/lib/env'
import { request } from './client'
import { keys } from './keys'
import type { ProcessingStatus, UploadReport } from './schemas'
import {
  detectBacklogReportSchema,
  observationSchema,
  photoDetailSchema,
  photoSchema,
  queueProgressSchema,
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
  /** Сколько снимков объекта ещё в фоновой обработке. */
  queue: (siteId: string) =>
    request(`/sites/${siteId}/photos/progress`, { schema: queueProgressSchema }),
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

/** Миниатюра для ленты: меньше, только рамки, без подписей (`?thumb=true`). */
export function annotatedThumbUrl(siteId: string, photoId: string): string {
  return `${annotatedImageUrl(siteId, photoId)}?thumb=true`
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

// Зеркалят StorageSettings бэкенда: одна пачка запроса — не больше 50 файлов и 200 МБ
export const MAX_BATCH_FILES = 50
export const MAX_BATCH_BYTES = 200 * 1024 * 1024

/** Выбор инженера — пачками по лимитам бэкенда, порядок файлов сохраняется. */
export function chunkFiles(files: readonly File[]): File[][] {
  const chunks: File[][] = []
  let current: File[] = []
  let bytes = 0
  for (const file of files) {
    if (
      current.length &&
      (current.length >= MAX_BATCH_FILES || bytes + file.size > MAX_BATCH_BYTES)
    ) {
      chunks.push(current)
      current = []
      bytes = 0
    }
    current.push(file)
    bytes += file.size
  }
  if (current.length) chunks.push(current)
  return chunks
}

interface UploadArgs {
  files: readonly File[]
  cameraId: string | null
  /** Сколько файлов уже отправлено — для «Отправлено 150 из 904». */
  onProgress?: (sent: number) => void
}

/**
 * Загрузка любого числа снимков: пачками по лимитам бэкенда, по очереди. Сервер только
 * принимает файлы, дату и технику ставит фоновая обработка — её прогресс показывает
 * `usePhotoQueue`. Итог — общий отчёт по всем пачкам.
 */
export function useUploadPhotos(siteId: string) {
  const qc = useQueryClient()
  return useSiteMutation(siteId, async ({ files, cameraId, onProgress }: UploadArgs) => {
    const report: UploadReport = { items: [], uploaded: 0, failed: 0 }
    let sent = 0
    for (const chunk of chunkFiles(files)) {
      const part = await framesApi.upload(siteId, chunk, cameraId)
      report.items.push(...part.items)
      report.uploaded += part.uploaded
      report.failed += part.failed
      sent += chunk.length
      onProgress?.(sent)
      // Очередь пошла — экран «Наблюдения» начинает показывать прогресс сразу
      void qc.invalidateQueries({ queryKey: keys.photoQueue(siteId) })
    }
    return report
  })
}

/**
 * Фоновая обработка снимков объекта: опрос раз в 2 с, пока очередь не пуста. Когда она
 * опустела, обновляется всё по объекту — даты, наблюдения и статусы этапов уже пересчитаны.
 */
export function usePhotoQueue(siteId: string) {
  const qc = useQueryClient()
  const wasActive = useRef(false)
  const query = useQuery({
    queryKey: keys.photoQueue(siteId),
    queryFn: () => framesApi.queue(siteId),
    refetchInterval: (q) =>
      q.state.data && q.state.data.queued + q.state.data.processing > 0 ? 2000 : false,
  })
  const left = query.data ? query.data.queued + query.data.processing : 0
  useEffect(() => {
    if (left > 0) wasActive.current = true
    else if (wasActive.current) {
      wasActive.current = false
      void qc.invalidateQueries({ queryKey: keys.site(siteId) })
    }
  }, [left, qc, siteId])
  return { left }
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
