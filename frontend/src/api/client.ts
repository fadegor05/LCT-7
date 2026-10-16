import type { z } from 'zod'
import { env } from '@/lib/env'
import { getToken, clearToken } from '@/lib/authStorage'

/** Ошибка HTTP или контракта. `detail` — поле FastAPI HTTPException, если оно есть. `code` — код ошибки из тела ответа для типизированной классификации. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown
  readonly code: string | undefined

  constructor(status: number, message: string, detail?: unknown, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.code = code
  }
}

type Query = Record<string, string | number | boolean | null | undefined>

interface RequestOptions<S extends z.ZodType | undefined> {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  schema?: S
  body?: unknown
  query?: Query
  signal?: AbortSignal
}

let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler
}

function buildUrl(path: string, query?: Query): string {
  const url = `${env.apiBaseUrl}${path}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

/**
 * Текст ошибки для интерфейса. Строковый `detail` пишет сервис бэкенда — по-русски и для
 * пользователя. Список в `detail` (422) — ошибки валидации FastAPI/pydantic: они
 * по-английски и для разработчика, поэтому показываем общий текст, а сырые сообщения
 * остаются в `ApiError.detail` и в консоли.
 */
function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    console.warn('Ошибка валидации запроса', detail)
    return 'Проверьте введённые данные'
  }
  return `Ошибка запроса (${status})`
}

/**
 * Тело ответа как JSON. На 500 сервер и прокси отдают простой текст («Internal Server Error»):
 * это не JSON, и текст ошибки разбора не должен попадать в интерфейс.
 */
function parseJson(text: string): unknown {
  if (!text) return undefined
  try {
    return JSON.parse(text) as unknown
  } catch {
    return undefined
  }
}

/**
 * Единственная точка обращения к API. Ответ проверяется Zod-схемой: расхождение контракта
 * всплывает сразу как ApiError, а не как `undefined` глубоко в компоненте.
 */
export async function request<S extends z.ZodType | undefined = undefined>(
  path: string,
  { method = 'GET', schema, body, query, signal }: RequestOptions<S> = {},
): Promise<S extends z.ZodType ? z.output<S> : void> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = getToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  let payload: BodyInit | undefined
  if (body instanceof FormData) {
    payload = body
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  const response = await fetch(buildUrl(path, query), { method, headers, body: payload, signal })
  const data = parseJson(await response.text())

  if (!response.ok) {
    const detail = (data as { detail?: unknown; code?: unknown } | undefined)?.detail
    const code = (data as { code?: unknown } | undefined)?.code
    const codeString = typeof code === 'string' ? code : undefined
    const error = new ApiError(
      response.status,
      errorMessage(detail, response.status),
      detail,
      codeString,
    )

    // Handle 401 on protected routes
    if (response.status === 401 && path !== '/auth/login') {
      clearToken()
      unauthorizedHandler?.()
    }

    throw error
  }
  if (!schema) return undefined as never

  const parsed = schema.safeParse(data)
  if (!parsed.success) {
    throw new ApiError(response.status, `Ответ ${path} не совпал с контрактом`, parsed.error.issues)
  }
  return parsed.data as never
}
