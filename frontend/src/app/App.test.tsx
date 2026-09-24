import { render, screen } from '@testing-library/react'
import { ApiError } from '@/api/client'
import { App } from './App'
import { createQueryClient } from './queryClient'

describe('App', () => {
  it('boots with the router and query client', async () => {
    window.history.pushState({}, '', '/sites')
    render(<App />)
    expect(await screen.findByRole('heading', { level: 1, name: 'Стройки' })).toBeInTheDocument()
  })
})

describe('createQueryClient', () => {
  it('does not retry client errors and retries others twice', () => {
    const retry = createQueryClient().getDefaultOptions().queries!.retry as (
      n: number,
      e: unknown,
    ) => boolean
    expect(retry(0, new ApiError(404, 'нет'))).toBe(false)
    expect(retry(0, new ApiError(503, 'сбой'))).toBe(true)
    expect(retry(1, new Error('сеть'))).toBe(true)
    expect(retry(2, new Error('сеть'))).toBe(false)
  })
})
