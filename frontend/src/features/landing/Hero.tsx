import { useRef } from 'react'
import { ButtonLink } from '@/components/ui/Button'
import { buttonClassName } from '@/components/ui/buttonClass'
import { ConstructionScene } from './ConstructionScene'
import { ProductWindow } from './ProductWindow'
import type { SignedInProps } from './Sections'
import { useMediaQuery } from './useMediaQuery'
import { useCursorParallax } from './useParallax'
import styles from './Hero.module.css'

/**
 * Первый экран: слева заголовок, пояснение и кнопки, справа башенный кран собирает башню из этапов
 * графика (цвет блока — статус). Ниже окно продукта на настоящем снимке площадки p03, оно выезжает
 * снизу один раз при загрузке. Кран только для широкого экрана, слои сцены едут за курсором.
 */
export function Hero({ signedIn = false }: SignedInProps) {
  const root = useRef<HTMLElement>(null)
  const wide = useMediaQuery('(width >= 1100px)')
  useCursorParallax(root)

  return (
    <section ref={root} className={styles.hero} aria-label="Веха">
      <div className={`${styles.top} ${wide ? styles.withCrane : ''}`}>
        <div className={styles.copy}>
          <h1 className={styles.title}>Видно, где стройка отстаёт от графика</h1>
          <p className={styles.lead}>
            <b>Веха сверяет обычные снимки с площадки с календарным графиком.</b> Показывает
            отставание в днях и кадры, по которым сделан вывод. Без BIM и без обхода площадки с
            камерой.
          </p>
          <div className={styles.cta}>
            <a href="#timeline" className={buttonClassName('primary', 'lg')}>
              Посмотреть пример
            </a>
            {signedIn ? (
              <ButtonLink to="/sites" variant="ghost" size="lg" className={styles.onWarm}>
                К стройкам
              </ButtonLink>
            ) : (
              <ButtonLink to="/register" variant="ghost" size="lg" className={styles.onWarm}>
                Попробовать на своём графике
              </ButtonLink>
            )}
          </div>
        </div>
        {wide ? (
          <div className={styles.crane}>
            <ConstructionScene />
          </div>
        ) : null}
      </div>

      <div className={styles.stage}>
        <img
          className={styles.photo}
          src="/landing/p03/hero.jpg"
          alt="Площадка p03, 19 июня 2023: буровые установки и башенные краны"
          width="1179"
          height="813"
          fetchPriority="high"
        />
        <div className={styles.window}>
          <ProductWindow />
        </div>
      </div>
    </section>
  )
}
