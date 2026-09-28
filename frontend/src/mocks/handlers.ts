/**
 * MSW-хендлеры: реализация контракта backend поверх in-memory db. Одни и те же хендлеры
 * работают в браузере (VITE_USE_MOCKS=true) и в тестах (src/test/setup.ts).
 */
import { delay, http, HttpResponse } from 'msw'
import { env } from '@/lib/env'
import * as db from './db'
import { user } from './fixtures'

const api = (path: string) => `${env.apiBaseUrl}${path}`

/** Небольшая задержка в браузере, чтобы были видны состояния загрузки; в тестах — ноль. */
const latency = () => (import.meta.env.MODE === 'test' ? Promise.resolve() : delay(250))

/** Задержка для долгого ответа (сценарий slow). В тестах пропускается. */
const assistantLatency = () => {
  const delayMs =
    import.meta.env.MODE === 'test' ? 0 : db.assistantDelayMs(db.getAssistantScenario())
  return delayMs > 0 ? delay(delayMs) : Promise.resolve()
}

/** В тестах FormData разбирает Node, и File там — не тот класс, что глобальный в jsdom. */
const isFile = (value: unknown): value is File =>
  typeof value === 'object' && value !== null && 'name' in value && 'size' in value

async function json<T>(request: Request): Promise<T> {
  return (await request.json()) as T
}

/** Ответ как у FastAPI: доменная ошибка → `{detail}` и опционально `{code}`. */
function handle(fn: () => unknown, status = 200) {
  try {
    const body = fn()
    return body === undefined
      ? new HttpResponse(null, { status: 204 })
      : HttpResponse.json(body as object, { status })
  } catch (error) {
    if (error instanceof db.MockError) {
      const errorBody: { detail: string; code?: string } = { detail: error.message }
      if (error.code !== undefined) {
        errorBody.code = error.code
      }
      return HttpResponse.json(errorBody, { status: error.status })
    }
    throw error
  }
}

/** Снимок-заглушка с рамками найденной техники — как PNG от `/annotated`. */
function annotated(siteId: string, photoId: string) {
  try {
    const photo = db.findPhoto(siteId, photoId)
    const boxes = photo.detections
      .map(({ bbox: [x1 = 0, y1 = 0, x2 = 0, y2 = 0], equipment_code }) => {
        const [x, y, w, h] = [x1 * 400, y1 * 300, (x2 - x1) * 400, (y2 - y1) * 300]
        return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="none" stroke="#e0a31a" stroke-width="3"/><text x="${x + 4}" y="${y + 14}" font-size="12" fill="#e0a31a">${equipment_code}</text>`
      })
      .join('')
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="#c9d3da"/><rect y="170" width="400" height="130" fill="#a38f74"/>${boxes}</svg>`
    return new HttpResponse(svg, {
      headers: { 'Content-Type': 'image/svg+xml', 'X-Content-Type-Options': 'nosniff' },
    })
  } catch {
    return HttpResponse.json({ detail: 'Файл снимка недоступен' }, { status: 404 })
  }
}

type SiteParams = { siteId: string }

export const handlers = [
  http.all(api('/*'), latency),

  http.get(api('/users/me'), () => HttpResponse.json(user)),

  // ---------- Стройки ----------
  http.get(api('/sites'), () => handle(db.listSites)),
  http.post(api('/sites'), async ({ request }) => {
    const data = await json<{ name: string; address: string | null }>(request)
    return handle(() => db.createSite(data), 201)
  }),
  http.get<SiteParams>(api('/sites/:siteId'), ({ params }) =>
    handle(() => db.getSite(params.siteId)),
  ),
  http.patch<SiteParams>(api('/sites/:siteId'), async ({ params, request }) => {
    const data = await json<{ name?: string; address?: string | null }>(request)
    return handle(() => db.updateSite(params.siteId, data))
  }),

  // ---------- График ----------
  http.get<SiteParams>(api('/sites/:siteId/schedule'), ({ params }) =>
    handle(() => db.getSchedule(params.siteId)),
  ),
  http.post<SiteParams>(api('/sites/:siteId/schedule/import'), async ({ params, request }) => {
    const file = (await request.formData()).get('file')
    if (!isFile(file)) return HttpResponse.json({ detail: 'Нет файла' }, { status: 422 })
    return handle(() => db.importSchedule(params.siteId, file.name), 201)
  }),
  http.patch<{ siteId: string; stageId: string }>(
    api('/sites/:siteId/schedule/stages/:stageId'),
    async ({ params, request }) => {
      const data = await json<Parameters<typeof db.updateStageDates>[2]>(request)
      return handle(() => db.updateStageDates(params.siteId, params.stageId, data))
    },
  ),

  // ---------- Методика ----------
  http.get(api('/equipment-types'), () => handle(db.listEquipmentTypes)),
  http.get<SiteParams>(api('/sites/:siteId/methodology'), ({ params }) =>
    handle(() => db.listRules(params.siteId)),
  ),
  http.patch<{ siteId: string; ruleId: string }>(
    api('/sites/:siteId/methodology/rules/:ruleId'),
    async ({ params, request }) => {
      const data = await json<Parameters<typeof db.updateRule>[2]>(request)
      return handle(() => db.updateRule(params.siteId, params.ruleId, data))
    },
  ),
  http.post<{ siteId: string; ruleId: string }>(
    api('/sites/:siteId/methodology/rules/:ruleId/sets'),
    async ({ params, request }) => {
      const data = await json<Parameters<typeof db.createSet>[2]>(request)
      return handle(() => db.createSet(params.siteId, params.ruleId, data), 201)
    },
  ),
  http.put<{ siteId: string; setId: string }>(
    api('/sites/:siteId/methodology/sets/:setId'),
    async ({ params, request }) => {
      const data = await json<Parameters<typeof db.replaceSet>[2]>(request)
      return handle(() => db.replaceSet(params.siteId, params.setId, data))
    },
  ),
  http.delete<{ siteId: string; setId: string }>(
    api('/sites/:siteId/methodology/sets/:setId'),
    ({ params }) => handle(() => db.deleteSet(params.siteId, params.setId)),
  ),

  // ---------- Снимки ----------
  http.get<SiteParams>(api('/sites/:siteId/photos'), ({ params, request }) => {
    const undated = new URL(request.url).searchParams.get('undated') === 'true'
    return handle(() => db.listPhotos(params.siteId, undated))
  }),
  http.post<SiteParams>(api('/sites/:siteId/photos'), async ({ params, request }) => {
    const files = (await request.formData()).getAll('files').filter(isFile)
    return handle(() => db.uploadPhotos(params.siteId, files), 201)
  }),
  http.patch<{ siteId: string; photoId: string }>(
    api('/sites/:siteId/photos/:photoId/date'),
    async ({ params, request }) => {
      const { captured_on } = await json<{ captured_on: string }>(request)
      return handle(() => db.setPhotoDate(params.siteId, params.photoId, captured_on))
    },
  ),
  http.post<{ siteId: string; photoId: string }>(
    api('/sites/:siteId/photos/:photoId/detect'),
    ({ params }) => handle(() => db.redetect(params.siteId, params.photoId)),
  ),
  http.post<SiteParams>(api('/sites/:siteId/photos/detect'), ({ params, request }) => {
    const url = new URL(request.url)
    const statusParam = url.searchParams.get('status')
    const defaultStatuses: ('pending' | 'failed')[] = ['pending', 'failed']
    const statuses: ('pending' | 'failed')[] = statusParam
      ? statusParam
          .split(',')
          .filter((s): s is 'pending' | 'failed' => s === 'pending' || s === 'failed')
      : defaultStatuses
    return handle(() => db.detectBacklog(params.siteId, statuses))
  }),
  http.get<{ siteId: string; photoId: string }>(
    api('/sites/:siteId/photos/:photoId/annotated'),
    ({ params }) => annotated(params.siteId, params.photoId),
  ),

  // ---------- Наблюдения ----------
  http.get<SiteParams>(api('/sites/:siteId/observations'), ({ params }) =>
    handle(() => db.listObservations(params.siteId)),
  ),
  http.get<{ siteId: string; date: string }>(
    api('/sites/:siteId/observations/:date'),
    ({ params }) => handle(() => db.getObservation(params.siteId, params.date)),
  ),

  // ---------- Оценка ----------
  http.get<SiteParams>(api('/sites/:siteId/assessment/stages'), ({ params }) =>
    handle(() => db.listStageStatuses(params.siteId)),
  ),
  http.get<SiteParams>(api('/sites/:siteId/assessment/deviations'), ({ params }) =>
    handle(() => db.listDeviations(params.siteId)),
  ),
  http.get<{ siteId: string; id: string }>(
    api('/sites/:siteId/assessment/deviations/:id'),
    ({ params }) => handle(() => db.getDeviation(params.siteId, params.id)),
  ),
  http.get<SiteParams>(api('/sites/:siteId/assessment/summary'), ({ params }) =>
    handle(() => db.getSummary(params.siteId)),
  ),

  // ---------- Ассистент ----------
  http.get(api('/assistant/status'), () => handle(() => ({ enabled: db.assistantEnabled() }))),
  http.post<SiteParams>(api('/sites/:siteId/assistant/ask'), async ({ params, request }) => {
    await assistantLatency()
    const body = await json<{ question?: unknown }>(request)
    const questionValue = body.question
    const question = (typeof questionValue === 'string' ? questionValue : '').trim()

    // Валидация вопроса (422 без code, с list detail)
    if (question.length < 3 || question.length > 500) {
      const msgType = question.length < 3 ? 'string_too_short' : 'string_too_long'
      const msgText =
        question.length < 3
          ? 'String should have at least 3 characters'
          : 'String should have at most 500 characters'
      return HttpResponse.json(
        {
          detail: [
            {
              loc: ['body', 'question'],
              msg: msgText,
              type: msgType,
            },
          ],
        },
        { status: 422 },
      )
    }

    return handle(() => db.assistantAsk(params.siteId))
  }),
]
