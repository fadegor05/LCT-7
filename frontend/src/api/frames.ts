import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { request } from './client'
import { keys } from './keys'
import {
  frameSchema,
  ingestSchema,
  needsReviewSchema,
  observationDaySchema,
  observationSchema,
  type SourceType,
} from './schemas'

export interface IngestInput {
  source_type: SourceType
  camera_id: string
  files: File[]
  slice_step_sec?: number
  clip_started_at?: string | null
}

export const framesApi = {
  observationDays: (siteId: string) =>
    request(`/sites/${siteId}/observations`, { schema: z.array(observationDaySchema) }),
  observation: (siteId: string, date: string) =>
    request(`/sites/${siteId}/observations/${date}`, { schema: observationSchema }),
  frames: (siteId: string, date: string | null) =>
    request(`/sites/${siteId}/frames`, { query: { date }, schema: z.array(frameSchema) }),
  needsReview: (siteId: string) =>
    request(`/sites/${siteId}/frames/needs-review`, { schema: needsReviewSchema }),
  confirmFrameTime: (frameId: string, capturedAt: string) =>
    request(`/frames/${frameId}`, {
      method: 'PATCH',
      body: { captured_at: capturedAt },
      schema: frameSchema,
    }),
  setClipStart: (ingestId: string, clipStartedAt: string) =>
    request(`/ingests/${ingestId}`, {
      method: 'PATCH',
      body: { clip_started_at: clipStartedAt },
      schema: ingestSchema,
    }),
  createIngest: (siteId: string, input: IngestInput) => {
    const form = new FormData()
    form.append('source_type', input.source_type)
    form.append('camera_id', input.camera_id)
    if (input.slice_step_sec) form.append('slice_step_sec', String(input.slice_step_sec))
    if (input.clip_started_at) form.append('clip_started_at', input.clip_started_at)
    input.files.forEach((file) => form.append('files', file))
    return request(`/sites/${siteId}/ingests`, { method: 'POST', body: form, schema: ingestSchema })
  },
  streams: (siteId: string) =>
    request(`/sites/${siteId}/ingests`, {
      query: { source_type: 'stream' },
      schema: z.array(ingestSchema),
    }),
  stopIngest: (ingestId: string) =>
    request(`/ingests/${ingestId}/stop`, { method: 'POST', schema: ingestSchema }),
}

export function useObservationDays(siteId: string) {
  return useQuery({
    queryKey: keys.observationDays(siteId),
    queryFn: () => framesApi.observationDays(siteId),
  })
}

export function useObservation(siteId: string, date: string | null) {
  return useQuery({
    queryKey: keys.observation(siteId, date ?? ''),
    queryFn: () => framesApi.observation(siteId, date!),
    enabled: Boolean(date),
  })
}

export function useFrames(siteId: string, date: string | null) {
  return useQuery({
    queryKey: keys.frames(siteId, date),
    queryFn: () => framesApi.frames(siteId, date),
  })
}

export function useNeedsReview(siteId: string) {
  return useQuery({
    queryKey: keys.needsReview(siteId),
    queryFn: () => framesApi.needsReview(siteId),
  })
}

export function useStreams(siteId: string) {
  return useQuery({ queryKey: keys.streams(siteId), queryFn: () => framesApi.streams(siteId) })
}

/** Любая правка входа (время кадра, новые кадры) пересчитывает стройку — сбрасываем её кэш. */
function useSiteMutation<TArgs, TResult>(siteId: string, fn: (args: TArgs) => Promise<TResult>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.site(siteId) }),
  })
}

export function useConfirmFrameTime(siteId: string) {
  return useSiteMutation(
    siteId,
    ({ frameId, capturedAt }: { frameId: string; capturedAt: string }) =>
      framesApi.confirmFrameTime(frameId, capturedAt),
  )
}

export function useSetClipStart(siteId: string) {
  return useSiteMutation(
    siteId,
    ({ ingestId, clipStartedAt }: { ingestId: string; clipStartedAt: string }) =>
      framesApi.setClipStart(ingestId, clipStartedAt),
  )
}

export function useCreateIngest(siteId: string) {
  return useSiteMutation(siteId, (input: IngestInput) => framesApi.createIngest(siteId, input))
}

export function useStopIngest(siteId: string) {
  return useSiteMutation(siteId, (ingestId: string) => framesApi.stopIngest(ingestId))
}
