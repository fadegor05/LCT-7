import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'
import styles from './Pill.module.css'

export type PillTone =
  | 'behind'
  | 'ontrack'
  | 'ahead'
  | 'caution'
  | 'cautionDashed'
  | 'accent'
  | 'neutral'
  | 'dashed'
  | 'unobserved'
  | 'outline'

interface PillProps {
  tone: PillTone
  icon?: IconName
  size?: 'md' | 'sm'
  children: ReactNode
}

/** Бейдж-«таблетка»: важность, итог, наблюдаемость, маркер и т. п. */
export function Pill({ tone, icon, size = 'md', children }: PillProps) {
  return (
    <span
      className={[styles.pill, styles[tone], size === 'sm' && styles.small]
        .filter(Boolean)
        .join(' ')}
    >
      {icon && <Icon name={icon} size={16} />}
      {children}
    </span>
  )
}
