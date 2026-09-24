import type { ReactNode } from 'react'
import { Icon } from './Icon'
import styles from './Callout.module.css'

export type CalloutTone = 'neutral' | 'caution' | 'behind'

interface CalloutProps {
  tone?: CalloutTone
  title?: string
  children?: ReactNode
}

export function Callout({ tone = 'neutral', title, children }: CalloutProps) {
  return (
    <div
      className={`${styles.callout} ${styles[tone]}`}
      role={tone === 'neutral' ? 'note' : 'alert'}
    >
      <span className={styles.icon}>
        <Icon name={tone === 'neutral' ? 'info' : 'alert'} size={24} />
      </span>
      <div className={styles.body}>
        {title && <p className={styles.title}>{title}</p>}
        {children && <div className={styles.text}>{children}</div>}
      </div>
    </div>
  )
}
