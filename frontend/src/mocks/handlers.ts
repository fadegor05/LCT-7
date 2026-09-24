/**
 * MSW-хендлеры: реализация контракта API поверх in-memory db. Одни и те же хендлеры
 * работают в браузере (VITE_USE_MOCKS=true) и в тестах (src/test/setup.ts).
 */
import { delay, http, HttpResponse } from 'msw'
import { env } from '@/lib/env'
import * as db from './db'
import { equipmentClasses, user } from './fixtures'

const api = (path: string) => `${env.apiBaseUrl}${path}`
const notFound = (what = 'Не найдено') => HttpResponse.json({ detail: what }, { status: 404 })
const conflict = (detail: string) => HttpResponse.json({ detail }, { status: 409 })

/** Небольшая задержка в браузере, чтобы были видны состояния загрузки; в тестах — ноль. */
const latency = () => (import.meta.env.MODE === 'test' ? Promise.resolve() : delay(250))

type SiteParams = { siteId: string }

/** В тестах FormData разбирает Node, и File там — не тот класс, что глобальный в jsdom. */
const isFile = (value: unknown): value is File =>
  typeof value === 'object' && value !== null && 'name' in value && 'size' in value

async function json<T>(request: Request): Promise<T> {
  return (await request.json()) as T
}

const REFERENCE_FRAME =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="#c9d3da"/><rect y="170" width="400" height="130" fill="#a38f74"/><rect x="40" y="120" width="120" height="70" fill="#8e8a84"/><rect x="250" y="200" width="90" height="40" fill="#e0a31a"/></svg>`,
  )

export const handlers = [
  http.all(api('/*'), latency),

  http.get(api('/users/me'), () => HttpResponse.json(user)),

  // ---------- Стройки ----------
  http.get(api('/sites'), () => HttpResponse.json(db.listSites())),
  http.post(api('/sites'), async ({ request }) =>
    HttpResponse.json(db.createSite(await json(request)), { status: 201 }),
  ),
  http.get<SiteParams>(api('/sites/:siteId'), ({ params }) => {
    const site = db.findSite(params.siteId)
    return site ? HttpResponse.json(site) : notFound('Стройка не найдена')
  }),
  http.patch<SiteParams>(api('/sites/:siteId'), async ({ params, request }) => {
    const site = db.updateSite(params.siteId, await json(request))
    return site ? HttpResponse.json(site) : notFound('Стройка не найдена')
  }),
  http.post<SiteParams>(api('/sites/:siteId/activate'), ({ params }) => {
    const result = db.activateSite(params.siteId)
    return typeof result === 'string' ? conflict(result) : HttpResponse.json(result)
  }),

  // ---------- График ----------
  http.get<SiteParams>(api('/sites/:siteId/schedule-imports/current'), ({ params }) => {
    const current = db.currentImport(params.siteId)
    return current ? HttpResponse.json(current) : notFound('График не загружен')
  }),
  http.post<SiteParams>(api('/sites/:siteId/schedule-imports'), async ({ params, request }) => {
    const file = (await request.formData()).get('file')
    if (!isFile(file)) return HttpResponse.json({ detail: 'Нет файла' }, { status: 422 })
    return HttpResponse.json(db.uploadSchedule(params.siteId, file.name, file.size), {
      status: 201,
    })
  }),
  http.get<SiteParams>(api('/sites/:siteId/stages'), ({ params }) =>
    HttpResponse.json(db.listStages(params.siteId)),
  ),
  http.patch<{ siteId: string; stageId: string }>(
    api('/sites/:siteId/stages/:stageId'),
    async ({ params, request }) => {
      const stage = db.updateStage(params.siteId, params.stageId, await json(request))
      return stage ? HttpResponse.json(stage) : notFound('Этап не найден')
    },
  ),

  // ---------- Методика ----------
  http.get(api('/equipment-classes'), () => HttpResponse.json(equipmentClasses)),
  http.get<SiteParams>(api('/sites/:siteId/methodology'), ({ params }) =>
    HttpResponse.json(db.listMethodology(params.siteId)),
  ),
  http.put<{ siteId: string; stageId: string }>(
    api('/sites/:siteId/methodology/:stageId'),
    async ({ params, request }) => {
      const kit = db.updateStageKit(params.siteId, params.stageId, await json(request))
      return kit ? HttpResponse.json(kit) : notFound('Этап не найден')
    },
  ),

  // ---------- Камеры ----------
  http.get<SiteParams>(api('/sites/:siteId/cameras'), ({ params }) =>
    HttpResponse.json(db.listCameras(params.siteId)),
  ),
  http.post<SiteParams>(api('/sites/:siteId/cameras'), async ({ params, request }) => {
    const result = db.saveCamera(params.siteId, null, await json(request))
    return typeof result === 'string'
      ? conflict(result)
      : HttpResponse.json(result, { status: 201 })
  }),
  http.patch<{ cameraId: string }>(api('/cameras/:cameraId'), async ({ params, request }) => {
    const siteId = db.cameraSite(params.cameraId)
    if (!siteId) return notFound('Камера не найдена')
    const result = db.saveCamera(siteId, params.cameraId, await json(request))
    return typeof result === 'string' ? conflict(result) : HttpResponse.json(result)
  }),
  http.post(api('/reference-frames'), async ({ request }) => {
    const { stream_url } = await json<{ stream_url: string }>(request)
    if (!stream_url) return HttpResponse.json({ detail: 'Нет ссылки на стрим' }, { status: 422 })
    return HttpResponse.json({ image_url: REFERENCE_FRAME })
  }),

  // ---------- Кадры и наблюдения ----------
  http.get<SiteParams>(api('/sites/:siteId/observations'), ({ params }) =>
    HttpResponse.json(db.observationDays(params.siteId)),
  ),
  http.get<{ siteId: string; date: string }>(
    api('/sites/:siteId/observations/:date'),
    ({ params }) => {
      const obs = db.observation(params.siteId, params.date)
      return obs ? HttpResponse.json(obs) : notFound('Наблюдения за дату нет')
    },
  ),
  http.get<SiteParams>(api('/sites/:siteId/frames/needs-review'), ({ params }) =>
    HttpResponse.json(db.needsReview(params.siteId)),
  ),
  http.get<SiteParams>(api('/sites/:siteId/frames'), ({ params, request }) => {
    const date = new URL(request.url).searchParams.get('date')
    return HttpResponse.json(db.listFrames(params.siteId, date))
  }),
  http.patch<{ frameId: string }>(api('/frames/:frameId'), async ({ params, request }) => {
    const { captured_at } = await json<{ captured_at: string }>(request)
    const frame = db.confirmFrameTime(params.frameId, captured_at)
    return frame ? HttpResponse.json(frame) : notFound('Кадр не найден')
  }),
  http.patch<{ ingestId: string }>(api('/ingests/:ingestId'), async ({ params, request }) => {
    const { clip_started_at } = await json<{ clip_started_at: string }>(request)
    const ingest = db.setClipStart(params.ingestId, clip_started_at)
    return ingest ? HttpResponse.json(ingest) : notFound('Загрузка не найдена')
  }),
  http.post<{ ingestId: string }>(api('/ingests/:ingestId/stop'), ({ params }) => {
    const ingest = db.stopIngest(params.ingestId)
    return ingest ? HttpResponse.json(ingest) : notFound('Загрузка не найдена')
  }),
  http.get<SiteParams>(api('/sites/:siteId/ingests'), ({ params }) =>
    HttpResponse.json(db.listStreams(params.siteId)),
  ),
  http.post<SiteParams>(api('/sites/:siteId/ingests'), async ({ params, request }) => {
    const form = await request.formData()
    const step = form.get('slice_step_sec')
    const ingest = db.createIngest(params.siteId, {
      source_type: form.get('source_type') as 'photo' | 'video' | 'stream',
      camera_id: form.get('camera_id') as string,
      files: form.getAll('files').filter(isFile),
      slice_step_sec: step ? Number(step) : null,
      clip_started_at: (form.get('clip_started_at') as string | null) ?? null,
    })
    return HttpResponse.json(ingest, { status: 201 })
  }),

  // ---------- Выводы ----------
  http.get<SiteParams>(api('/sites/:siteId/stage-statuses'), ({ params }) =>
    HttpResponse.json(db.stageStatuses(params.siteId)),
  ),
  http.get<SiteParams>(api('/sites/:siteId/deviations'), ({ params }) =>
    HttpResponse.json(db.siteDeviations(params.siteId)),
  ),
  http.get(api('/deviations'), () => HttpResponse.json(db.allDeviations())),
  http.get<{ id: string }>(api('/deviations/:id'), ({ params }) => {
    const deviation = db.findDeviation(params.id)
    return deviation ? HttpResponse.json(deviation) : notFound('Отклонение не найдено')
  }),
  http.post<{ id: string }>(api('/deviations/:id/decision'), async ({ params, request }) => {
    const deviation = db.findDeviation(params.id)
    if (!deviation) return notFound('Отклонение не найдено')
    if (!deviation.is_hypothesis) return conflict('Решение принимается только по гипотезе')
    const { decision, comment } = await json<{
      decision: 'confirmed' | 'rejected'
      comment: string | null
    }>(request)
    return HttpResponse.json(db.decide(params.id, decision, comment), { status: 201 })
  }),
  http.delete<{ id: string }>(api('/deviations/:id/decision'), ({ params }) => {
    db.undoDecision(params.id)
    return new HttpResponse(null, { status: 204 })
  }),
]
