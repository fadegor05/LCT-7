import type { StageStatusValue } from '@/api/schemas'
import { StatusBadge } from '@/components/ui/StatusBadge'
import styles from './Overview.module.css'

// Правила — как в движке (backend/app/domains/assessment/engine.py), как в clean-mvp
const RULES: { status: StageStatusValue; text: string }[] = [
  {
    status: 'on_track',
    text: 'Маркер этапа появился в пределах 3 дней от планового начала, и после планового конца этап не затянулся.',
  },
  { status: 'ahead', text: 'Маркер появился больше чем на 3 дня раньше планового начала.' },
  {
    status: 'behind',
    text: 'Этап начался позже плана больше чем на 3 дня или его техника на площадке после планового конца. Задержка — интервалом: даты известны с точностью до частоты съёмки.',
  },
  {
    status: 'not_started',
    text: 'Плановое начало прошло, а маркера нет 3 рабочие даты подряд при высокой наблюдаемости.',
  },
  {
    status: 'not_observed',
    text: 'Снимков мало, наблюдаемость низкая или этап не отличить по технике от идущих одновременно: судить об этапе нельзя.',
  },
  {
    status: 'not_checked',
    text: 'У этапа нет техники, которую различает детектор, нет плановых дат или проверка отключена в методике.',
  },
]

/** Легенда статусов под таблицей «Этапы»: почему у этапа такой статус (как в clean-mvp). */
export function StatusLegend() {
  return (
    <details className={styles.legend} aria-label="Как выбирается статус этапа">
      <summary className="sm">Как выбирается статус этапа</summary>
      <p className="sm muted">
        Маркер — техника, которая отличает этап от идущих одновременно (нормативная по ГЭСН). Он
        задаёт фактические даты этапа. Если маркера нет, этап виден только по всему комплекту
        техники.
      </p>
      <ul className={styles.legendList}>
        {RULES.map((r) => (
          <li key={r.status} className={styles.legendRow}>
            <span data-part="badge">
              <StatusBadge status={r.status} />
            </span>
            <span className="sm">{r.text}</span>
          </li>
        ))}
      </ul>
    </details>
  )
}
