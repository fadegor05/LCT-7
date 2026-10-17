import { Link } from 'react-router'
import { ProductWindow } from './ProductWindow'
import styles from './Hero.module.css'

/**
 * Первый экран: заголовок, пояснение и кнопки слева, ниже окно продукта на настоящем снимке
 * площадки p03. Окно выезжает снизу один раз при загрузке (при «меньше движения» стоит на месте).
 */
export function Hero() {
  return (
    <section className={styles.hero} aria-label="Веха">
      <div className={styles.top}>
        <h1 className={styles.title}>Видно, где стройка отстаёт от графика</h1>
        <p className={styles.lead}>
          <b>Веха сверяет обычные снимки с площадки с календарным графиком.</b> Показывает
          отставание в днях и кадры, по которым сделан вывод. Без BIM и без обхода площадки с
          камерой.
        </p>
        <div className={styles.cta}>
          <a href="#timeline" className={styles.primary}>
            Посмотреть пример
          </a>
          <Link to="/register" className={styles.ghost}>
            Попробовать на своём графике
          </Link>
        </div>
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
