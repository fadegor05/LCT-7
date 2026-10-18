/** Камеры объекта (домен camera): список, создание, правка и удаление; зона — в долях кадра. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { request } from './client'
import { keys } from './keys'
import { cameraSchema, type Zone } from './schemas'

export interface CameraInput {
  name: string
  stream_url: string | null
  capture_every_s: number | null
  zone: Zone | null
}

export function useCameras(siteId: string) {
  return useQuery({
    queryKey: keys.cameras(siteId),
    queryFn: ({ signal }) =>
      request(`/sites/${siteId}/cameras`, { schema: z.array(cameraSchema), signal }),
  })
}

/** Создать камеру (`cameraId` не задан) или поправить существующую. */
export function useSaveCamera(siteId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ cameraId, data }: { cameraId: string | null; data: CameraInput }) =>
      cameraId
        ? request(`/sites/${siteId}/cameras/${cameraId}`, {
            method: 'PATCH',
            body: data,
            schema: cameraSchema,
          })
        : request(`/sites/${siteId}/cameras`, { method: 'POST', body: data, schema: cameraSchema }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.site(siteId) }),
  })
}

export function useDeleteCamera(siteId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (cameraId: string) =>
      request(`/sites/${siteId}/cameras/${cameraId}`, { method: 'DELETE' }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.site(siteId) }),
  })
}
