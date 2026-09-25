import type { DateSource } from '@/api/schemas'
import { dateSourceLabels } from '@/lib/labels'
import { Icon } from './Icon'
import styles from './DateSourceBadge.module.css'

type Kind = 'received' | 'inferred' | 'manual'

const KIND: Record<DateSource, Kind> = {
  channel: 'received',
  metadata: 'received',
  stamp: 'inferred',
  neighbours: 'inferred',
  manual: 'manual',
}

const TITLE: Record<Kind, string> = {
  received: 'Дата получена вместе со снимком',
  inferred: 'Дата выведена сервисом',
  manual: 'Дата введена инженером',
}

/** Источник даты снимка обязателен в интерфейсе (architecture §7.4). */
export function DateSourceBadge({ source }: { source: DateSource }) {
  const kind = KIND[source]
  return (
    <span
      className={[styles.badge, kind !== 'received' && styles[kind]].filter(Boolean).join(' ')}
      title={TITLE[kind]}
    >
      {kind === 'received' && <Icon name="camera" size={14} />}
      {kind === 'manual' && <Icon name="pencil" size={14} />}
      {dateSourceLabels[source]}
    </span>
  )
}
