import { Link } from 'react-router'
import type { ObservationEquipment } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { Icon } from '@/components/ui/Icon'
import { Pill } from '@/components/ui/Pill'
import { activityLabels } from '@/lib/labels'
import styles from './Observations.module.css'

function ActivityBadge({ item }: { item: ObservationEquipment }) {
  const label = activityLabels[item.activity]
  if (item.activity === 'working')
    return (
      <Pill tone="ontrack" icon="check">
        {label}
      </Pill>
    )
  if (item.activity === 'idle') {
    return (
      <Pill tone={item.activity_hypothesis ? 'cautionDashed' : 'caution'} icon="clock">
        {label}
      </Pill>
    )
  }
  return (
    <Pill tone="neutral" icon="minus">
      {label}
    </Pill>
  )
}

interface EquipmentListProps {
  siteId: string
  stageName: string | null
  items: readonly ObservationEquipment[]
}

/** «Техника на площадке» за дату: не менее N (максимум по кадрам), активность и основание. */
export function EquipmentList({ siteId, stageName, items }: EquipmentListProps) {
  return (
    <Card>
      <div>
        <h3>Техника на площадке</h3>
        {stageName && <p className="sm muted">Этап: {stageName}</p>}
      </div>
      {items.length === 0 ? (
        <p className="muted">Техники на кадрах не найдено. Кадр без находок — тоже наблюдение.</p>
      ) : (
        <ul className={styles.equipment}>
          {items.map((item) => (
            <li key={item.equipment_class} className={styles.equipmentRow}>
              <span className={styles.name}>
                <Icon name="truck" size={24} />
                <span className="lab">{item.name}</span>
              </span>
              <span className="sm">не менее {item.min_count}</span>
              <span>
                {item.deviation_id ? (
                  <Link
                    to={`/sites/${siteId}/deviations/${item.deviation_id}`}
                    className={styles.activityLink}
                    aria-label={`${item.name}: ${activityLabels[item.activity]} — открыть отклонение`}
                  >
                    <ActivityBadge item={item} />
                  </Link>
                ) : (
                  <ActivityBadge item={item} />
                )}
              </span>
              <span className="sm muted">{item.basis_text}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="sm muted">
        Число берётся как максимум по кадрам, а не сумма: одна машина, снятая с нескольких ракурсов,
        остаётся одной. Активность: есть движение, значит работает; нет движения и вне зоны на серии
        кадров, значит простой (гипотеза); иначе неизвестно.
      </p>
    </Card>
  )
}
