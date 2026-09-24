import type { ReactNode } from 'react'
import styles from './PageHeader.module.css'

interface PageHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className={styles.head}>
      <div className={styles.text}>
        <h1>{title}</h1>
        {subtitle && <div className="muted">{subtitle}</div>}
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </div>
  )
}

interface SectionHeaderProps {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  level?: 2 | 3
}

/** Заголовок раздела страницы: h2 + пояснение мелким шрифтом + действия справа. */
export function SectionHeader({ title, description, actions, level = 2 }: SectionHeaderProps) {
  const Heading = level === 2 ? 'h2' : 'h3'
  return (
    <div className={styles.section}>
      <div>
        <Heading>{title}</Heading>
        {description && (
          <p className="sm muted" style={{ marginTop: 'var(--space-1)' }}>
            {description}
          </p>
        )}
      </div>
      {actions}
    </div>
  )
}
