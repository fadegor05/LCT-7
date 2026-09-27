import type { z } from 'zod'
import { env } from '@/lib/env'

/** Ошибка HTTP или контракта. `detail` — поле FastAPI HTTPException, если оно есть. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
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

function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown }
    if (typeof first.msg === 'string') return first.msg
  }
  return `Ошибка запроса (${status})`
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
  let payload: BodyInit | undefined
  if (body instanceof FormData) {
    payload = body
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  const response = await fetch(buildUrl(path, query), { method, headers, body: payload, signal })
  const text = await response.text()
  const data: unknown = text ? JSON.parse(text) : undefined

  if (!response.ok) {
    const detail = (data as { detail?: unknown } | undefined)?.detail
    throw new ApiError(response.status, errorMessage(detail, response.status), detail)
  }
  if (!schema) return undefined as never

  const parsed = schema.safeParse(data)
  if (!parsed.success) {
    throw new ApiError(response.status, `Ответ ${path} не совпал с контрактом`, parsed.error.issues)
  }
  return parsed.data as never
}
