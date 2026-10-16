import { Navigate, useLocation } from 'react-router'
import { AppLayout } from '@/components/layout/AppLayout'
import { getToken } from '@/lib/authStorage'

/** Проверка аутентификации перед доступом к защищённым маршрутам. */
export function RequireAuth() {
  const location = useLocation()
  const token = getToken()

  if (!token) {
    const from = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to="/login" state={{ from }} replace />
  }

  return <AppLayout />
}
