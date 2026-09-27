import { http, HttpResponse } from 'msw'
import { z } from 'zod'
import { server } from '@/mocks/server'
import { ApiError, request } from './client'

describe('request', () => {
  it('parses the response with the schema and passes query params', async () => {
    let url = ''
    server.use(
      http.get('/api/echo', ({ request: r }) => {
        url = r.url
        return HttpResponse.json({ value: 1 })
      }),
    )
    const data = await request('/echo', {
      schema: z.object({ value: z.number() }),
      query: { date: '2026-09-18', skip: null, none: undefined },
    })
    expect(data).toEqual({ value: 1 })
    expect(url).toContain('?date=2026-09-18')
    expect(url).not.toContain('skip')
  })

  it('sends JSON bodies', async () => {
    let body: unknown
    let type: string | null = null
    server.use(
      http.post('/api/items', async ({ request: r }) => {
        body = await r.json()
        type = r.headers.get('content-type')
        return new HttpResponse(null, { status: 204 })
      }),
    )
    await expect(request('/items', { method: 'POST', body: { a: 1 } })).resolves.toBeUndefined()
    expect(body).toEqual({ a: 1 })
    expect(type).toBe('application/json')
  })

  it('sends FormData without forcing a content type', async () => {
    let name: FormDataEntryValue | null = null
    server.use(
      http.post('/api/upload', async ({ request: r }) => {
        name = (await r.formData()).get('name')
        return HttpResponse.json({})
      }),
    )
    const form = new FormData()
    form.append('name', 'x')
    await request('/upload', { method: 'POST', body: form })
    expect(name).toBe('x')
  })

  it('throws ApiError with FastAPI detail', async () => {
    server.use(
      http.get('/api/fail', () => HttpResponse.json({ detail: 'Нет доступа' }, { status: 403 })),
    )
    const error = await request('/fail').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 403, message: 'Нет доступа' })
  })

  it('hides raw pydantic messages behind a generic text for 422', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const detail = [{ msg: 'Value error, captured_on cannot be in the future' }]
    server.use(http.get('/api/invalid', () => HttpResponse.json({ detail }, { status: 422 })))
    const error = await request('/invalid').catch((e: unknown) => e)
    expect(error).toMatchObject({ status: 422, message: 'Проверьте введённые данные', detail })
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })

  it('falls back to a generic message', async () => {
    server.use(http.get('/api/boom', () => new HttpResponse(null, { status: 500 })))
    await expect(request('/boom')).rejects.toThrow('Ошибка запроса (500)')
  })

  it('reports contract mismatches', async () => {
    server.use(http.get('/api/bad', () => HttpResponse.json({ value: 'x' })))
    await expect(request('/bad', { schema: z.object({ value: z.number() }) })).rejects.toThrow(
      'не совпал с контрактом',
    )
  })
})
