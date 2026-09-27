import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { request } from './client'
import { keys } from './keys'
import {
  decisionRecordSchema,
  deviationListItemSchema,
  deviationSchema,
  stageStatusSchema,
  type DecisionInput,
} from './schemas'

export const deviationsApi = {
  all: () => request('/deviations', { schema: z.array(deviationListItemSchema) }),
  bySite: (siteId: string) =>
    request(`/sites/${siteId}/deviations`, { schema: z.array(deviationListItemSchema) }),
  get: (id: string) => request(`/deviations/${id}`, { schema: deviationSchema }),
  stageStatuses: (siteId: string) =>
    request(`/sites/${siteId}/stage-statuses`, { schema: z.array(stageStatusSchema) }),
  decide: (id: string, data: DecisionInput) =>
    request(`/deviations/${id}/decision`, {
      method: 'POST',
      body: data,
      schema: decisionRecordSchema,
    }),
  /** «Изменить решение»: текущее решение закрывается, история на сервере сохраняется. */
  undoDecision: (id: string) => request(`/deviations/${id}/decision`, { method: 'DELETE' }),
}

export function useAllDeviations() {
  return useQuery({ queryKey: keys.allDeviations, queryFn: deviationsApi.all })
}

export function useSiteDeviations(siteId: string) {
  return useQuery({
    queryKey: keys.siteDeviations(siteId),
    queryFn: () => deviationsApi.bySite(siteId),
  })
}

export function useDeviation(id: string) {
  return useQuery({ queryKey: keys.deviation(id), queryFn: () => deviationsApi.get(id) })
}

export function useStageStatuses(siteId: string) {
  return useQuery({
    queryKey: keys.stageStatuses(siteId),
    queryFn: () => deviationsApi.stageStatuses(siteId),
  })
}

export function useDecision(deviationId: string, siteId: string) {
  const qc = useQueryClient()
  const invalidate = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: keys.deviation(deviationId) }),
      qc.invalidateQueries({ queryKey: keys.siteDeviations(siteId) }),
      qc.invalidateQueries({ queryKey: keys.allDeviations }),
    ])
  const decide = useMutation({
    mutationFn: (data: DecisionInput) => deviationsApi.decide(deviationId, data),
    onSuccess: invalidate,
  })
  const undo = useMutation({
    mutationFn: () => deviationsApi.undoDecision(deviationId),
    onSuccess: invalidate,
  })
  return { decide, undo }
}
