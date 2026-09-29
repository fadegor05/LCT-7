/**
 * История переписки с ассистентом: по одной на стройку, хранится в localStorage браузера.
 * Хранилище может быть недоступно (приватный режим, запрет сайта) — тогда история живёт
 * только до перезагрузки страницы, интерфейс от этого не ломается.
 */
import { useCallback, useEffect, useState } from 'react'
import { z } from 'zod'
import { assistantAnswerSchema } from '@/api/schemas'

/** Сколько последних сообщений хранить на стройку: localStorage не резиновый. */
export const CHAT_HISTORY_LIMIT = 100

const failureKindSchema = z.enum([
  'unavailable',
  'timeout',
  'rate_limited',
  'out_of_scope',
  'too_large',
  'not_found',
  'invalid_question',
  'bad_request',
  'cancelled',
  'unknown',
])

const chatMessageSchema = z.discriminatedUnion('role', [
  z.object({ id: z.string(), at: z.string(), role: z.literal('user'), text: z.string() }),
  z.object({
    id: z.string(),
    at: z.string(),
    role: z.literal('assistant'),
    answer: assistantAnswerSchema,
  }),
  z.object({
    id: z.string(),
    at: z.string(),
    role: z.literal('failure'),
    kind: failureKindSchema,
    title: z.string(),
    text: z.string(),
    /** Вопрос, на который не ответили: по нему работает «Повторить». */
    question: z.string(),
    retryable: z.boolean(),
  }),
])

export type ChatMessage = z.infer<typeof chatMessageSchema>
type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never
export type NewChatMessage = DistributiveOmit<ChatMessage, 'id' | 'at'>

export const chatStorageKey = (siteId: string) => `lct7:assistant-chat:${siteId}`

/** Читает историю стройки; битые или чужие данные молча отбрасываются. */
export function loadChat(siteId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(chatStorageKey(siteId))
    if (!raw) return []
    const parsed = z.array(chatMessageSchema).safeParse(JSON.parse(raw))
    return parsed.success ? parsed.data : []
  } catch {
    return []
  }
}

/** Сохраняет историю стройки; пустая история удаляет ключ. */
export function saveChat(siteId: string, messages: readonly ChatMessage[]): void {
  try {
    const key = chatStorageKey(siteId)
    if (messages.length === 0) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(messages.slice(-CHAT_HISTORY_LIMIT)))
  } catch {
    // Хранилище недоступно или переполнено — история останется только в памяти.
  }
}

let counter = 0
const newId = () => `${Date.now().toString(36)}-${(counter++).toString(36)}`

/**
 * История чата стройки `siteId`: читается из localStorage при монтировании и смене стройки,
 * каждое изменение сразу записывается обратно.
 */
export function useChatHistory(siteId: string) {
  const [state, setState] = useState(() => ({ siteId, messages: loadChat(siteId) }))

  // Смена стройки: подгружаем её историю прямо в рендере, чтобы не мигнуть чужой перепиской.
  let current = state
  if (state.siteId !== siteId) {
    current = { siteId, messages: loadChat(siteId) }
    setState(current)
  }

  useEffect(() => saveChat(state.siteId, state.messages), [state])

  const append = useCallback((message: NewChatMessage) => {
    const full = { ...message, id: newId(), at: new Date().toISOString() }
    setState((prev) => ({
      ...prev,
      messages: [...prev.messages, full].slice(-CHAT_HISTORY_LIMIT),
    }))
  }, [])

  const remove = useCallback((id: string) => {
    setState((prev) => ({ ...prev, messages: prev.messages.filter((m) => m.id !== id) }))
  }, [])

  const clear = useCallback(() => setState((prev) => ({ ...prev, messages: [] })), [])

  return { messages: current.messages, append, remove, clear }
}
