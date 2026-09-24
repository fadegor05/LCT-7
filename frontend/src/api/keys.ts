/** Ключи TanStack Query. Иерархия ['site', id, ...] позволяет инвалидировать всё по стройке разом. */
export const keys = {
  me: ['me'] as const,
  sites: ['sites'] as const,
  site: (siteId: string) => ['site', siteId] as const,
  scheduleImport: (siteId: string) => ['site', siteId, 'schedule-import'] as const,
  stages: (siteId: string) => ['site', siteId, 'stages'] as const,
  methodology: (siteId: string) => ['site', siteId, 'methodology'] as const,
  equipmentClasses: ['equipment-classes'] as const,
  cameras: (siteId: string) => ['site', siteId, 'cameras'] as const,
  observationDays: (siteId: string) => ['site', siteId, 'observations'] as const,
  observation: (siteId: string, date: string) => ['site', siteId, 'observations', date] as const,
  frames: (siteId: string, date: string | null) =>
    ['site', siteId, 'frames', date ?? 'all'] as const,
  needsReview: (siteId: string) => ['site', siteId, 'needs-review'] as const,
  streams: (siteId: string) => ['site', siteId, 'streams'] as const,
  stageStatuses: (siteId: string) => ['site', siteId, 'stage-statuses'] as const,
  siteDeviations: (siteId: string) => ['site', siteId, 'deviations'] as const,
  allDeviations: ['deviations'] as const,
  deviation: (id: string) => ['deviation', id] as const,
}
