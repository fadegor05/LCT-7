import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { request } from './client'
import { keys } from './keys'
import { equipmentClassSchema, stageKitSchema, type StageKitUpdate } from './schemas'

export const methodologyApi = {
  list: (siteId: string) =>
    request(`/sites/${siteId}/methodology`, { schema: z.array(stageKitSchema) }),
  update: (siteId: string, stageId: string, data: StageKitUpdate) =>
    request(`/sites/${siteId}/methodology/${stageId}`, {
      method: 'PUT',
      body: data,
      schema: stageKitSchema,
    }),
  equipmentClasses: () => request('/equipment-classes', { schema: z.array(equipmentClassSchema) }),
}

export function useMethodology(siteId: string) {
  return useQuery({
    queryKey: keys.methodology(siteId),
    queryFn: () => methodologyApi.list(siteId),
  })
}

export function useEquipmentClasses() {
  return useQuery({
    queryKey: keys.equipmentClasses,
    queryFn: methodologyApi.equipmentClasses,
    staleTime: Infinity,
  })
}

export function useUpdateStageKit(siteId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ stageId, data }: { stageId: string; data: StageKitUpdate }) =>
      methodologyApi.update(siteId, stageId, data),
    // Правка методики пересчитывает выводы стройки: сбрасываем всё по ней.
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.site(siteId) }),
  })
}
