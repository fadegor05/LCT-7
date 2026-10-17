import { useEffect } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router'
import { Button } from '@/components/ui/Button'
import { Logo } from '@/components/ui/Logo'
import { useMe } from '@/api/auth'
import { clearToken } from '@/lib/authStorage'
import { setUnauthorizedHandler } from '@/api/client'
import { env } from '@/lib/env'
import { useQueryClient } from '@tanstack/react-query'
import styles from './AppLayout.module.css'

export function AppLayout() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const me = useMe()

  // Initialize unauthorized handler once when AppLayout mounts
  useEffect(() => {
    setUnauthorizedHandler(() => {
      void qc.clear()
      void navigate('/login', { replace: true })
    })
  }, [navigate, qc])

  const handleLogout = () => {
    clearToken()
    void qc.clear()
    // Вышли сами — возвращаем на лендинг, а не на форму входа.
    void navigate('/', { replace: true })
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <Link to="/sites" className={styles.logo}>
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
          {me.data && <span className={styles.userName}>{me.data.full_name}</span>}
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
