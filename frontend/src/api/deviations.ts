/** Выводы по стройке (домен assessment): статусы этапов, отклонения, итог. Только чтение. */
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { request } from './client'
import { keys } from './keys'
import {
  deviationDetailSchema,
  deviationSchema,
  siteSummarySchema,
  stageStatusSchema,
  type Site,
} from './schemas'

const base = (siteId: string) => `/sites/${siteId}/assessment`

export const deviationsApi = {
  /** Статусы этапов по position; 404 — график не загружен. */
  stageStatuses: (siteId: string) =>
    request(`${base(siteId)}/stages`, { schema: z.array(stageStatusSchema) }),
  list: (siteId: string) =>
    request(`${base(siteId)}/deviations`, { schema: z.array(deviationSchema) }),
  get: (siteId: string, id: string) =>
    request(`${base(siteId)}/deviations/${id}`, { schema: deviationDetailSchema }),
  summary: (siteId: string) => request(`${base(siteId)}/summary`, { schema: siteSummarySchema }),
  /** Решение по гипотезе; `decision: null` — снять («Изменить решение»). */
  decide: (siteId: string, id: string, body: DecisionInput) =>
    request(`${base(siteId)}/deviations/${id}/decision`, {
      method: 'PUT',
      body,
      schema: deviationDetailSchema,
    }),
}

export interface DecisionInput {
  decision: 'confirmed' | 'rejected' | null
  comment?: string | null
}

/** Решение инженера: обновляет списки, счётчики и карточку объекта. */
export function useDecision(siteId: string, id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: DecisionInput) => deviationsApi.decide(siteId, id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.site(siteId) }),
  })
}

export function useStageStatuses(siteId: string, enabled = true) {
  return useQuery({
    queryKey: keys.stageStatuses(siteId),
    queryFn: () => deviationsApi.stageStatuses(siteId),
    enabled,
  })
}

export function useDeviations(siteId: string) {
  return useQuery({ queryKey: keys.deviations(siteId), queryFn: () => deviationsApi.list(siteId) })
}

export function useDeviation(siteId: string, id: string) {
  return useQuery({
    queryKey: keys.deviation(siteId, id),
    queryFn: () => deviationsApi.get(siteId, id),
  })
}

export function useSummary(siteId: string) {
  return useQuery({ queryKey: keys.summary(siteId), queryFn: () => deviationsApi.summary(siteId) })
}

/** Сквозного списка на бэкенде нет: собираем отклонения по каждой стройке. */
export function useAllDeviations(sites: readonly Site[]) {
  return useQueries({
    queries: sites.map((site) => ({
      queryKey: keys.deviations(site.id),
      queryFn: () => deviationsApi.list(site.id),
    })),
    combine: (results) => ({
      isPending: results.some((r) => r.isPending),
      error: results.find((r) => r.error)?.error ?? null,
      data: results.flatMap((r, i) =>
        (r.data ?? []).map((d) => ({ ...d, site_id: sites[i]!.id, site_name: sites[i]!.name })),
      ),
    }),
  })
}
