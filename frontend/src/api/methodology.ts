import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { request } from './client'
import { keys } from './keys'
import {
  applyDefaultsResultSchema,
  equipmentSetSchema,
  equipmentTypeSchema,
  ruleSchema,
  type RuleUpdate,
  type SetWrite,
} from './schemas'

export const methodologyApi = {
  /** Правила по этапам графика; сервер лениво создаёт их из базового набора. 404 — нет графика. */
  list: (siteId: string) =>
    request(`/sites/${siteId}/methodology`, { schema: z.array(ruleSchema) }),
  updateRule: (siteId: string, ruleId: string, data: RuleUpdate) =>
    request(`/sites/${siteId}/methodology/rules/${ruleId}`, {
      method: 'PATCH',
      body: data,
      schema: ruleSchema,
    }),
  createSet: (siteId: string, ruleId: string, data: SetWrite) =>
    request(`/sites/${siteId}/methodology/rules/${ruleId}/sets`, {
      method: 'POST',
      body: data,
      schema: equipmentSetSchema,
    }),
  replaceSet: (siteId: string, setId: string, data: SetWrite) =>
    request(`/sites/${siteId}/methodology/sets/${setId}`, {
      method: 'PUT',
      body: data,
      schema: equipmentSetSchema,
    }),
  deleteSet: (siteId: string, setId: string) =>
    request(`/sites/${siteId}/methodology/sets/${setId}`, { method: 'DELETE' }),
  equipmentTypes: () => request('/equipment-types', { schema: z.array(equipmentTypeSchema) }),
  applyDefaults: (siteId: string) =>
    request(`/sites/${siteId}/methodology/apply-defaults`, {
      method: 'POST',
      schema: applyDefaultsResultSchema,
    }),
}

export function useMethodology(siteId: string) {
  return useQuery({
    queryKey: keys.methodology(siteId),
    queryFn: () => methodologyApi.list(siteId),
  })
}

export function useEquipmentTypes() {
  return useQuery({
    queryKey: keys.equipmentTypes,
    queryFn: methodologyApi.equipmentTypes,
    staleTime: Infinity,
  })
}

/** Правка методики пересчитывает выводы стройки: сбрасываем всё по ней. */
function useMethodologyMutation<TArgs, TResult>(
  siteId: string,
  fn: (args: TArgs) => Promise<TResult>,
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.site(siteId) }),
  })
}

export function useUpdateRule(siteId: string) {
  return useMethodologyMutation(siteId, ({ ruleId, data }: { ruleId: string; data: RuleUpdate }) =>
    methodologyApi.updateRule(siteId, ruleId, data),
  )
}

export function useCreateSet(siteId: string) {
  return useMethodologyMutation(siteId, ({ ruleId, data }: { ruleId: string; data: SetWrite }) =>
    methodologyApi.createSet(siteId, ruleId, data),
  )
}

export function useReplaceSet(siteId: string) {
  return useMethodologyMutation(siteId, ({ setId, data }: { setId: string; data: SetWrite }) =>
    methodologyApi.replaceSet(siteId, setId, data),
  )
}

export function useDeleteSet(siteId: string) {
  return useMethodologyMutation(siteId, (setId: string) => methodologyApi.deleteSet(siteId, setId))
}

export function useApplyDefaults(siteId: string) {
  return useMethodologyMutation(siteId, () => methodologyApi.applyDefaults(siteId))
}
