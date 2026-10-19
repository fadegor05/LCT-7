import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { ApiError, request } from './client'
import { keys } from './keys'
import { siteSchema, userSchema, type Site, type SiteCreate } from './schemas'

/** Пустой адрес в форме — это «нет адреса» (null) на бэкенде. */
const toBody = (data: Partial<SiteCreate>) =>
  data.address === undefined ? data : { ...data, address: data.address.trim() || null }

/** id стройки из URL не UUID — бэкенд отвечает 422 с текстом pydantic. Для человека это та же «не найдена». */
async function getSite(siteId: string) {
  try {
    return await request(`/sites/${siteId}`, { schema: siteSchema })
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      throw new ApiError(404, 'Стройка не найдена', error.detail)
    }
    throw error
  }
}

export const sitesApi = {
  me: () => request('/users/me', { schema: userSchema }),
  list: () => request('/sites', { schema: z.array(siteSchema) }),
  get: getSite,
  create: (data: SiteCreate) =>
    request('/sites', { method: 'POST', body: toBody(data), schema: siteSchema }),
  update: (siteId: string, data: Partial<SiteCreate>) =>
    request(`/sites/${siteId}`, { method: 'PATCH', body: toBody(data), schema: siteSchema }),
}

export function useMe() {
  return useQuery({ queryKey: keys.me, queryFn: sitesApi.me })
}

export function useSites() {
  return useQuery({ queryKey: keys.sites, queryFn: sitesApi.list })
}

export function useSite(siteId: string) {
  const qc = useQueryClient()
  return useQuery({
    queryKey: keys.site(siteId),
    queryFn: () => sitesApi.get(siteId),
    // Шапка объекта сразу из списка строек: переход со «Строек» не ждёт запроса
    initialData: () => qc.getQueryData<Site[]>(keys.sites)?.find((s) => s.id === siteId),
    initialDataUpdatedAt: () => qc.getQueryState(keys.sites)?.dataUpdatedAt,
  })
}

export function useCreateSite() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: sitesApi.create,
    onSuccess: async (site) => {
      qc.setQueryData(keys.site(site.id), site)
      await qc.invalidateQueries({ queryKey: keys.sites })
    },
  })
}

export function useUpdateSite(siteId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<SiteCreate>) => sitesApi.update(siteId, data),
    onSuccess: async (site) => {
      qc.setQueryData(keys.site(siteId), site)
      await qc.invalidateQueries({ queryKey: keys.sites })
    },
  })
}
