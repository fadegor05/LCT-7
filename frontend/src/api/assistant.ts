/**
 * Ассистент: API функции, классификация ошибок, хуки useAssistantStatus и useAskAssistant.
 * Ошибки типизированы по `code` из ответа backend, который отражает причину отказа.
 * Ответы эфемерны: хранятся только в мутации, очищаются при смене стройки или инвалидации
 * кэша запросов этой стройки.
 */
import { useCallback, useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { request, ApiError } from './client'
import { keys } from './keys'
import {
  assistantAnswerSchema,
  assistantQuestionSchema,
  assistantStatusSchema,
  type AssistantAnswer,
} from './schemas'

/** Виды отказов классификация ошибок по коду backend. */
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
  message: string
  retryable: boolean
}

/**
 * Классифицирует ошибку ассистента по типу и коду, включая типы сетевых ошибок.
 * Порядок проверок:
 * 1. AbortError (имя 'AbortError') → cancelled
 * 2. ApiError → по коду и статусу
 * 3. TypeError (rejected fetch) → unavailable
 * 4. Прочее → unknown
 */
export function classifyAssistantError(error: unknown): AssistantFailure {
  // Отмена абортом (отмена пользователя или смена siteId)
  if (
    error instanceof DOMException
      ? error.name === 'AbortError'
      : error instanceof Error && error.name === 'AbortError'
  ) {
    return {
      kind: 'cancelled',
      message: '',
      retryable: false,
    }
  }

  if (error instanceof ApiError) {
    // По коду из тела ответа
    if (error.code) {
      switch (error.code) {
        case 'assistant_unavailable':
          return {
            kind: 'unavailable',
            message: error.message,
            retryable: false,
          }
        case 'assistant_timeout':
          return {
            kind: 'timeout',
            message: error.message,
            retryable: true,
          }
        case 'rate_limited':
          return {
            kind: 'rate_limited',
            message: error.message,
            retryable: false,
          }
        case 'out_of_scope':
          return {
            kind: 'out_of_scope',
            message: error.message,
            retryable: false,
          }
        case 'report_too_large':
          return {
            kind: 'too_large',
            message: error.message,
            retryable: false,
          }
        case 'assistant_bad_request':
          return {
            kind: 'bad_request',
            message: error.message,
            retryable: false,
          }
        default:
          return {
            kind: 'unknown',
            message: 'Не удалось получить ответ',
            retryable: false,
          }
      }
    }

    // Без кода — по статусу
    switch (error.status) {
      case 404:
        return {
          kind: 'not_found',
          message: error.message,
          retryable: false,
        }
      case 422:
        // 422 без code и с array detail = валидация вопроса
        return {
          kind: 'invalid_question',
          message: 'Вопрос должен быть от 3 до 500 символов',
          retryable: false,
        }
      default:
        return {
          kind: 'unknown',
          message: 'Не удалось получить ответ',
          retryable: false,
        }
    }
  }

  // Rejected fetch (TypeError)
  if (error instanceof TypeError) {
    return {
      kind: 'unavailable',
      message: 'Нет связи с сервером',
      retryable: false,
    }
  }

  // Неизвестная ошибка
  return {
    kind: 'unknown',
    message: 'Не удалось получить ответ',
    retryable: false,
  }
}

const base = '/assistant'

export const assistantApi = {
  /** GET /assistant/status — проверить, включён ли ассистент. */
  status: (signal?: AbortSignal) =>
    request(`${base}/status`, { schema: assistantStatusSchema, signal }),

  /** POST /sites/:siteId/assistant/ask — отправить вопрос. */
  ask: (siteId: string, question: string, signal?: AbortSignal) =>
    request(`/sites/${siteId}/assistant/ask`, {
      method: 'POST',
      body: { question },
      schema: assistantAnswerSchema,
      signal,
    }),
}

/** Статус ассистента: включён ли он, загружается ли запрос. Никогда не выбрасывает исключение. */
export function useAssistantStatus() {
  const { data, isPending } = useQuery({
    queryKey: keys.assistantStatus,
    queryFn: () => assistantApi.status(),
    retry: false,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })

  return {
    enabled: data?.enabled === true,
    isPending,
  }
}

/**
 * Хук для взаимодействия с ассистентом: отправка вопросов, отмена, сброс.
 *
 * - `ask(question)` — валидирует локально, отправляет вопрос, возвращает ответ или undefined;
 *   никогда не выбрасывает исключение. Локальная валидация (3-500 символов) не отправляет запрос.
 * - `cancel()` — отменяет in-flight запрос через AbortController.
 * - `reset()` — очищает ответ и ошибку.
 * - Ответ очищается при смене `siteId` или инвалидации кэша запросов [`site`, siteId].
 * - Unmount автоматически отменяет in-flight запрос (no React warnings).
 */
export function useAskAssistant(siteId: string) {
  const queryClient = useQueryClient()
  const inFlightRef = useRef(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const currentSiteIdRef = useRef(siteId)
  const isMountedRef = useRef(true)

  const {
    mutateAsync,
    data: answer,
    error: rawError,
    reset: mutationReset,
    isPending,
  } = useMutation({
    mutationKey: keys.assistant(siteId),
    mutationFn: async (question: string) => {
      // Локальная валидация перед запросом
      const parsed = assistantQuestionSchema.safeParse(question)
      if (!parsed.success) {
        // Для ошибки валидации создаём Error с классификацией в свойстве
        const validationError = new Error('validation_error')
        // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-member-access -- Храним результат классификации на ошибке
        ;(validationError as any).__failure = classifyAssistantError(validationError)
        throw validationError
      }

      // Отправляем триммированный вопрос
      const trimmedQuestion = question.trim()
      const controller = new AbortController()
      abortControllerRef.current = controller

      try {
        const result = await assistantApi.ask(siteId, trimmedQuestion, controller.signal)
        return result
      } catch (err) {
        // Классифицируем и добавляем в Error
        const error = err instanceof Error ? err : new Error(String(err))
        // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-member-access -- Храним результат классификации на ошибке
        ;(error as any).__failure = classifyAssistantError(err)
        throw error
      }
    },
  })

  // Вычисляем failure из error
  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment -- Получаем классификацию, сохранённую при броске
  const failure: AssistantFailure | undefined = rawError
    ? (rawError as any).__failure || classifyAssistantError(rawError) // eslint-disable-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-member-access
    : undefined

  // Отмена in-flight запроса
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }, [])

  // Сброс состояния
  const reset = useCallback(() => {
    mutationReset()
  }, [mutationReset])

  // Отправка вопроса: проверяем in-flight, валидируем, отправляем
  const ask = useCallback(
    async (question: string): Promise<AssistantAnswer | undefined> => {
      // Если уже идёт запрос, игнорируем
      if (inFlightRef.current) {
        return undefined
      }

      inFlightRef.current = true
      currentSiteIdRef.current = siteId

      try {
        const result = await mutateAsync(question)
        if (!isMountedRef.current) {
          inFlightRef.current = false
          return undefined
        }
        inFlightRef.current = false
        return result
      } catch {
        // Ошибка уже установлена в mutation.error, просто возвращаем undefined
        if (!isMountedRef.current) {
          inFlightRef.current = false
          return undefined
        }
        inFlightRef.current = false
        return undefined
      }
    },
    [mutateAsync, siteId],
  )

  // Наблюдаем за изменением siteId и инвалидацией кэша
  useEffect(() => {
    // Если siteId изменился, отменяем запрос и очищаем состояние
    if (currentSiteIdRef.current !== siteId) {
      cancel()
      mutationReset()
      currentSiteIdRef.current = siteId
    }

    // Подписываемся на инвалидацию кэша для этой стройки
    const unsubscribe = queryClient.getQueryCache().subscribe(() => {
      // Отменяем in-flight запрос при любой инвалидации под ['site', siteId]
      cancel()
    })

    return () => {
      unsubscribe()
    }
  }, [siteId, cancel, mutationReset, queryClient])

  // На unmount отменяем запрос (без state update)
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [])

  return {
    ask,
    cancel,
    reset,
    isPending,
    answer,
    failure,
  }
}
