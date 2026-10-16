import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { ApiError } from './client'
import { useLogin, useMe } from './auth'
import { getToken, clearToken, setToken } from '@/lib/authStorage'
import { createTestQueryClient } from '@/test/render'

describe('useLogin hook', () => {
  beforeEach(() => {
    clearToken()
    localStorage.clear()
  })

  it('successful login stores token and returns user', async () => {
    const queryClient = createTestQueryClient()
    const { result } = renderHook(() => useLogin(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    })

    result.current.mutate({ login: 'demo', password: 'demo' })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.access_token).toBe('mock-token')
    expect(result.current.data?.user?.full_name).toBe('инженер [ФИО]')
    expect(getToken()).toBe('mock-token')
  })

  it('wrong credentials rejects with 401 and does not store token', async () => {
    const queryClient = createTestQueryClient()
    const { result } = renderHook(() => useLogin(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    })

    result.current.mutate({ login: 'wrong', password: 'wrong' })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeInstanceOf(ApiError)
    expect((result.current.error as ApiError).status).toBe(401)
    expect(getToken()).toBe(null)
  })
})

describe('useMe hook', () => {
  beforeEach(() => {
    clearToken()
    localStorage.clear()
  })

  it('returns user when authenticated', async () => {
    const queryClient = createTestQueryClient()
    setToken('mock-token')

    const { result } = renderHook(() => useMe(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.full_name).toBe('инженер [ФИО]')
  })

  it('returns 401 error when not authenticated', async () => {
    const queryClient = createTestQueryClient()
    clearToken()

    const { result } = renderHook(() => useMe(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeInstanceOf(ApiError)
    expect((result.current.error as ApiError).status).toBe(401)
  })
})
