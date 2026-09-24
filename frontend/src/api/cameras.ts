import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { request } from './client'
import { keys } from './keys'
import { cameraSchema, referenceFrameSchema, type CameraInput } from './schemas'

export const camerasApi = {
  list: (siteId: string) => request(`/sites/${siteId}/cameras`, { schema: z.array(cameraSchema) }),
  create: (siteId: string, data: CameraInput) =>
    request(`/sites/${siteId}/cameras`, { method: 'POST', body: data, schema: cameraSchema }),
  update: (cameraId: string, data: CameraInput) =>
    request(`/cameras/${cameraId}`, { method: 'PATCH', body: data, schema: cameraSchema }),
  /** Один кадр со стрима для рисования зоны. Кадр не сохраняется. */
  referenceFrame: (streamUrl: string) =>
    request('/reference-frames', {
      method: 'POST',
      body: { stream_url: streamUrl },
      schema: referenceFrameSchema,
    }),
}

export function useCameras(siteId: string) {
  return useQuery({ queryKey: keys.cameras(siteId), queryFn: () => camerasApi.list(siteId) })
}

export function useSaveCamera(siteId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ cameraId, data }: { cameraId: string | null; data: CameraInput }) =>
      cameraId ? camerasApi.update(cameraId, data) : camerasApi.create(siteId, data),
    // Зона влияет на активность техники — пересчёт выводов по стройке.
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.site(siteId) }),
  })
}

export function useReferenceFrame() {
  return useMutation({ mutationFn: camerasApi.referenceFrame })
}
