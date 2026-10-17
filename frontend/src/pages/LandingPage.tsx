import { useRef } from 'react'
import { Link, Navigate } from 'react-router'
import { Logo } from '@/components/ui/Logo'
import { ConstructionScene } from '@/features/landing/ConstructionScene'
import { GanttBackdrop } from '@/features/landing/GanttBackdrop'
import { useCursorParallax } from '@/features/landing/useParallax'
import { useMediaQuery } from '@/features/landing/useMediaQuery'
import { useScrolledPast } from '@/features/landing/useScrolledPast'
import { getToken } from '@/lib/authStorage'
import styles from './LandingPage.module.css'

/** К графику листаем плавно, если система не просит «уменьшить движение». */
function scrollToSchedule() {
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  document.getElementById('schedule')?.scrollIntoView?.({ behavior: reduce ? 'auto' : 'smooth' })
}

/**
 * Первая страница для гостя: что такое Веха и вход. Вошедшего сразу ведём к стройкам.
 * На компьютере первый экран — оффер и кран, который собирает башню из этапов; край второго экрана
 * (график работ с бегущей линией «сегодня») выглядывает снизу как подсказка листать. На телефоне
 * остаётся только график фоном. Все слои с `data-depth` едут за курсором.
 */
export function LandingPage() {
  const page = useRef<HTMLDivElement>(null)
  const cta = useRef<HTMLDivElement>(null)
  useCursorParallax(page)
  // Кран только для компьютера: на телефоне остаётся график фоном с параллаксом, сцена не создаётся.
  const desktop = useMediaQuery('(width >= 1100px)')
  // Прокрутили мимо кнопок оффера — они переезжают в правый верхний угол.
  const docked = useScrolledPast(cta)
  if (getToken()) return <Navigate to="/sites" replace />

  return (
    <div ref={page} className={styles.page}>
      {desktop ? null : (
        <>
          <GanttBackdrop />
          <div className={styles.veil} aria-hidden="true" />
        </>
      )}

      <div className={styles.screen}>
        {desktop ? (
          <div className={styles.dock}>
            <div className={styles.scene}>
              <ConstructionScene />
            </div>
          </div>
        ) : null}

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
            Веха сверяет снимки с площадки с графиком работ: какая техника работает, какие этапы
            идут по плану, а какие отстают и на сколько.
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
          <div ref={cta} className={styles.cta}>
            <Link to="/login" className={styles.primary}>
              Войти
            </Link>
            <Link to="/register" className={styles.ghost}>
              Зарегистрироваться
            </Link>
          </div>
        </main>

        {desktop ? (
          <button type="button" className={styles.cue} onClick={scrollToSchedule}>
            Смотреть график
            <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
              <path d="M3 6l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.6" />
            </svg>
          </button>
        ) : null}
      </div>

      {desktop ? (
        <section id="schedule" className={styles.schedule}>
          <GanttBackdrop />
          <div className={styles.veil} aria-hidden="true" />
          <div className={styles.scheduleHead} data-depth="0.5">
            <h2 className={styles.scheduleTitle}>Отставание видно на графике</h2>
            <p className={styles.scheduleLead}>
              Серым показан план, цветом — что реально сделано по снимкам. Красные этапы отстают, и
              рядом написано, на сколько дней.
            </p>
          </div>
          <aside className={styles.legend} data-depth="0.8" aria-label="Как читать график">
            <h3 className={styles.legendTitle}>Как читать график</h3>
            <ul className={styles.legendList}>
              <li>
                <i className={`${styles.swatch} ${styles.swPlan}`} />
                План этапа
              </li>
              <li>
                <i className={`${styles.swatch} ${styles.swOk}`} />
                Сделано по снимкам, всё по плану
              </li>
              <li>
                <i className={`${styles.swatch} ${styles.swAhead}`} />
                Идёт с опережением
              </li>
              <li>
                <i className={`${styles.swatch} ${styles.swLate}`} />
                Отстаёт, в подписи сколько дней
              </li>
              <li>
                <i className={`${styles.swatch} ${styles.swToday}`} />
                Сегодняшний день
              </li>
            </ul>
          </aside>
        </section>
      ) : null}

      <div
        className={`${styles.floatCta} ${docked ? styles.floatCtaShown : ''}`}
        aria-hidden={!docked}
        inert={!docked}
      >
        <Link to="/login" className={styles.primary}>
          Войти
        </Link>
        <Link to="/register" className={styles.ghost}>
          Зарегистрироваться
        </Link>
      </div>
    </div>
  )
}
