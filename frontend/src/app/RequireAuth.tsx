import { Navigate, Outlet, useLocation } from 'react-router'
import { AppLayout } from '@/components/layout/AppLayout'
import { getToken } from '@/lib/authStorage'

/** Проверка аутентификации перед доступом к защищённым маршрутам. */
/** `bare` — без шапки приложения: отчёт A4 — отдельный документ, как в clean-mvp. */
export function RequireAuth({ bare = false }: { bare?: boolean }) {
  const location = useLocation()
  const token = getToken()

  if (!token) {
    const from = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to="/login" state={{ from }} replace />
  }

  return bare ? <Outlet /> : <AppLayout />
}
