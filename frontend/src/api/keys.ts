/** Ключи TanStack Query. Иерархия ['site', id, ...] позволяет инвалидировать всё по стройке разом. */
export const keys = {
  me: ['me'] as const,
  sites: ['sites'] as const,
  site: (siteId: string) => ['site', siteId] as const,
  schedule: (siteId: string) => ['site', siteId, 'schedule'] as const,
  methodology: (siteId: string) => ['site', siteId, 'methodology'] as const,
  equipmentTypes: ['equipment-types'] as const,
  observations: (siteId: string) => ['site', siteId, 'observations'] as const,
  observation: (siteId: string, date: string) => ['site', siteId, 'observations', date] as const,
  photos: (siteId: string) => ['site', siteId, 'photos'] as const,
  undatedPhotos: (siteId: string) => ['site', siteId, 'photos', 'undated'] as const,
  stageStatuses: (siteId: string) => ['site', siteId, 'assessment', 'stages'] as const,
  deviations: (siteId: string) => ['site', siteId, 'assessment', 'deviations'] as const,
  deviation: (siteId: string, id: string) =>
    ['site', siteId, 'assessment', 'deviations', id] as const,
  summary: (siteId: string) => ['site', siteId, 'assessment', 'summary'] as const,
  assistantStatus: ['assistant', 'status'] as const,
  assistant: (siteId: string) => ['site', siteId, 'assistant'] as const,
}
