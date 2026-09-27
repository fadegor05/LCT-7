import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { request } from './client'
import { keys } from './keys'
import { siteSchema, userSchema, type SiteCreate } from './schemas'

export const sitesApi = {
  me: () => request('/users/me', { schema: userSchema }),
  list: () => request('/sites', { schema: z.array(siteSchema) }),
  get: (siteId: string) => request(`/sites/${siteId}`, { schema: siteSchema }),
  create: (data: SiteCreate) =>
    request('/sites', { method: 'POST', body: data, schema: siteSchema }),
  update: (siteId: string, data: Partial<SiteCreate>) =>
    request(`/sites/${siteId}`, { method: 'PATCH', body: data, schema: siteSchema }),
  activate: (siteId: string) =>
    request(`/sites/${siteId}/activate`, { method: 'POST', schema: siteSchema }),
}

export function useMe() {
  return useQuery({ queryKey: keys.me, queryFn: sitesApi.me })
}

export function useSites() {
  return useQuery({ queryKey: keys.sites, queryFn: sitesApi.list })
}

export function useSite(siteId: string) {
  return useQuery({ queryKey: keys.site(siteId), queryFn: () => sitesApi.get(siteId) })
}

export function useCreateSite() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: sitesApi.create,
    onSuccess: (site) => qc.setQueryData(keys.site(site.id), site),
  })
}

export function useUpdateSite(siteId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<SiteCreate>) => sitesApi.update(siteId, data),
    onSuccess: (site) => qc.setQueryData(keys.site(siteId), site),
  })
}

export function useActivateSite(siteId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => sitesApi.activate(siteId),
    onSuccess: async (site) => {
      qc.setQueryData(keys.site(siteId), site)
      await qc.invalidateQueries({ queryKey: keys.sites })
    },
  })
}
