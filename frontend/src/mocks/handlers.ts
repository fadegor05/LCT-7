/**
 * MSW-хендлеры: реализация контракта backend поверх in-memory db. Одни и те же хендлеры
 * работают в браузере (VITE_USE_MOCKS=true) и в тестах (src/test/setup.ts).
 */
import { delay, http, HttpResponse } from 'msw'
import { parseModeSchema, type ChannelKind, type Zone } from '@/api/schemas'
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

/** Снимок-заглушка без рамок — как `/image` бэкенда: сам кадр для ориентира зоны. */
function photoImage(siteId: string, photoId: string) {
  try {
    db.findPhoto(siteId, photoId)
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="#c9d3da"/><rect y="170" width="400" height="130" fill="#a38f74"/></svg>`
    return new HttpResponse(svg, {
      headers: { 'Content-Type': 'image/svg+xml', 'X-Content-Type-Options': 'nosniff' },
    })
  } catch {
    return HttpResponse.json({ detail: 'Файл снимка недоступен' }, { status: 404 })
  }
}

type SiteParams = { siteId: string }

/** Тело запроса камеры: поля как у CameraIn/CameraUpdate бэкенда; в PATCH отсутствующее поле не меняется. */
interface CameraBody {
  name: string
  stream_url: string | null
  capture_every_s: number | null
  zone: Zone | null
}

const cameraWrite = (body: CameraBody): db.CameraWrite => ({
  name: body.name,
  stream_url: body.stream_url ?? null,
  capture_every_s: body.capture_every_s ?? null,
  zone: body.zone ?? null,
})

export const handlers = [
  http.all(api('/*'), latency),

  http.post(api('/auth/login'), async ({ request }) => {
    const data = await json<{ login: string; password: string }>(request)
    // Demo credentials: demo/demo
    return handle(() => {
      if (data.login.toLowerCase() === 'demo' && data.password === 'demo') {
        return {
          access_token: 'mock-token',
          token_type: 'bearer' as const,
          user,
        }
      }
      throw new db.MockError(401, 'Неверный логин или пароль')
    })
  }),

  http.post(api('/auth/register'), async ({ request }) => {
    const data = await json<{ login: string; password: string; full_name?: string }>(request)
    return handle(() => {
      const login = data.login.trim().toLowerCase()
      if (login === 'demo') {
        throw new db.MockError(409, 'Логин уже занят')
      }
      return {
        access_token: 'mock-token',
        token_type: 'bearer' as const,
        user: { ...user, login, full_name: data.full_name?.trim() || login },
      }
    })
  }),

  http.get(api('/users/me'), ({ request }) => {
    const authHeader = request.headers.get('Authorization')
    if (!authHeader) {
      return handle(() => {
        throw new db.MockError(401, 'Требуется авторизация')
      })
    }
    return HttpResponse.json(db.getUser())
  }),

  http.patch(api('/users/me'), async ({ request }) => {
    const data = await json<{ full_name: string }>(request)
    return handle(() => db.renameUser(data.full_name))
  }),

  // ---------- Уведомления ----------
  http.get(api('/notifications'), () => handle(db.listNotifications)),
  http.post(api('/notifications/read'), () => handle(db.markAllRead)),
  http.post(api('/notifications/test'), async ({ request }) => {
    const data = await json<{ title?: string; body?: string; link?: string | null }>(request)
    return handle(() => db.createTestNotification(data), 201)
  }),

  // ---------- Каналы доставки ----------
  http.get(api('/users/me/channels'), () => handle(db.listChannels)),
  http.post<{ channel: ChannelKind }>(
    api('/users/me/channels/:channel/link'),
    async ({ params, request }) => {
      // У телеграма тела нет
      const data = await json<{ address?: string }>(request).catch((): { address?: string } => ({}))
      return handle(() => db.linkChannel(params.channel, data.address))
    },
  ),
  http.patch<{ channel: ChannelKind }>(
    api('/users/me/channels/:channel'),
    async ({ params, request }) => {
      const data = await json<{ enabled: boolean }>(request)
      return handle(() => db.toggleChannel(params.channel, data.enabled))
    },
  ),
  http.delete<{ channel: ChannelKind }>(api('/users/me/channels/:channel'), ({ params }) =>
    handle(() => {
      db.unlinkChannel(params.channel)
      return undefined
    }),
  ),

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
    const form = await request.formData()
    const file = form.get('file')
    if (!isFile(file)) return HttpResponse.json({ detail: 'Нет файла' }, { status: 422 })
    const mode = parseModeSchema.catch('auto').parse(form.get('mode'))
    return handle(() => db.importSchedule(params.siteId, file.name, mode), 201)
  }),
  http.post<SiteParams>(
    api('/sites/:siteId/schedule/stages/merge'),
    async ({ params, request }) => {
      const data = await json<{ stage_ids: string[] }>(request)
      return handle(() => db.mergeStages(params.siteId, data.stage_ids))
    },
  ),
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
  http.post<SiteParams>(api('/sites/:siteId/methodology/apply-defaults'), ({ params }) =>
    handle(() => db.applyDefaultKits(params.siteId), 200),
  ),

  // ---------- Снимки ----------
  http.get<SiteParams>(api('/sites/:siteId/photos'), ({ params, request }) => {
    const undated = new URL(request.url).searchParams.get('undated') === 'true'
    return handle(() => db.listPhotos(params.siteId, undated))
  }),
  http.post<SiteParams>(api('/sites/:siteId/photos'), async ({ params, request }) => {
    const form = await request.formData()
    const files = form.getAll('files').filter(isFile)
    const cameraId = form.get('camera_id')
    return handle(
      () => db.uploadPhotos(params.siteId, files, typeof cameraId === 'string' ? cameraId : null),
      201,
    )
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
    api('/sites/:siteId/photos/:photoId'),
    ({ params }) => handle(() => db.findPhoto(params.siteId, params.photoId)),
  ),
  http.get<{ siteId: string; photoId: string }>(
    api('/sites/:siteId/photos/:photoId/annotated'),
    ({ params }) => annotated(params.siteId, params.photoId),
  ),
  http.get<{ siteId: string; photoId: string }>(
    api('/sites/:siteId/photos/:photoId/image'),
    ({ params }) => photoImage(params.siteId, params.photoId),
  ),

  // ---------- Камеры ----------
  http.get<SiteParams>(api('/sites/:siteId/cameras'), ({ params }) =>
    handle(() => db.listCameras(params.siteId)),
  ),
  http.post<SiteParams>(api('/sites/:siteId/cameras'), async ({ params, request }) => {
    const body = await json<CameraBody>(request)
    return handle(() => db.createCamera(params.siteId, cameraWrite(body)), 201)
  }),
  http.patch<{ siteId: string; cameraId: string }>(
    api('/sites/:siteId/cameras/:cameraId'),
    async ({ params, request }) => {
      const body = await json<Partial<CameraBody>>(request)
      return handle(() => db.updateCamera(params.siteId, params.cameraId, body))
    },
  ),
  http.post<SiteParams>(api('/sites/:siteId/cameras/preview'), async ({ params, request }) => {
    const body = await json<{ stream_url: string }>(request)
    return handle(() => db.previewFrame(params.siteId, body.stream_url))
  }),
  http.post<{ siteId: string; cameraId: string }>(
    api('/sites/:siteId/cameras/:cameraId/capture'),
    ({ params }) => handle(() => db.captureCamera(params.siteId, params.cameraId), 201),
  ),
  http.delete<{ siteId: string; cameraId: string }>(
    api('/sites/:siteId/cameras/:cameraId'),
    ({ params }) => handle(() => db.deleteCamera(params.siteId, params.cameraId)),
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
