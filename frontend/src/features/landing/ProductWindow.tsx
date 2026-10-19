import { Pill } from '@/components/ui/Pill'
import styles from './ProductWindow.module.css'

const ROWS = [
  {
    stage: 'Устройство свай',
    plan: 'до 31.07.2023',
    fact: 'буровые видны 14.08',
    tone: 'behind',
    icon: 'clock',
    status: 'Отставание 14–43 дня',
  },
  {
    stage: 'Ограждение котлована: шпунт',
    plan: 'с 01.07.2023',
    fact: 'техники этапа нет',
    tone: 'outline',
    icon: 'circle',
    status: 'Не начат',
  },
] as const

/**
 * Экран «Обзор» Вехи на данных p03, собранный из тех же бейджей, что и в приложении.
 * Это картинка, а не интерфейс: читателю он не нужен, поэтому `role="img"`.
 */
export function ProductWindow() {
  return (
    <div
      className={styles.win}
      role="img"
      aria-label="Экран «Обзор» Вехи: площадка p03, отставание от 14 до 43 дней, два этапа со статусами"
    >
      <div className={styles.bar} aria-hidden="true">
        <i />
        <i />
        <i />
        <span>snmpsh.ru / sites / p03</span>
      </div>
      <div className={styles.body} aria-hidden="true">
        <div className={styles.head}>
          <b>Площадка p03</b>
          <span>Москва · срез от 13.10.2023</span>
          <nav>
            <u>Обзор</u>
            <span>Наблюдения</span>
            <span>Методика</span>
          </nav>
        </div>
        <div className={styles.cards}>
          <div className={styles.summary}>
            <small>Итог по объекту</small>
            <strong>Отставание 14–43 дня</strong>
            <span>Худший интервал по этапам. Точность не выше частоты съёмки.</span>
          </div>
          <dl className={styles.data}>
            <div>
              <dt>Наблюдаемость</dt>
              <dd>Средняя</dd>
            </div>
            <div>
              <dt>Всего снимков</dt>
              <dd>12</dd>
            </div>
            <div>
              <dt>Последний снимок</dt>
              <dd>13.10.2023</dd>
            </div>
            <div>
              <dt>Дней наблюдений</dt>
              <dd>5</dd>
            </div>
          </dl>
        </div>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Этап</th>
              <th>План</th>
              <th>Факт по снимкам</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r.stage}>
                <td>{r.stage}</td>
                <td>{r.plan}</td>
                <td>{r.fact}</td>
                <td>
                  <Pill tone={r.tone} icon={r.icon} size="sm">
                    {r.status}
                  </Pill>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
