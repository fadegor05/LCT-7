import type { Observation, ObservedEquipment } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { ConfidenceMeter } from '@/components/ui/ConfidenceMeter'
import { Icon } from '@/components/ui/Icon'
import { Pill } from '@/components/ui/Pill'
import { activityLabels, levelLabels } from '@/lib/labels'
import styles from './Observations.module.css'

function ActivityBadge({ item }: { item: ObservedEquipment }) {
  const label = activityLabels[item.activity]
  if (item.activity === 'works')
    return (
      <Pill tone="ontrack" icon="check">
        {label}
      </Pill>
    )
  if (item.activity === 'idle') {
    return (
      <Pill tone="caution" icon="clock">
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

/** «Техника на площадке» за дату: не менее N (максимум по снимкам), активность и уверенность. */
export function EquipmentList({ observation }: { observation: Observation }) {
  const items = observation.equipment
  return (
    <Card>
      <div>
        <h3>Техника на площадке</h3>
        <p className="sm muted">
          Наблюдаемость {levelLabels[observation.observability].toLowerCase()}
          {observation.observability_notes && ` · ${observation.observability_notes}`}
        </p>
      </div>
      {items.length === 0 ? (
        <p className="muted">
          Техники на снимках не найдено. Снимок без находок — тоже наблюдение.
        </p>
      ) : (
        <ul className={styles.equipment}>
          {items.map((item) => (
            <li key={item.equipment_type_id} className={styles.equipmentRow}>
              <span className={styles.name}>
                <Icon name="truck" size={24} />
                <span className="lab">{item.equipment_title}</span>
              </span>
              <span className="sm">не менее {item.count_min}</span>
              <span>
                <ActivityBadge item={item} />
              </span>
              <ConfidenceMeter level={item.confidence} />
            </li>
          ))}
        </ul>
      )}
      <p className="sm muted">
        Число берётся как максимум по снимкам, а не сумма: одна машина, снятая с нескольких
        ракурсов, остаётся одной. Активность по снимкам без камер определяется только как «работает»
        или «неизвестно».
      </p>
    </Card>
  )
}
