/**
 * Данные вкладок объекта загружаются заранее — по наведению на вкладку или строку стройки
 * (как в clean-mvp). Переход открывает уже готовый экран: без «Загрузка…» и сдвигов.
 */
import { type QueryClient, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { request } from './client'
import { deviationsApi } from './deviations'
import { framesApi } from './frames'
import { keys } from './keys'
import { methodologyApi } from './methodology'
import { scheduleApi } from './schedule'
import { cameraSchema } from './schemas'
import { sitesApi } from './sites'

export type SiteTab = 'overview' | 'observations' | 'methodology' | 'cameras'

const cameras = (siteId: string) =>
  request(`/sites/${siteId}/cameras`, { schema: z.array(cameraSchema) })

/** Загрузить данные вкладки, если их ещё нет в кэше (свежие не перезапрашиваются). */
export async function prefetchSite(
  client: QueryClient,
  siteId: string,
  tab: SiteTab = 'overview',
): Promise<void> {
  const fetch = <T>(queryKey: readonly unknown[], queryFn: () => Promise<T>) =>
    client.prefetchQuery({ queryKey, queryFn })
  const common = [
    fetch(keys.site(siteId), () => sitesApi.get(siteId)),
    fetch(keys.observations(siteId), () => framesApi.observations(siteId)),
    fetch(keys.photos(siteId), () => framesApi.photos(siteId)),
    fetch(keys.undatedPhotos(siteId), () => framesApi.photos(siteId, true)),
  ]
  const byTab: Record<SiteTab, Promise<unknown>[]> = {
    overview: [
      fetch(keys.summary(siteId), () => deviationsApi.summary(siteId)),
      fetch(keys.deviations(siteId), () => deviationsApi.list(siteId)),
    ],
    observations: [fetch(keys.cameras(siteId), () => cameras(siteId))],
    methodology: [],
    cameras: [fetch(keys.cameras(siteId), () => cameras(siteId))],
  }
  await Promise.all([...common, ...byTab[tab]])
  // Статусы этапов и методика без графика — 404: просим их, только когда график есть
  await fetch(keys.schedule(siteId), () => scheduleApi.get(siteId))
  if (client.getQueryData(keys.schedule(siteId))) {
    if (tab === 'overview') {
      await fetch(keys.stageStatuses(siteId), () => deviationsApi.stageStatuses(siteId))
    }
    if (tab === 'methodology') {
      await fetch(keys.methodology(siteId), () => methodologyApi.list(siteId))
    }
  }
}

/** Обработчики для ссылки: данные вкладки грузятся по наведению и фокусу. */
export function usePrefetchSite() {
  const client = useQueryClient()
  return (siteId: string, tab?: SiteTab) => {
    const start = () => void prefetchSite(client, siteId, tab)
    return { onMouseEnter: start, onFocus: start }
  }
}
