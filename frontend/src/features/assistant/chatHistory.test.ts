import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  CHAT_HISTORY_LIMIT,
  chatStorageKey,
  loadChat,
  saveChat,
  useChatHistory,
  type ChatMessage,
} from './chatHistory'

const userMessage = (text: string, id = text): ChatMessage => ({
  id,
  at: '2026-01-01T10:00:00Z',
  role: 'user',
  text,
})

describe('chatHistory storage', () => {
  afterEach(() => vi.restoreAllMocks())

  it('round-trips messages per site', () => {
    saveChat('a', [userMessage('вопрос')])
    expect(loadChat('a')).toEqual([userMessage('вопрос')])
    expect(loadChat('b')).toEqual([])
  })

  it('drops data that does not match the schema', () => {
    localStorage.setItem(chatStorageKey('a'), JSON.stringify([{ role: 'robot' }]))
    expect(loadChat('a')).toEqual([])
  })

  it('removes the key for an empty history', () => {
    saveChat('a', [userMessage('вопрос')])
    saveChat('a', [])
    expect(localStorage.getItem(chatStorageKey('a'))).toBeNull()
  })

  it('keeps only the last messages within the limit', () => {
    const many = Array.from({ length: CHAT_HISTORY_LIMIT + 5 }, (_, i) => userMessage(`q${i}`))
    saveChat('a', many)
    const saved = loadChat('a')
    expect(saved).toHaveLength(CHAT_HISTORY_LIMIT)
    expect(saved[0]).toEqual(userMessage('q5'))
  })

  it('survives an unavailable storage', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    expect(loadChat('a')).toEqual([])
    expect(() => saveChat('a', [userMessage('вопрос')])).not.toThrow()
  })
})

describe('useChatHistory', () => {
  it('appends, removes and clears messages and mirrors them to storage', () => {
    const { result } = renderHook(() => useChatHistory('a'))
    act(() => result.current.append({ role: 'user', text: 'первый' }))
    act(() => result.current.append({ role: 'user', text: 'второй' }))
    expect(result.current.messages.map((m) => m.role === 'user' && m.text)).toEqual([
      'первый',
      'второй',
    ])
    expect(loadChat('a')).toHaveLength(2)

    act(() => result.current.remove(result.current.messages[0]!.id))
    expect(loadChat('a')).toHaveLength(1)

    act(() => result.current.clear())
    expect(result.current.messages).toEqual([])
    expect(localStorage.getItem(chatStorageKey('a'))).toBeNull()
  })

  it('switches to the other site history without leaking messages', () => {
    saveChat('b', [userMessage('вопрос по b')])
    const { result, rerender } = renderHook(({ id }) => useChatHistory(id), {
      initialProps: { id: 'a' },
    })
    act(() => result.current.append({ role: 'user', text: 'вопрос по a' }))

    rerender({ id: 'b' })
    expect(result.current.messages).toEqual([userMessage('вопрос по b')])
    expect(loadChat('a')).toHaveLength(1)

    rerender({ id: 'a' })
    expect(result.current.messages.map((m) => m.role === 'user' && m.text)).toEqual(['вопрос по a'])
  })
})
