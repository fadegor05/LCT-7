import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, request } from './client'
import { keys } from './keys'
import { scheduleReportSchema, stageSchema, type StageDatesUpdate } from './schemas'

export const scheduleApi = {
  /** Отчёт о загруженном графике с этапами; 404 — графика ещё нет. */
  get: async (siteId: string) => {
    try {
      return await request(`/sites/${siteId}/schedule`, { schema: scheduleReportSchema })
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null
      throw error
    }
  },
  /** Импорт CSV/XLSX (multipart `file`); переимпорт заменяет график целиком. */
  upload: (siteId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request(`/sites/${siteId}/schedule/import`, {
      method: 'POST',
      body: form,
      schema: scheduleReportSchema,
    })
  },
  updateStage: (siteId: string, stageId: string, data: StageDatesUpdate) =>
    request(`/sites/${siteId}/schedule/stages/${stageId}`, {
      method: 'PATCH',
      body: data,
      schema: stageSchema,
    }),
}

export function useSchedule(siteId: string | undefined) {
  return useQuery({
    queryKey: keys.schedule(siteId ?? ''),
    queryFn: () => scheduleApi.get(siteId!),
    enabled: Boolean(siteId),
  })
}

/** График — вход для методики и оценки: после его правки сбрасывается кэш всей стройки. */
export function useUploadSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ siteId, file }: { siteId: string; file: File }) =>
      scheduleApi.upload(siteId, file),
    onSuccess: async (data, { siteId }) => {
      qc.setQueryData(keys.schedule(siteId), data)
      await qc.invalidateQueries({ queryKey: keys.site(siteId) })
    },
  })
}

export function useUpdateStageDates(siteId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ stageId, data }: { stageId: string; data: StageDatesUpdate }) =>
      scheduleApi.updateStage(siteId, stageId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.site(siteId) }),
  })
}
