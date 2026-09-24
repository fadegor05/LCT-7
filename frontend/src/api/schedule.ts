import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { ApiError, request } from './client'
import { keys } from './keys'
import { scheduleImportSchema, stageSchema, type StageUpdate } from './schemas'

export const scheduleApi = {
  /** Текущая загрузка графика; 404 — графика ещё нет. */
  current: async (siteId: string) => {
    try {
      return await request(`/sites/${siteId}/schedule-imports/current`, {
        schema: scheduleImportSchema,
      })
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null
      throw error
    }
  },
  upload: (siteId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request(`/sites/${siteId}/schedule-imports`, {
      method: 'POST',
      body: form,
      schema: scheduleImportSchema,
    })
  },
  stages: (siteId: string) => request(`/sites/${siteId}/stages`, { schema: z.array(stageSchema) }),
  updateStage: (siteId: string, stageId: string, data: StageUpdate) =>
    request(`/sites/${siteId}/stages/${stageId}`, {
      method: 'PATCH',
      body: data,
      schema: stageSchema,
    }),
}

export function useScheduleImport(siteId: string | undefined) {
  return useQuery({
    queryKey: keys.scheduleImport(siteId ?? ''),
    queryFn: () => scheduleApi.current(siteId!),
    enabled: Boolean(siteId),
  })
}

export function useStages(siteId: string | undefined) {
  return useQuery({
    queryKey: keys.stages(siteId ?? ''),
    queryFn: () => scheduleApi.stages(siteId!),
    enabled: Boolean(siteId),
  })
}

export function useUploadSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ siteId, file }: { siteId: string; file: File }) =>
      scheduleApi.upload(siteId, file),
    onSuccess: async (data, { siteId }) => {
      qc.setQueryData(keys.scheduleImport(siteId), data)
      await qc.invalidateQueries({ queryKey: keys.stages(siteId) })
    },
  })
}

export function useUpdateStage(siteId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ stageId, data }: { stageId: string; data: StageUpdate }) =>
      scheduleApi.updateStage(siteId, stageId, data),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: keys.stages(siteId) }),
        qc.invalidateQueries({ queryKey: keys.scheduleImport(siteId) }),
      ])
    },
  })
}
