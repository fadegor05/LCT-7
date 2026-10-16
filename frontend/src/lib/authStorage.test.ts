import { describe, it, expect, beforeEach, vi } from 'vitest'
import { getToken, setToken, clearToken } from './authStorage'

describe('authStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('setToken stores token in localStorage', () => {
    setToken('test-token')
    expect(localStorage.getItem('lct7.token')).toBe('test-token')
  })

  it('getToken retrieves token from localStorage', () => {
    localStorage.setItem('lct7.token', 'my-token')
    expect(getToken()).toBe('my-token')
  })

  it('getToken returns null when token not set', () => {
    expect(getToken()).toBe(null)
  })

  it('clearToken removes token from localStorage', () => {
    localStorage.setItem('lct7.token', 'test-token')
    clearToken()
    expect(localStorage.getItem('lct7.token')).toBe(null)
  })

  it('handles localStorage.getItem throwing error', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage error')
    })
    expect(() => getToken()).not.toThrow()
    expect(getToken()).toBe(null)
  })

  it('handles localStorage.setItem throwing error', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage error')
    })
    expect(() => setToken('token')).not.toThrow()
  })

  it('handles localStorage.removeItem throwing error', () => {
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('storage error')
    })
    expect(() => clearToken()).not.toThrow()
  })
})
