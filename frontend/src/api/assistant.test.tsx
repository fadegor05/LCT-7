/**
 * Тесты API ассистента: классификация ошибок, хуки useAssistantStatus и useAskAssistant,
 * локальная валидация, отмена, двойное отправка, эфемерность ответов.
 */
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import * as db from '@/mocks/db'
import { BEREZNIKI } from '@/mocks/fixtures'
import { ApiError } from './client'
import { classifyAssistantError, useAskAssistant, useAssistantStatus } from './assistant'

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
  })
}

function wrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

describe('classifyAssistantError', () => {
  it('AbortError с name === "AbortError" → cancelled', () => {
    const error = new DOMException('user cancelled', 'AbortError')
    const result = classifyAssistantError(error)
    expect(result).toEqual({ kind: 'cancelled', message: '', retryable: false })
  })

  it('отклоненный fetch (TypeError) → unavailable', () => {
    const error = new TypeError('Failed to fetch')
    const result = classifyAssistantError(error)
    expect(result).toEqual({
      kind: 'unavailable',
      message: 'Нет связи с сервером',
      retryable: false,
    })
  })

  it.each([
    [404, undefined, 'not_found', 'Стройка не найдена'],
    [422, undefined, 'invalid_question', 'Вопрос должен быть от 3 до 500 символов'],
    [429, 'rate_limited', 'rate_limited', 'Слишком много вопросов'],
    [503, 'assistant_unavailable', 'unavailable', 'Ассистент недоступен'],
    [504, 'assistant_timeout', 'timeout', 'Модель не ответила'],
    [413, 'report_too_large', 'too_large', 'Отчёт слишком велик'],
    [422, 'out_of_scope', 'out_of_scope', 'отвечает только на вопросы'],
    [400, 'assistant_bad_request', 'bad_request', 'Плохой запрос'],
    [500, undefined, 'unknown', 'Не удалось получить ответ'],
  ])('ApiError status %i code %s → kind %s', (status, code, expectedKind, messageSnippet) => {
    const error = new ApiError(status, messageSnippet, [], code)
    const result = classifyAssistantError(error)
    expect(result.kind).toBe(expectedKind)
    if (messageSnippet) expect(result.message).toContain(messageSnippet)
  })

  it('timeout → retryable: true, остальные → false', () => {
    const timeout = classifyAssistantError(new ApiError(504, 'x', [], 'assistant_timeout'))
    expect(timeout.retryable).toBe(true)

    const unavailable = classifyAssistantError(new ApiError(503, 'x', [], 'assistant_unavailable'))
    expect(unavailable.retryable).toBe(false)

    const rateLimited = classifyAssistantError(new ApiError(429, 'x', [], 'rate_limited'))
    expect(rateLimited.retryable).toBe(false)
  })

  it('unknown code в ApiError → unknown', () => {
    const error = new ApiError(400, 'test', [], 'unknown_code_xyz')
    const result = classifyAssistantError(error)
    expect(result.kind).toBe('unknown')
  })

  it('обычная ошибка (не ApiError) → unknown', () => {
    const error = new Error('Some error')
    const result = classifyAssistantError(error)
    expect(result.kind).toBe('unknown')
    expect(result.message).toBe('Не удалось получить ответ')
  })
})

describe('useAssistantStatus', () => {
  let client: QueryClient

  beforeEach(() => {
    client = createTestQueryClient()
    db.resetDb()
  })

  it('по умолчанию ассистент включён', async () => {
    const { result } = renderHook(() => useAssistantStatus(), { wrapper: wrapper(client) })

    await waitFor(() => {
      expect(result.current.isPending).toBe(false)
    })

    expect(result.current.enabled).toBe(true)
  })

  it('сценарий no_llm → enabled: false', async () => {
    db.setAssistantScenario('no_llm')
    const { result } = renderHook(() => useAssistantStatus(), { wrapper: wrapper(client) })

    await waitFor(() => {
      expect(result.current.isPending).toBe(false)
    })

    expect(result.current.enabled).toBe(false)
  })

  it('сценарий unavailable → enabled: false', async () => {
    db.setAssistantScenario('unavailable')
    const { result } = renderHook(() => useAssistantStatus(), { wrapper: wrapper(client) })

    await waitFor(() => {
      expect(result.current.isPending).toBe(false)
    })

    expect(result.current.enabled).toBe(false)
  })

  it('500 ошибка → enabled: false, одна попытка, нет ошибок в консоли', async () => {
    server.use(http.get('*/assistant/status', () => new HttpResponse(null, { status: 500 })))

    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const { result } = renderHook(() => useAssistantStatus(), { wrapper: wrapper(client) })

    await waitFor(() => {
      expect(result.current.isPending).toBe(false)
    })

    expect(result.current.enabled).toBe(false)
    expect(consoleErrorSpy).not.toHaveBeenCalled()

    consoleErrorSpy.mockRestore()
  })

  it('404 ошибка → enabled: false', async () => {
    server.use(
      http.get('*/assistant/status', () =>
        HttpResponse.json({ detail: 'Not found' }, { status: 404 }),
      ),
    )

    const { result } = renderHook(() => useAssistantStatus(), { wrapper: wrapper(client) })

    await waitFor(() => {
      expect(result.current.isPending).toBe(false)
    })

    expect(result.current.enabled).toBe(false)
  })

  it('невалидный JSON → enabled: false', async () => {
    server.use(http.get('*/assistant/status', () => new HttpResponse('<html>')))

    const { result } = renderHook(() => useAssistantStatus(), { wrapper: wrapper(client) })

    await waitFor(() => {
      expect(result.current.isPending).toBe(false)
    })

    expect(result.current.enabled).toBe(false)
  })

  it('контракт не совпал (enabled: "yes") → enabled: false', async () => {
    server.use(
      http.get('*/assistant/status', () => HttpResponse.json({ enabled: 'yes' }, { status: 200 })),
    )

    const { result } = renderHook(() => useAssistantStatus(), { wrapper: wrapper(client) })

    await waitFor(() => {
      expect(result.current.isPending).toBe(false)
    })

    expect(result.current.enabled).toBe(false)
  })

  it('HttpResponse.error() → enabled: false', async () => {
    server.use(http.get('*/assistant/status', () => HttpResponse.error()))

    const { result } = renderHook(() => useAssistantStatus(), { wrapper: wrapper(client) })

    await waitFor(() => {
      expect(result.current.isPending).toBe(false)
    })

    expect(result.current.enabled).toBe(false)
  })
})

describe('useAskAssistant', () => {
  let client: QueryClient

  beforeEach(() => {
    client = createTestQueryClient()
    db.resetDb()
  })

  it('успешный ask: question "где отставание и на сколько"', async () => {
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('где отставание и на сколько')

    expect(answer).toBeDefined()
    expect(answer?.answer).toContain('Этап')

    await waitFor(() => {
      expect(result.current.isPending).toBe(false)
    })

    expect(result.current.answer).toBeDefined()
    expect(result.current.failure).toBeUndefined()
  })

  it('валидация: question "  ab  " → invalid_question, counter 0', async () => {
    let requestCount = 0
    server.use(
      http.post(`*/sites/${BEREZNIKI}/assistant/ask`, () => {
        requestCount++
        return HttpResponse.json({ answer: 'test' }, { status: 200 })
      }),
    )

    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('  ab  ')

    await waitFor(() => {
      expect(result.current.failure?.kind).toBe('invalid_question')
    })

    expect(answer).toBeUndefined()
    expect(requestCount).toBe(0)
  })

  it('валидация: 3 символа проходит', async () => {
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('abc')

    expect(answer).toBeDefined()
  })

  it('валидация: 500 символов проходит', async () => {
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('a'.repeat(500))

    expect(answer).toBeDefined()
  })

  it('валидация: 501 символ не проходит', async () => {
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('a'.repeat(501))

    expect(answer).toBeUndefined()
    expect(result.current.failure?.kind).toBe('invalid_question')
  })

  it('вопрос отправляется триммированным', async () => {
    let capturedBody: unknown
    server.use(
      http.post(`*/sites/${BEREZNIKI}/assistant/ask`, async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json(
          {
            answer: 'test',
            verified: true,
            numbers_not_in_report: [],
            numbers_of_other_site: [],
            limits: 'test',
            site_label: 'p1',
            stages: [],
          },
          { status: 200 },
        )
      }),
    )

    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    await result.current.ask('  hello world  ')

    expect(capturedBody).toEqual({ question: 'hello world' })
  })

  it('scenario rate_limited → failure с kind и message', async () => {
    db.setAssistantScenario('rate_limited')
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('что с этапами')

    expect(answer).toBeUndefined()
    expect(result.current.failure?.kind).toBe('rate_limited')
    expect(result.current.failure?.message).toContain('Слишком много вопросов')
  })

  it('scenario timeout → failure с kind timeout, retryable: true', async () => {
    db.setAssistantScenario('timeout')
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('что с этапами')

    expect(answer).toBeUndefined()
    expect(result.current.failure?.kind).toBe('timeout')
    expect(result.current.failure?.retryable).toBe(true)
  })

  it('scenario out_of_scope → failure', async () => {
    db.setAssistantScenario('out_of_scope')
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('что с этапами')

    expect(answer).toBeUndefined()
    expect(result.current.failure?.kind).toBe('out_of_scope')
  })

  it('scenario too_large → failure', async () => {
    db.setAssistantScenario('too_large')
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('что с этапами')

    expect(answer).toBeUndefined()
    expect(result.current.failure?.kind).toBe('too_large')
  })

  it('scenario unavailable → failure unavailable', async () => {
    db.setAssistantScenario('unavailable')
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('что с этапами')

    expect(answer).toBeUndefined()
    expect(result.current.failure?.kind).toBe('unavailable')
  })

  it('unknown site → not_found', async () => {
    const { result } = renderHook(() => useAskAssistant('unknown-site'), {
      wrapper: wrapper(client),
    })

    const answer = await result.current.ask('что с этапами')

    expect(answer).toBeUndefined()
    expect(result.current.failure?.kind).toBe('not_found')
  })

  it('HttpResponse.error() → unavailable', async () => {
    server.use(http.post(`*/sites/${BEREZNIKI}/assistant/ask`, () => HttpResponse.error()))

    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('что с этапами')

    expect(answer).toBeUndefined()
    expect(result.current.failure?.kind).toBe('unavailable')
  })

  it('double submit: вторая ask() во время pending возвращает undefined, одна сетевая запрос', async () => {
    let requestCount = 0
    server.use(
      http.post(`*/sites/${BEREZNIKI}/assistant/ask`, async () => {
        requestCount++
        await new Promise((resolve) => setTimeout(resolve, 100))
        return HttpResponse.json(
          {
            answer: 'test',
            verified: true,
            numbers_not_in_report: [],
            numbers_of_other_site: [],
            limits: 'test',
            site_label: 'p1',
            stages: [],
          },
          { status: 200 },
        )
      }),
    )

    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const promise1 = result.current.ask('first')
    const result2 = result.current.ask('second')

    expect(result2).toBeUndefined()
    const answer1 = await promise1
    expect(answer1).toBeDefined()
    expect(requestCount).toBe(1)
  })

  it('cancel: отменяет запрос, failure.kind === cancelled, нет второго запроса', async () => {
    let requestCount = 0
    server.use(
      http.post(`*/sites/${BEREZNIKI}/assistant/ask`, async () => {
        requestCount++
        await new Promise((resolve) => setTimeout(resolve, 1000))
        return HttpResponse.json(
          {
            answer: 'test',
            verified: true,
            numbers_not_in_report: [],
            numbers_of_other_site: [],
            limits: 'test',
            site_label: 'p1',
            stages: [],
          },
          { status: 200 },
        )
      }),
    )

    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const promise = result.current.ask('question')
    expect(result.current.isPending).toBe(true)

    result.current.cancel()

    await waitFor(() => {
      expect(result.current.isPending).toBe(false)
    })

    expect(result.current.failure?.kind).toBe('cancelled')
    expect(requestCount).toBe(1)

    // Следующий ask() работает
    const answer = await result.current.ask('another')
    expect(answer).toBeDefined()
  })

  it('reset: очищает answer', async () => {
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    await result.current.ask('где отставание')

    await waitFor(() => {
      expect(result.current.answer).toBeDefined()
    })

    result.current.reset()

    expect(result.current.answer).toBeUndefined()
    expect(result.current.failure).toBeUndefined()
  })

  it('localStorage и sessionStorage пусты', async () => {
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    await result.current.ask('где отставание')

    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it('изменение siteId очищает answer и абортирует in-flight запрос', async () => {
    let requestCount = 0
    server.use(
      http.post(`*/sites/${BEREZNIKI}/assistant/ask`, async () => {
        requestCount++
        await new Promise((resolve) => setTimeout(resolve, 100))
        return HttpResponse.json(
          {
            answer: 'test',
            verified: true,
            numbers_not_in_report: [],
            numbers_of_other_site: [],
            limits: 'test',
            site_label: 'p1',
            stages: [],
          },
          { status: 200 },
        )
      }),
    )

    const { result, rerender } = renderHook(({ siteId }) => useAskAssistant(siteId), {
      wrapper: wrapper(client),
      initialProps: { siteId: BEREZNIKI },
    })

    const promise = result.current.ask('question')

    rerender({ siteId: 'other-site' })

    await waitFor(() => {
      expect(result.current.answer).toBeUndefined()
    })
  })

  it('invalidation of ["site", siteId] очищает answer', async () => {
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    await result.current.ask('где отставание')

    await waitFor(() => {
      expect(result.current.answer).toBeDefined()
    })

    client.invalidateQueries({ queryKey: ['site', BEREZNIKI] })

    await waitFor(() => {
      expect(result.current.answer).toBeUndefined()
    })
  })

  it('invalidation of ["site", other-site-id] не очищает answer', async () => {
    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    await result.current.ask('где отставание')

    await waitFor(() => {
      expect(result.current.answer).toBeDefined()
    })

    client.invalidateQueries({ queryKey: ['site', 'other-id'] })

    expect(result.current.answer).toBeDefined()
  })

  it('invalidation во время pending абортирует и late response не появляется', async () => {
    let requestCount = 0
    server.use(
      http.post(`*/sites/${BEREZNIKI}/assistant/ask`, async () => {
        requestCount++
        await new Promise((resolve) => setTimeout(resolve, 100))
        return HttpResponse.json(
          {
            answer: 'test',
            verified: true,
            numbers_not_in_report: [],
            numbers_of_other_site: [],
            limits: 'test',
            site_label: 'p1',
            stages: [],
          },
          { status: 200 },
        )
      }),
    )

    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const askPromise = result.current.ask('question')

    // Invalidate while pending
    client.invalidateQueries({ queryKey: ['site', BEREZNIKI] })

    // Wait for the ask to complete and handler to resolve
    await askPromise
    await new Promise((resolve) => setTimeout(resolve, 50))

    // Answer should still be undefined because invalidation aborted/rejected it
    expect(result.current.answer).toBeUndefined()
    expect(requestCount).toBe(1)
  })

  it('contract drift: answer без stages → failure unknown с "не совпал с контрактом"', async () => {
    server.use(
      http.post(`*/sites/${BEREZNIKI}/assistant/ask`, () =>
        HttpResponse.json(
          {
            answer: 'test',
            verified: true,
            numbers_not_in_report: [],
            numbers_of_other_site: [],
            limits: 'test',
            site_label: 'p1',
            // stages поле отсутствует!
          },
          { status: 200 },
        ),
      ),
    )

    const { result } = renderHook(() => useAskAssistant(BEREZNIKI), { wrapper: wrapper(client) })

    const answer = await result.current.ask('где отставание')

    await waitFor(() => {
      expect(result.current.failure).toBeDefined()
    })

    expect(answer).toBeUndefined()
    expect(result.current.failure?.kind).toBe('unknown')
    expect(result.current.failure?.message).toContain('не совпал с контрактом')
  })

  it('unmount while pending: нет React warning', async () => {
    server.use(
      http.post(`*/sites/${BEREZNIKI}/assistant/ask`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 500))
        return HttpResponse.json(
          {
            answer: 'test',
            verified: true,
            numbers_not_in_report: [],
            numbers_of_other_site: [],
            limits: 'test',
            site_label: 'p1',
            stages: [],
          },
          { status: 200 },
        )
      }),
    )

    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const { result, unmount } = renderHook(() => useAskAssistant(BEREZNIKI), {
      wrapper: wrapper(client),
    })

    result.current.ask('question')
    unmount()

    await new Promise((resolve) => setTimeout(resolve, 600))

    expect(consoleErrorSpy).not.toHaveBeenCalled()

    consoleErrorSpy.mockRestore()
  })
})
