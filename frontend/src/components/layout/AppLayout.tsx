import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { Button } from '@/components/ui/Button'
import { Logo } from '@/components/ui/Logo'
import { NotificationBell } from '@/features/notifications/NotificationBell'
import { useMe } from '@/api/auth'
import { clearToken } from '@/lib/authStorage'
import { setUnauthorizedHandler } from '@/api/client'
import { clearImageCache } from '@/api/images'
import { env } from '@/lib/env'
import { useQueryClient } from '@tanstack/react-query'
import styles from './AppLayout.module.css'

export function AppLayout() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const me = useMe()
  // Новый раздел открывается сверху: иначе вкладка наследует прокрутку прошлой и прыгает,
  // когда подгружается. Смена `?date=` прокрутку не трогает; к `#якорю` страницы
  // прокручивают сами (как в clean-mvp)
  const { pathname, hash } = useLocation()
  useEffect(() => {
    if (!hash) window.scrollTo(0, 0)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- только при смене раздела
  }, [pathname])

  // Initialize unauthorized handler once when AppLayout mounts
  useEffect(() => {
    setUnauthorizedHandler(() => {
      void qc.clear()
      clearImageCache()
      void navigate('/login', { replace: true })
    })
  }, [navigate, qc])

  const handleLogout = () => {
    clearToken()
    void qc.clear()
    clearImageCache()
    // Вышли сами — возвращаем на лендинг, а не на форму входа.
    void navigate('/', { replace: true })
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        {/* state.landing — явный переход на лендинг, даже для вошедшего (см. LandingPage). */}
        <Link to="/" state={{ landing: true }} className={styles.logo}>
          <Logo />
          Веха
        </Link>
        <nav className={styles.nav} aria-label="Основная навигация">
          <NavLink to="/sites" className={styles.navLink}>
            Стройки
          </NavLink>
        </nav>
        {env.useMocks && (
          <span className={styles.mockBadge} title="Данные из MSW-моков (VITE_USE_MOCKS=true)">
            Моки
          </span>
        )}
        <div className={styles.userSection}>
          <NotificationBell />
          {me.data && (
            <Link to="/profile" className={styles.userName}>
              {me.data.full_name}
            </Link>
          )}
          <Button variant="secondary" size="sm" onClick={handleLogout}>
            Выйти
          </Button>
        </div>
      </header>
      <main className={styles.main}>
        <div className={styles.content}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
