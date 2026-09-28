/**
 * Тесты API ассистента: классификация ошибок, useAssistantStatus, useAskAssistant
 * (валидация до сети, двойная отправка, отмена, эфемерность ответа) поверх MSW-моков.
 */
import type { ReactNode } from 'react'
import { QueryClientProvider, type QueryClient } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import * as db from '@/mocks/db'
import { BEREZNIKI } from '@/mocks/fixtures'
import { server } from '@/mocks/server'
import { createTestQueryClient } from '@/test/render'
import { ApiError } from './client'
import {
  assistantApi,
  classifyAssistantError,
  useAskAssistant,
  useAssistantStatus,
} from './assistant'
import type { AssistantAnswer } from './schemas'

const OTHER_SITE = 'site-other'
const ASK_URL = '/api/sites/:siteId/assistant/ask'
const STATUS_URL = '/api/assistant/status'

const answerBody: AssistantAnswer = {
  answer: 'Этап 1 «Подготовка» отстаёт на 3 дня.',
  verified: true,
  numbers_not_in_report: [],
  numbers_of_other_site: [],
  limits: 'Проверяются числа, а не смысл.',
  site_label: 'p1',
  stages: [],
}

function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

function mountAsk(siteId = BEREZNIKI) {
  const client = createTestQueryClient()
  const utils = renderHook(({ id }) => useAskAssistant(id), {
    wrapper: wrapperFor(client),
    initialProps: { id: siteId },
  })
  return { ...utils, client }
}

type AskHook = { current: ReturnType<typeof useAskAssistant> }

/**
 * Состояние мутации TanStack доходит до React отложенно (пакетная рассылка через таймер),
 * уже после `act`: даём ему дойти, прежде чем читать `result.current`.
 */
const settle = () =>
  act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 10))
  })

/** Задать вопрос и дождаться, пока состояние хука обновится. */
async function submit(result: AskHook, question: string) {
  let answer: AssistantAnswer | undefined
  await act(async () => {
    answer = await result.current.ask(question)
  })
  await settle()
  return answer
}

/** Ждёт отказа запроса и возвращает ApiError; если запрос прошёл — тест падает. */
async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  let value: unknown
  try {
    value = await promise
  } catch (error) {
    if (error instanceof ApiError) return error
    throw error
  }
  throw new Error(`Ожидался отказ запроса, получен ответ: ${JSON.stringify(value)}`)
}

/** Обработчик, отвечающий по команде теста: считает вызовы и видит аборт запроса. */
function gatedAsk() {
  const state = { calls: 0, aborted: false, release: () => {} }
  const gate = new Promise<void>((resolve) => {
    state.release = resolve
  })
  server.use(
    http.post(ASK_URL, async ({ request }) => {
      state.calls += 1
      request.signal.addEventListener('abort', () => {
        state.aborted = true
      })
      await gate
      return HttpResponse.json(answerBody)
    }),
  )
  return state
}

/** Обработчик, считающий вызовы и запоминающий тело запроса. */
function countingAsk() {
  const state = { calls: 0, bodies: [] as unknown[] }
  server.use(
    http.post(ASK_URL, async ({ request }) => {
      state.calls += 1
      state.bodies.push(await request.json())
      return HttpResponse.json(answerBody)
    }),
  )
  return state
}

describe('classifyAssistantError', () => {
  it('AbortError → cancelled, без текста', () => {
    expect(classifyAssistantError(new DOMException('стоп', 'AbortError'))).toEqual({
      kind: 'cancelled',
      message: '',
      retryable: false,
    })
  })

  it('AbortError из другого окружения (не DOMException) → cancelled', () => {
    const error = Object.assign(new Error('aborted'), { name: 'AbortError' })
    expect(classifyAssistantError(error).kind).toBe('cancelled')
  })

  it('отказ fetch (TypeError) → unavailable', () => {
    expect(classifyAssistantError(new TypeError('Failed to fetch'))).toEqual({
      kind: 'unavailable',
      message: 'Нет связи с сервером',
      retryable: false,
    })
  })

  it.each([
    [404, undefined, 'not_found', 'Стройка не найдена'],
    [422, undefined, 'invalid_question', 'Вопрос должен быть от 3 до 500 символов'],
    [429, 'rate_limited', 'rate_limited', 'Слишком много вопросов. Повторите через 30 с.'],
    [503, 'assistant_unavailable', 'unavailable', 'Ассистент недоступен'],
    [504, 'assistant_timeout', 'timeout', 'Модель не ответила. Повторите вопрос позже.'],
    [413, 'report_too_large', 'too_large', 'Отчёт слишком велик для ассистента'],
    [422, 'out_of_scope', 'out_of_scope', 'Только по отчёту'],
    [400, 'assistant_bad_request', 'bad_request', 'Ассистент не принял запрос'],
    [500, undefined, 'unknown', 'Не удалось получить ответ'],
    [400, 'something_new', 'unknown', 'Не удалось получить ответ'],
  ])('ApiError %i / код %s → %s', (status, code, kind, message) => {
    const result = classifyAssistantError(new ApiError(status, message, undefined, code))
    expect(result.kind).toBe(kind)
    // Текст: у кодов сервера — серверный, у валидации и неизвестного — фиксированный клиентский.
    expect(result.message).toBe(message)
  })

  it('повторить можно только после таймаута модели', () => {
    const failures = [
      new ApiError(504, 'x', undefined, 'assistant_timeout'),
      new ApiError(503, 'x', undefined, 'assistant_unavailable'),
      new ApiError(429, 'x', undefined, 'rate_limited'),
      new ApiError(422, 'x', undefined, 'out_of_scope'),
      new ApiError(413, 'x', undefined, 'report_too_large'),
      new ApiError(400, 'x', undefined, 'assistant_bad_request'),
      new ApiError(404, 'x'),
      new ApiError(422, 'x', []),
      new TypeError('Failed to fetch'),
      new Error('x'),
    ].map((error) => classifyAssistantError(error))
    expect(failures.filter((f) => f.retryable).map((f) => f.kind)).toEqual(['timeout'])
  })

  it('произвольная ошибка → unknown', () => {
    expect(classifyAssistantError(new Error('boom'))).toEqual({
      kind: 'unknown',
      message: 'Не удалось получить ответ',
      retryable: false,
    })
  })
})

describe('useAssistantStatus', () => {
  const mountStatus = () =>
    renderHook(() => useAssistantStatus(), { wrapper: wrapperFor(createTestQueryClient()) })

  it('пока запрос идёт, ассистент выключен, а isPending — true', async () => {
    const { result } = mountStatus()
    expect(result.current).toEqual({ enabled: false, isPending: true })
    await waitFor(() => expect(result.current.isPending).toBe(false))
  })

  it('по умолчанию включён', async () => {
    const { result } = mountStatus()
    await waitFor(() => expect(result.current.enabled).toBe(true))
  })

  it.each(['no_llm', 'unavailable'] as const)('сценарий %s → выключен', async (scenario) => {
    db.setAssistantScenario(scenario)
    const { result } = mountStatus()
    await waitFor(() => expect(result.current.isPending).toBe(false))
    expect(result.current.enabled).toBe(false)
  })

  it.each([
    ['500', () => new HttpResponse('Internal Server Error', { status: 500 })],
    ['503', () => HttpResponse.json({ detail: 'Ассистент недоступен' }, { status: 503 })],
    ['404', () => HttpResponse.json({ detail: 'нет' }, { status: 404 })],
    ['не JSON', () => new HttpResponse('<html>', { status: 200 })],
    ['нарушение контракта', () => HttpResponse.json({ enabled: 'yes' })],
    ['обрыв сети', () => HttpResponse.error()],
  ])('%s → выключен, один запрос, без ошибок в консоли', async (_name, respond) => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    let calls = 0
    server.use(
      http.get(STATUS_URL, () => {
        calls += 1
        return respond()
      }),
    )
    const { result } = mountStatus()
    await waitFor(() => expect(result.current.isPending).toBe(false))
    expect(result.current.enabled).toBe(false)
    expect(calls).toBe(1)
    expect(consoleError).not.toHaveBeenCalled()
  })
})

describe('useAskAssistant', () => {
  it('успех: ответ по контракту, вопрос отправлен как есть', async () => {
    const asked = countingAsk()
    const { result } = mountAsk()

    const answer = await submit(result, 'где отставание и на сколько')

    expect(answer).toEqual(answerBody)
    expect(result.current.answer).toEqual(answerBody)
    expect(result.current.failure).toBeUndefined()
    expect(result.current.isPending).toBe(false)
    expect(asked.bodies).toEqual([{ question: 'где отставание и на сколько' }])
  })

  it('пробелы по краям обрезаются перед отправкой', async () => {
    const asked = countingAsk()
    const { result } = mountAsk()
    await submit(result, '  hello world  ')
    expect(asked.bodies).toEqual([{ question: 'hello world' }])
  })

  it.each([
    ['слишком короткий после trim', '  ab  '],
    ['501 символ', 'а'.repeat(501)],
    ['пустой', '   '],
  ])('%s: в сеть не уходит, причина — invalid_question', async (_name, question) => {
    const asked = countingAsk()
    const { result } = mountAsk()

    const answer = await submit(result, question)

    expect(answer).toBeUndefined()
    expect(result.current.failure).toEqual({
      kind: 'invalid_question',
      message: 'Вопрос должен быть от 3 до 500 символов',
      retryable: false,
    })
    expect(asked.calls).toBe(0)
  })

  it.each([
    ['3 символа', 'abc'],
    ['500 символов', 'а'.repeat(500)],
  ])('%s: уходит в сеть один раз и принимается', async (_name, question) => {
    const asked = countingAsk()
    const { result } = mountAsk()
    const answer = await submit(result, question)
    expect(asked.calls).toBe(1)
    expect(answer).toEqual(answerBody)
    expect(result.current.failure).toBeUndefined()
  })

  it.each([
    ['rate_limited', 'rate_limited', 'Слишком много вопросов. Повторите через 30 с.', false],
    ['timeout', 'timeout', 'Модель не ответила. Повторите вопрос позже.', true],
    ['out_of_scope', 'out_of_scope', 'Ассистент отвечает только на вопросы по отчёту', false],
    ['too_large', 'too_large', 'Отчёт слишком велик для ассистента', false],
    ['unavailable', 'unavailable', 'Ассистент недоступен', false],
  ] as const)('сценарий %s → %s', async (scenario, kind, text, retryable) => {
    db.setAssistantScenario(scenario)
    const { result } = mountAsk()

    const answer = await submit(result, 'что с этапами')

    expect(answer).toBeUndefined()
    expect(result.current.answer).toBeUndefined()
    expect(result.current.failure?.kind).toBe(kind)
    expect(result.current.failure?.message).toContain(text)
    expect(result.current.failure?.retryable).toBe(retryable)
  })

  it('неизвестная стройка → not_found', async () => {
    const { result } = mountAsk('unknown-site')
    await submit(result, 'что с этапами')
    expect(result.current.failure).toMatchObject({
      kind: 'not_found',
      message: 'Стройка не найдена',
    })
  })

  it('обрыв сети → unavailable', async () => {
    server.use(http.post(ASK_URL, () => HttpResponse.error()))
    const { result } = mountAsk()
    await submit(result, 'что с этапами')
    expect(result.current.failure).toMatchObject({
      kind: 'unavailable',
      message: 'Нет связи с сервером',
    })
  })

  it('расхождение контракта: без stages → unknown, а ApiError говорит о контракте', async () => {
    // `undefined` в JSON исчезает: сервер «забыл» поле stages.
    const broken = { ...answerBody, stages: undefined }
    server.use(http.post(ASK_URL, () => HttpResponse.json(broken)))

    const error = await rejection(assistantApi.ask(BEREZNIKI, 'что с этапами'))
    expect(error.message).toContain('не совпал с контрактом')

    const { result } = mountAsk()
    await submit(result, 'что с этапами')
    expect(result.current.answer).toBeUndefined()
    expect(result.current.failure?.kind).toBe('unknown')
  })

  it('повторная отправка во время ожидания: один запрос, вторая ask() даёт undefined', async () => {
    const pending = gatedAsk()
    const { result } = mountAsk()

    let first!: Promise<AssistantAnswer | undefined>
    let second!: Promise<AssistantAnswer | undefined>
    act(() => {
      first = result.current.ask('первый вопрос')
      second = result.current.ask('второй вопрос')
    })

    await expect(second).resolves.toBeUndefined()
    await waitFor(() => expect(pending.calls).toBe(1))
    await waitFor(() => expect(result.current.isPending).toBe(true))

    await act(async () => {
      pending.release()
      await first
    })
    await settle()
    expect(result.current.answer).toEqual(answerBody)
    expect(pending.calls).toBe(1)
  })

  it('после завершения можно спрашивать снова', async () => {
    const asked = countingAsk()
    const { result } = mountAsk()
    await submit(result, 'первый вопрос')
    await submit(result, 'второй вопрос')
    expect(asked.calls).toBe(2)
  })

  it('cancel: запрос прерван, pending снят, failure.kind = cancelled, второго запроса нет', async () => {
    const pending = gatedAsk()
    const { result } = mountAsk()

    let asked!: Promise<AssistantAnswer | undefined>
    act(() => {
      asked = result.current.ask('долгий вопрос')
    })
    await waitFor(() => expect(pending.calls).toBe(1))
    await waitFor(() => expect(result.current.isPending).toBe(true))

    act(() => result.current.cancel())
    await act(async () => {
      await expect(asked).resolves.toBeUndefined()
    })
    await settle()

    expect(pending.aborted).toBe(true)
    expect(result.current.isPending).toBe(false)
    expect(result.current.failure?.kind).toBe('cancelled')
    expect(result.current.failure?.message).toBe('')
    expect(pending.calls).toBe(1)

    // После отмены хук готов к новому вопросу.
    const next = countingAsk()
    await submit(result, 'новый вопрос')
    expect(next.calls).toBe(1)
    expect(result.current.answer).toEqual(answerBody)
    expect(result.current.failure).toBeUndefined()
  })

  describe('эфемерность ответа', () => {
    it('ничего не пишется в localStorage и sessionStorage', async () => {
      countingAsk()
      const { result } = mountAsk()
      await submit(result, 'где отставание')
      expect(result.current.answer).toBeDefined()
      expect(localStorage.length).toBe(0)
      expect(sessionStorage.length).toBe(0)
    })

    it('reset() убирает ответ и отказ', async () => {
      countingAsk()
      const { result } = mountAsk()
      await submit(result, 'где отставание')
      expect(result.current.answer).toBeDefined()

      act(() => result.current.reset())
      await settle()
      expect(result.current.answer).toBeUndefined()
      expect(result.current.failure).toBeUndefined()
    })

    it('смена siteId убирает ответ', async () => {
      countingAsk()
      const { result, rerender } = mountAsk()
      await submit(result, 'где отставание')
      expect(result.current.answer).toBeDefined()

      rerender({ id: OTHER_SITE })
      await waitFor(() => expect(result.current.answer).toBeUndefined())
    })

    it('смена siteId во время ожидания: запрос прерван, поздний ответ не появляется', async () => {
      const pending = gatedAsk()
      const { result, rerender } = mountAsk()

      let asked!: Promise<AssistantAnswer | undefined>
      act(() => {
        asked = result.current.ask('долгий вопрос')
      })
      await waitFor(() => expect(pending.calls).toBe(1))

      rerender({ id: OTHER_SITE })
      await waitFor(() => expect(result.current.isPending).toBe(false))
      expect(pending.aborted).toBe(true)

      await act(async () => {
        pending.release()
        await asked
      })
      await settle()
      expect(result.current.answer).toBeUndefined()
      expect(result.current.failure).toBeUndefined()
    })

    it("инвалидация ['site', id, …] убирает ответ, чужой стройки — нет", async () => {
      countingAsk()
      const { result, client } = mountAsk()
      client.setQueryData(['site', BEREZNIKI, 'schedule'], {})
      client.setQueryData(['site', OTHER_SITE, 'schedule'], {})
      await submit(result, 'где отставание')
      expect(result.current.answer).toBeDefined()

      await act(async () => {
        await client.invalidateQueries({ queryKey: ['site', OTHER_SITE] })
      })
      await settle()
      expect(result.current.answer).toBeDefined()

      await act(async () => {
        await client.invalidateQueries({ queryKey: ['site', BEREZNIKI] })
      })
      await waitFor(() => expect(result.current.answer).toBeUndefined())
    })

    it('инвалидация во время ожидания прерывает запрос, поздний ответ не появляется', async () => {
      const pending = gatedAsk()
      const { result, client } = mountAsk()
      client.setQueryData(['site', BEREZNIKI, 'schedule'], {})

      let asked!: Promise<AssistantAnswer | undefined>
      act(() => {
        asked = result.current.ask('долгий вопрос')
      })
      await waitFor(() => expect(pending.calls).toBe(1))

      await act(async () => {
        await client.invalidateQueries({ queryKey: ['site', BEREZNIKI] })
      })
      await waitFor(() => expect(pending.aborted).toBe(true))
      await waitFor(() => expect(result.current.isPending).toBe(false))

      await act(async () => {
        pending.release()
        await asked
      })
      await settle()
      expect(result.current.answer).toBeUndefined()
    })
  })

  it('размонтирование во время ожидания: запрос прерван, предупреждений React нет', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const pending = gatedAsk()
    const { result, unmount } = mountAsk()

    let asked!: Promise<AssistantAnswer | undefined>
    act(() => {
      asked = result.current.ask('долгий вопрос')
    })
    await waitFor(() => expect(pending.calls).toBe(1))

    unmount()
    await waitFor(() => expect(pending.aborted).toBe(true))

    pending.release()
    await expect(asked).resolves.toBeUndefined()
    expect(consoleError).not.toHaveBeenCalled()
  })

  it('сценарий slow в тестах отвечает без задержки', async () => {
    db.setAssistantScenario('slow')
    const { result } = mountAsk()
    await submit(result, 'что с этапами')
    expect(result.current.answer).toBeDefined()
  })
})
