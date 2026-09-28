/**
 * Ассистент: API функции, классификация ошибок, хуки useAssistantStatus и useAskAssistant.
 * Ошибки типизированы по `code` из ответа backend, который отражает причину отказа.
 * Ответы эфемерны: хранятся только в мутации, очищаются при смене стройки или инвалидации
 * кэша запросов этой стройки.
 */
import { useCallback, useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, request } from './client'
import { keys } from './keys'
import {
  assistantAnswerSchema,
  assistantQuestionSchema,
  assistantStatusSchema,
  type AssistantAnswer,
} from './schemas'

/** Виды отказов ассистента: интерфейс рисует их по `kind`, статусы и коды не разбирает. */
export type AssistantFailureKind =
  | 'unavailable'
  | 'timeout'
  | 'rate_limited'
  | 'out_of_scope'
  | 'too_large'
  | 'not_found'
  | 'invalid_question'
  | 'bad_request'
  | 'cancelled'
  | 'unknown'

export interface AssistantFailure {
  kind: AssistantFailureKind
  /** Текст для пользователя: по-русски; у `cancelled` пустой. */
  message: string
  /** Есть ли смысл предложить «Повторить» (только таймаут модели). */
  retryable: boolean
}

const QUESTION_HINT = 'Вопрос должен быть от 3 до 500 символов'
const UNKNOWN_MESSAGE = 'Не удалось получить ответ'

const failure = (
  kind: AssistantFailureKind,
  message: string,
  retryable = false,
): AssistantFailure => ({ kind, message, retryable })

/** Отмена запроса: имя `AbortError` у DOMException и у ошибок из других окружений (Node, jsdom). */
function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' && error !== null && 'name' in error && error.name === 'AbortError'
  )
}

/**
 * Разбирает ошибку ассистента в вид для интерфейса.
 * Порядок: отмена → ApiError (по `code`, затем по статусу) → отказ fetch → прочее.
 * Текст для пользователя — русский `detail` сервера; общие тексты — для валидации, сети и неизвестного.
 */
export function classifyAssistantError(error: unknown): AssistantFailure {
  if (isAbortError(error)) return failure('cancelled', '')

  if (error instanceof ApiError) {
    switch (error.code) {
      case 'assistant_unavailable':
        return failure('unavailable', error.message)
      case 'assistant_timeout':
        return failure('timeout', error.message, true)
      case 'rate_limited':
        return failure('rate_limited', error.message)
      case 'out_of_scope':
        return failure('out_of_scope', error.message)
      case 'report_too_large':
        return failure('too_large', error.message)
      case 'assistant_bad_request':
        return failure('bad_request', error.message)
      case undefined:
        // Без кода: 404 — нет стройки или графика, 422 — валидация вопроса (список в `detail`).
        if (error.status === 404) return failure('not_found', error.message)
        if (error.status === 422) return failure('invalid_question', QUESTION_HINT)
        return failure('unknown', UNKNOWN_MESSAGE)
      default:
        return failure('unknown', UNKNOWN_MESSAGE)
    }
  }

  // fetch отклонён: нет сети, сервер не отвечает.
  if (error instanceof TypeError) return failure('unavailable', 'Нет связи с сервером')

  return failure('unknown', UNKNOWN_MESSAGE)
}

export const assistantApi = {
  /** Включён ли ассистент: ML доступен и LLM настроена. Платный вызов не тратит. */
  status: (signal?: AbortSignal) =>
    request('/assistant/status', { schema: assistantStatusSchema, signal }),

  /** Вопрос по отчёту стройки. Каждый вызов — платный запрос к модели. */
  ask: (siteId: string, question: string, signal?: AbortSignal) =>
    request(`/sites/${siteId}/assistant/ask`, {
      method: 'POST',
      body: { question },
      schema: assistantAnswerSchema,
      signal,
    }),
}

/**
 * Доступность ассистента для интерфейса. Любая ошибка (сеть, 5xx, битый контракт) — `enabled: false`:
 * ассистента просто нет, а не «сломанная кнопка». Без повторов: статус не должен долбить сервер.
 */
export function useAssistantStatus() {
  const { data, isPending } = useQuery({
    queryKey: keys.assistantStatus,
    queryFn: ({ signal }) => assistantApi.status(signal),
    retry: false,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })
  return { enabled: data?.enabled === true, isPending }
}

/** Ключ запроса относится к стройке `siteId`: `['site', siteId, …]`. */
function belongsToSite(queryKey: readonly unknown[], siteId: string): boolean {
  return queryKey[0] === 'site' && queryKey[1] === siteId
}

/**
 * Вопрос ассистенту по стройке.
 *
 * - `ask(question)` — проверяет вопрос локально (3–500 символов, trim), отправляет, возвращает
 *   ответ; при отказе или повторном нажатии во время ожидания возвращает `undefined` и не
 *   бросает исключений. Причина отказа — в `failure`.
 * - `cancel()` — отменяет ожидание; `failure.kind === 'cancelled'`, показывать его не нужно.
 * - `reset()` — убирает ответ и отказ.
 * - Ответ живёт только в состоянии хука и сбрасывается (запрос отменяется) при смене `siteId`,
 *   при инвалидации любого запроса `['site', siteId, …]` и при размонтировании.
 */
export function useAskAssistant(siteId: string) {
  const queryClient = useQueryClient()
  const inFlight = useRef(false)
  const controller = useRef<AbortController | null>(null)

  const mutation = useMutation({
    mutationKey: keys.assistant(siteId),
    retry: false,
    mutationFn: async (question: string): Promise<AssistantAnswer> => {
      const parsed = assistantQuestionSchema.safeParse(question)
      // Проверка до сети: слишком короткий или длинный вопрос на сервер не уходит.
      if (!parsed.success) throw new ApiError(422, QUESTION_HINT)

      const current = new AbortController()
      controller.current = current
      return assistantApi.ask(siteId, parsed.data, current.signal)
    },
  })
  const { mutateAsync, reset: resetMutation } = mutation

  const cancel = useCallback(() => controller.current?.abort(), [])

  // Отмена и сброс: запрос прерывается, а результат уже отвязанной мутации в состояние не попадает.
  // Эффекты ниже вызывают её через ref: их зависимости — только `siteId`, и перерисовка
  // (например, из-за смены состояния мутации) не должна обрывать идущий запрос.
  const discardRef = useRef(() => {})
  useEffect(() => {
    discardRef.current = () => {
      controller.current?.abort()
      resetMutation()
    }
  }, [resetMutation])

  const ask = useCallback(
    async (question: string): Promise<AssistantAnswer | undefined> => {
      if (inFlight.current) return undefined
      inFlight.current = true
      try {
        return await mutateAsync(question)
      } catch {
        return undefined // причина в mutation.error → failure
      } finally {
        inFlight.current = false
      }
    },
    [mutateAsync],
  )

  // Смена стройки и размонтирование: чужой ответ показывать нельзя.
  useEffect(() => () => discardRef.current(), [siteId])

  // Правка входных данных стройки (любой запрос ['site', siteId, …] инвалидирован) — ответ устарел.
  useEffect(
    () =>
      queryClient.getQueryCache().subscribe((event) => {
        if (
          event.type === 'updated' &&
          event.action.type === 'invalidate' &&
          belongsToSite((event.query as { queryKey: readonly unknown[] }).queryKey, siteId)
        ) {
          discardRef.current()
        }
      }),
    [queryClient, siteId],
  )

  return {
    ask,
    cancel,
    reset: resetMutation,
    isPending: mutation.isPending,
    answer: mutation.data,
    failure: mutation.error ? classifyAssistantError(mutation.error) : undefined,
  }
}
