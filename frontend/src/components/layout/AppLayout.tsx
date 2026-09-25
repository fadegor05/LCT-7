import { Link, NavLink, Outlet } from 'react-router'
import { Logo } from '@/components/ui/Logo'
import { env } from '@/lib/env'
import styles from './AppLayout.module.css'

export function AppLayout() {
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
      </header>
      <main className={styles.main}>
        <div className={styles.content}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
