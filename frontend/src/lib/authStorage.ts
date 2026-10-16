/**
 * Управление токеном доступа в localStorage.
 * Все операции обёрнуты в try/catch чтобы не упасть если localStorage недоступен.
 */

const TOKEN_KEY = 'lct7.token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // localStorage недоступен; ошибка уже залогирована браузером
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    // localStorage недоступен; ошибка уже залогирована браузером
  }
}
