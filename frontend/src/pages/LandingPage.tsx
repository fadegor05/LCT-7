import { Link, Navigate } from 'react-router'
import { Logo } from '@/components/ui/Logo'
import { GanttBackdrop } from '@/features/landing/GanttBackdrop'
import { getToken } from '@/lib/authStorage'
import styles from './LandingPage.module.css'

/** Первая страница для гостя: что такое Веха и вход. Вошедшего сразу ведём к стройкам. */
export function LandingPage() {
  if (getToken()) return <Navigate to="/sites" replace />

  return (
    <div className={styles.page}>
      <GanttBackdrop />
      <div className={styles.veil} aria-hidden="true" />

      <header className={styles.top}>
        <span className={styles.brand}>
          <Logo />
          Веха
        </span>
      </header>

      <main className={styles.hero}>
        <p className={styles.eyebrow}>Контроль строительства по снимкам</p>
        <h1 className={styles.title}>Видно, где стройка отстаёт от графика</h1>
        <p className={styles.lead}>
          Веха сверяет снимки с площадки с графиком работ: какая техника работает, какие этапы идут
          по плану, а какие отстают и на сколько.
        </p>
        <ol className={styles.steps}>
          <li>
            <b>01</b>Загрузите график работ из CSV или XLSX
          </li>
          <li>
            <b>02</b>Добавьте снимки с площадки — дата берётся из файла
          </li>
          <li>
            <b>03</b>Получите отклонения с доказательствами на снимках
          </li>
        </ol>
        <div className={styles.cta}>
          <Link to="/login" className={styles.primary}>
            Войти
          </Link>
          <Link to="/register" className={styles.ghost}>
            Зарегистрироваться
          </Link>
        </div>
      </main>
    </div>
  )
}
